from fastapi import FastAPI, HTTPException, Depends, Request, Header
from pydantic import BaseModel
import numpy as np
from datetime import datetime, timedelta
from app.classifier import classify_batch
from app.models import SessionLocal, Prediction, User, TokenBlacklist, AuditLog
from app.auth import (hash_password, verify_password,
                      create_access_token, create_refresh_token, decode_token)

app = FastAPI()

class ClassifyRequest(BaseModel):
    pixels: list[list[int]]

class ClassifyResponse(BaseModel):
    prediction: str
    confidence: float
    scores: dict[str, float]

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

def get_current_user(authorization: str = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ")[1]
    db = SessionLocal()
    blacklisted = db.query(TokenBlacklist).filter_by(token=token).first()
    db.close()
    if blacklisted:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload

def require_admin(payload: dict = Depends(get_current_user)):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    return payload

def log_action(email, action, ip, success):
    db = SessionLocal()
    db.add(AuditLog(user_email=email, action=action, ip_address=ip, success=success))
    db.commit()
    db.close()

@app.get("/health")
def health():
    return {"status": "ok", "model_version": "v1"}

@app.post("/auth/register")
def register(req: RegisterRequest, request: Request):
    db = SessionLocal()
    if db.query(User).filter_by(email=req.email).first():
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=req.email, hashed_password=hash_password(req.password))
    db.add(user)
    db.commit()
    db.close()
    log_action(req.email, "register", request.client.host, "success")
    return {"message": "User registered successfully"}

@app.post("/auth/login")
def login(req: LoginRequest, request: Request):
    db = SessionLocal()
    user = db.query(User).filter_by(email=req.email).first()
    ip = request.client.host
    if not user:
        db.close()
        log_action(req.email, "login", ip, "failed_no_user")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.locked_until and user.locked_until > datetime.utcnow():
        db.close()
        log_action(req.email, "login", ip, "failed_locked")
        raise HTTPException(status_code=403, detail="Account locked")
    if not verify_password(req.password, user.hashed_password):
        user.failed_attempts += 1
        if user.failed_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.commit()
        db.close()
        log_action(req.email, "login", ip, "failed_wrong_password")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user.failed_attempts = 0
    user.locked_until = None
    email = user.email
    role = user.role
    db.commit()
    db.close()
    token_data = {"sub": email, "role": role}
    log_action(email, "login", ip, "success")
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer"
    }

@app.post("/auth/logout")
def logout(authorization: str = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ")[1]
    db = SessionLocal()
    db.add(TokenBlacklist(token=token))
    db.commit()
    db.close()
    return {"message": "Logged out successfully"}

@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest, authorization: str = Header(default=None)):
    payload = get_current_user(authorization)
    arr = np.array(req.pixels, dtype=np.uint8)[np.newaxis]
    result = classify_batch(arr)[0]
    db = SessionLocal()
    db.add(Prediction(
        prediction=result["prediction"],
        confidence=result["confidence"],
        model_version="v1",
        user_email=payload.get("sub")
    ))
    db.commit()
    db.close()
    return result

@app.get("/results")
def results(authorization: str = Header(default=None)):
    payload = get_current_user(authorization)
    db = SessionLocal()
    rows = db.query(Prediction).filter_by(
        user_email=payload.get("sub")
    ).order_by(Prediction.created_at.desc()).limit(10).all()
    result_list = [
        {"id": r.id, "prediction": r.prediction,
         "confidence": r.confidence, "created_at": str(r.created_at)}
        for r in rows
    ]
    db.close()
    return {"results": result_list}

@app.get("/admin/results")
def admin_results(payload: dict = Depends(require_admin)):
    db = SessionLocal()
    rows = db.query(Prediction).order_by(Prediction.created_at.desc()).limit(50).all()
    result_list = [
        {"id": r.id, "prediction": r.prediction, "confidence": r.confidence,
         "user_email": r.user_email, "created_at": str(r.created_at)}
        for r in rows
    ]
    db.close()
    return {"results": result_list}

@app.get("/admin/audit")
def audit_log(payload: dict = Depends(require_admin)):
    db = SessionLocal()
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(50).all()
    log_list = [
        {"user": r.user_email, "action": r.action,
         "ip": r.ip_address, "success": r.success, "at": str(r.created_at)}
        for r in rows
    ]
    db.close()
    return {"logs": log_list}
