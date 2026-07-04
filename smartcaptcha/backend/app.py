from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import joblib
import uuid
import time

app = FastAPI()

challenges = {}

def cleanup_challenges():
    now = time.time()
    expired = [cid for cid, t in list(challenges.items()) if now - t > 300]
    for cid in expired:
        challenges.pop(cid, None)

@app.get("/challenge")
def get_challenge():
    cleanup_challenges()
    challenge_id = uuid.uuid4().hex
    challenges[challenge_id] = time.time()
    return {"challenge_id": challenge_id}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_PATH = "captcha_model.pkl"

# All 10 features the frontend sends — must match train_model.py FEATURE_COLUMNS
FEATURE_COLUMNS = [
    "avg_mouse_speed",
    "mouse_path_entropy",
    "click_delay",
    "task_completion_time",
    "idle_time",
    "micro_jitter_variance",
    "acceleration_curve",
    "curvature_variance",
    "overshoot_correction_ratio",
    "timing_entropy",
]

if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
    MODEL_LOADED = True
    print(f"[OK] Model loaded from {MODEL_PATH}")
    print(f"   Expected features: {model.n_features_in_}")
else:
    model = None
    MODEL_LOADED = False
    print("[WARN] ML model missing — running in safe fallback mode")


@app.get("/")
def root():
    return {
        "status": "backend alive",
        "model_loaded": MODEL_LOADED,
        "features": FEATURE_COLUMNS,
    }


@app.post("/verify")
def verify(payload: dict):
    cleanup_challenges()
    challenge_id = payload.get("challenge_id")
    if not challenge_id:
        raise HTTPException(status_code=400, detail="Missing challenge_id")
    
    if challenge_id not in challenges:
        raise HTTPException(status_code=403, detail="Invalid or expired challenge_id")
    
    creation_time = challenges.pop(challenge_id)
    if time.time() - creation_time > 300:
        raise HTTPException(status_code=403, detail="Expired challenge_id")


    # ------------------------------------------------------------------
    # HARD BOT RULE (FIRST GATE)
    # Catches naive automation before it even reaches the ML model.
    # Requires ALL four indicators simultaneously to avoid false positives.
    # ------------------------------------------------------------------
    try:
        speed     = float(payload.get("avg_mouse_speed", 0))
        entropy   = float(payload.get("mouse_path_entropy", 1))
        delay     = float(payload.get("click_delay", 1))
        dur       = float(payload.get("task_completion_time", 1))
        jitter    = float(payload.get("micro_jitter_variance", 1))
        timing_h  = float(payload.get("timing_entropy", 1))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid feature value: {exc}")

    naive_bot = (
        speed   > 2.2 and
        entropy < 0.08 and
        delay   < 0.2 and
        dur     < 0.8 and
        jitter  < 0.2 and
        timing_h < 0.10
    )
    if naive_bot:
        return {
            "prediction": "Bot",
            "confidence": 1.0,
            "gate": "hard_rule",
        }

    # ------------------------------------------------------------------
    # SAFE FALLBACK (NO MODEL)
    # ------------------------------------------------------------------
    if not MODEL_LOADED:
        return {
            "prediction": "Human",
            "confidence": 0.5,
            "gate": "fallback",
        }

    # ------------------------------------------------------------------
    # ML PREDICTION — all 10 features in exact training order
    # Missing features default to 0.0 (safe for tree-based models).
    # ------------------------------------------------------------------
    try:
        feature_vector = [[
            float(payload.get(col, 0.0)) for col in FEATURE_COLUMNS
        ]]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Feature extraction error: {exc}")

    prediction = model.predict(feature_vector)[0]
    proba      = model.predict_proba(feature_vector)[0]
    confidence = float(max(proba))

    return {
        "prediction": "Human" if int(prediction) == 1 else "Bot",
        "confidence": round(confidence, 4),
        "gate": "ml",
    }
