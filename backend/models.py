from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from database import Base

class SensorData(Base):
    __tablename__ = "sensor_data"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    temperature = Column(Float)
    humidity = Column(Float)

# TODO: ajouter DeviceStatus et Log
