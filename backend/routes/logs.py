from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas

router = APIRouter()

@router.get("/", response_model=List[schemas.LogResponse])
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(models.Log).order_by(models.Log.timestamp.desc()).limit(limit).all()
