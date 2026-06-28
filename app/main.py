from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
from app.classifier import classify_batch
from app.models import SessionLocal, Prediction

class ClassifyRequest(BaseModel):
    pixels: list[list[int]]

class ClassifyResponse(BaseModel):
    prediction: str
    confidence: float
    scores: dict[str, float]

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok", "model_version": "v1"}

@app.get("/results")
def results():
    db = SessionLocal()
    rows = db.query(Prediction).order_by(Prediction.created_at.desc()).limit(10).all()
    db.close()
    return {"results": [
        {"id": r.id, "prediction": r.prediction,
         "confidence": r.confidence, "model_version": r.model_version,
         "created_at": str(r.created_at)}
        for r in rows
    ]}

@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest):
    arr = np.array(req.pixels, dtype=np.uint8)[np.newaxis]
    result = classify_batch(arr)[0]
    db = SessionLocal()
    row = Prediction(
        prediction=result["prediction"],
        confidence=result["confidence"],
        model_version="v1"
    )
    db.add(row)
    db.commit()
    db.close()
    return result
