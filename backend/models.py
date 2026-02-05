from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from database import Base

class SensorData(Base):
    __tablename__ = "sensor_data"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    temperature = Column(Float)
    humidity = Column(Float)

class DeviceStatus(Base):
    __tablename__ = "device_status"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    device_name = Column(String, index=True)
    status = Column(String)  # "up" ou "down"

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    message = Column(String)
    level = Column(String)  # "info", "warning", "error"
