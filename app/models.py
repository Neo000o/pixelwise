from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    prediction = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    model_version = Column(String, nullable=False)
    user_email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"
    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, nullable=False)
    blacklisted_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    user_email = Column(String, nullable=True)
    action = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    success = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

DB_PASSWORD = os.getenv("DB_PASSWORD")
DATABASE_URL = f"postgresql://pixelwise:{DB_PASSWORD}@localhost/pixelwise"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
