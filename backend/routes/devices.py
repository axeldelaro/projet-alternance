from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from database import get_db
import models, schemas

router = APIRouter()

@router.get("/", response_model=List[schemas.DeviceStatusResponse])
def get_all_devices(db: Session = Depends(get_db)):
    subquery = db.query(
        models.DeviceStatus.device_name,
        func.max(models.DeviceStatus.timestamp).label("max_timestamp")
    ).group_by(models.DeviceStatus.device_name).subquery()

    return db.query(models.DeviceStatus).join(
        subquery,
        (models.DeviceStatus.device_name == subquery.c.device_name) &
        (models.DeviceStatus.timestamp == subquery.c.max_timestamp)
    ).all()
