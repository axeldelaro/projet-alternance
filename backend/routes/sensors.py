from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas

router = APIRouter()

@router.get("/latest", response_model=schemas.SensorDataResponse)
def get_latest(db: Session = Depends(get_db)):
    latest = db.query(models.SensorData).order_by(models.SensorData.timestamp.desc()).first()
    if not latest:
        return models.SensorData(temperature=0.0, humidity=0.0)
    return latest

@router.get("/history", response_model=List[schemas.SensorDataResponse])
def get_history(limit: int = 20, db: Session = Depends(get_db)):
    return db.query(models.SensorData).order_by(models.SensorData.timestamp.desc()).limit(limit).all()
