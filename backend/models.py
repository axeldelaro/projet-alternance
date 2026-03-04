from sqlalchemy import Column, Integer, Float, String, DateTime
from datetime import datetime
from database import Base


class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    temperature = Column(Float)
    humidity = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)


class DeviceStatus(Base):
    __tablename__ = "device_status"

    id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(String)
    level = Column(String, default="info")
    timestamp = Column(DateTime, default=datetime.utcnow)


class DiscoveredHost(Base):
    __tablename__ = "discovered_hosts"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, unique=True)
    mac = Column(String)
    hostname = Column(String)
    status = Column(String, default="up")
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
