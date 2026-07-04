import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "backend alive"}

@app.get("/challenge")
def challenge():
    return {"challenge_id": str(uuid.uuid4())}

@app.post("/verify")
def verify(payload: dict):
    return {
        "prediction": "Human",
        "confidence": 0.99
    }
