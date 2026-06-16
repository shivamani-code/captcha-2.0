from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import joblib

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_PATH = "captcha_model.pkl"

if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
    MODEL_LOADED = True
else:
    model = None
    MODEL_LOADED = False
    print("⚠️ ML model missing — running in safe fallback")


@app.get("/")
def root():
    return {"status": "backend alive"}


@app.post("/verify")
def verify(payload: dict):

    # ---------------------------
    # HARD BOT RULE (FIRST GATE)
    # ---------------------------
    if (
        payload["avg_mouse_speed"] > 2.0 and
        payload["mouse_path_entropy"] < 0.08 and
        payload["click_delay"] < 0.2 and
        payload["task_completion_time"] < 1.0
    ):
        return {
            "prediction": "Bot",
            "confidence": 1.0
        }

    # ---------------------------
    # SAFE FALLBACK (NO MODEL)
    # ---------------------------
    if not MODEL_LOADED:
        return {
            "prediction": "Human",
            "confidence": 0.5
        }

    # ---------------------------
    # ML PREDICTION
    # ---------------------------
    features = [[
        payload["avg_mouse_speed"],
        payload["mouse_path_entropy"],
        payload["click_delay"],
        payload["task_completion_time"],
        payload["idle_time"]
    ]]

    prediction = model.predict(features)[0]

    proba = model.predict_proba(features)[0]

    confidence = max(proba)

    return {
        "prediction": "Human" if prediction == 1 else "Bot",
        "confidence": round(float(confidence), 4)
    }
