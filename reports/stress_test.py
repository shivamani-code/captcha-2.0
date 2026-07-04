import sys
import os
import json
import time
import urllib.request
import urllib.error
import numpy as np

# Add backend to path to import app and challenges for in-memory expired test
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "smartcaptcha", "backend")))
from app import app, challenges

use_testclient = False

VERIFY_URL = "http://localhost:8000/verify"
CHALLENGE_URL = "http://localhost:8000/challenge"

RNG = np.random.default_rng(seed=42)

def generate_human_features() -> dict:
    speed = float(RNG.uniform(100.0, 600.0))
    if RNG.random() < 0.1:
        speed = float(RNG.uniform(550.0, 800.0))
    return {
        "avg_mouse_speed":           round(speed, 4),
        "mouse_path_entropy":        round(float(RNG.uniform(0.25, 0.90)), 4),
        "click_delay":               round(float(RNG.uniform(0.5, 3.0)), 4),
        "task_completion_time":      round(float(RNG.uniform(0.6, 4.0)), 4),
        "idle_time":                 round(float(RNG.uniform(0.0, 0.8)), 4),
        "micro_jitter_variance":     round(float(RNG.uniform(5.0, 120.0)), 4),
        "acceleration_curve":        round(float(RNG.uniform(800.0, 6000.0)), 4),
        "curvature_variance":        round(float(RNG.uniform(0.0005, 0.12)), 4),
        "overshoot_correction_ratio":round(float(RNG.beta(1.5, 12) * 0.25), 4),
        "timing_entropy":            round(float(RNG.uniform(0.45, 0.98)), 4),
    }

def generate_bot_features() -> dict:
    # Generate naive bot-like features
    return {
        "avg_mouse_speed":            round(float(RNG.uniform(1200.0, 3000.0)), 4),
        "mouse_path_entropy":         round(float(RNG.uniform(0.0, 0.06)), 4),
        "click_delay":                round(float(RNG.uniform(0.01, 0.15)), 4),
        "task_completion_time":       round(float(RNG.uniform(0.08, 0.5)), 4),
        "idle_time":                  round(float(RNG.uniform(0.0, 0.02)), 4),
        "micro_jitter_variance":      round(float(RNG.uniform(0.0, 0.2)), 4),
        "acceleration_curve":         round(float(RNG.uniform(0.0, 80.0)), 4),
        "curvature_variance":         round(float(RNG.uniform(0.0, 0.0008)), 4),
        "overshoot_correction_ratio": round(float(RNG.uniform(0.0, 0.005)), 4),
        "timing_entropy":             round(float(RNG.uniform(0.0, 0.08)), 4),
    }

def make_post(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return e.code, json.loads(body)
        except Exception:
            return e.code, e.reason

def get_challenge():
    with urllib.request.urlopen(CHALLENGE_URL) as res:
        return json.loads(res.read().decode())["challenge_id"]

print("--- Starting Stress Testing ---")
human_accepted = 0
human_rejected = 0
bot_accepted = 0
bot_rejected = 0

# 15 Human attempts
for i in range(15):
    cid = get_challenge()
    payload = generate_human_features()
    payload["challenge_id"] = cid
    status, resp = make_post(VERIFY_URL, payload)
    if status == 200 and resp.get("prediction") == "Human":
        human_accepted += 1
    else:
        human_rejected += 1

# 15 Bot attempts
for i in range(15):
    cid = get_challenge()
    payload = generate_bot_features()
    payload["challenge_id"] = cid
    status, resp = make_post(VERIFY_URL, payload)
    if status == 200 and resp.get("prediction") == "Human":
        bot_accepted += 1
    else:
        bot_rejected += 1

print(f"Human attempts: Accepted={human_accepted}, Rejected={human_rejected}")
print(f"Bot attempts: Accepted={bot_accepted}, Rejected={bot_rejected}")

print("\n--- Starting Security Validation ---")
security_results = {}

# 1. Missing challenge ID
print("Testing Missing Challenge ID...")
status, resp = make_post(VERIFY_URL, generate_human_features())
security_results["missing_id"] = {
    "status": status,
    "response": resp,
    "passed": status == 400
}

# 2. Fake challenge ID
print("Testing Fake Challenge ID...")
payload = generate_human_features()
payload["challenge_id"] = "fake_id_xyz_987"
status, resp = make_post(VERIFY_URL, payload)
security_results["fake_id"] = {
    "status": status,
    "response": resp,
    "passed": status == 403
}

# 3. Reused challenge ID
print("Testing Reused Challenge ID...")
cid = get_challenge()
payload = generate_human_features()
payload["challenge_id"] = cid
# first call (should succeed)
status1, resp1 = make_post(VERIFY_URL, payload)
# second call with same cid (should be rejected)
status2, resp2 = make_post(VERIFY_URL, payload)
security_results["reused_id"] = {
    "status_first": status1,
    "status_second": status2,
    "response_second": resp2,
    "passed": status1 == 200 and status2 == 403
}

# 4. Expired challenge ID
print("Testing Expired Challenge ID...")
# Inject an expired challenge directly into the backend's challenges dict
expired_cid = "expired_test_token_112233"
challenges[expired_cid] = time.time() - 600 # 10 mins ago (expired)

if use_testclient:
    # Use TestClient to verify the backend behavior for the injected expired challenge
    payload = generate_human_features()
    payload["challenge_id"] = expired_cid
    response = client.post("/verify", json=payload)
    passed = response.status_code == 403 and "expired" in response.json().get("detail", "").lower()
    status_code = response.status_code
    resp_json = response.json()
else:
    # Safe fallback direct validation call if TestClient isn't available
    from fastapi import HTTPException
    try:
        # Import verify endpoint directly and run it
        from app import verify
        payload = generate_human_features()
        payload["challenge_id"] = expired_cid
        verify(payload)
        passed = False
        status_code = 200
        resp_json = "Allowed (Error: verification did not raise exception)"
    except HTTPException as e:
        passed = e.status_code == 403 and "expired" in e.detail.lower()
        status_code = e.status_code
        resp_json = {"detail": e.detail}

security_results["expired_id"] = {
    "status": status_code,
    "response": resp_json,
    "passed": passed
}

print("Security check results:")
for k, v in security_results.items():
    print(f"  {k}: {'PASS' if v['passed'] else 'FAIL'} (Status: {v.get('status') or v.get('status_second')})")

output_results = {
    "stress_test": {
        "human": {
            "attempts": 15,
            "accepted": human_accepted,
            "rejected": human_rejected
        },
        "bot": {
            "attempts": 15,
            "accepted": bot_accepted,
            "rejected": bot_rejected
        }
    },
    "security": security_results
}

os.makedirs(os.path.dirname(__file__), exist_ok=True)
with open(os.path.join(os.path.dirname(__file__), "stress_results.json"), "w") as f:
    json.dump(output_results, f, indent=2)

print("\nValidation script completed and results exported to stress_results.json")
