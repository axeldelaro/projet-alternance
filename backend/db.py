import logging, yaml
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel, ConfigDict

try:
    with open(Path(__file__).parent / "config.yaml") as f:
        config = yaml.safe_load(f) or {}
except FileNotFoundError:
    config = {}

engine = create_engine("sqlite:///./monitoring.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class SensorData(Base):
    __tablename__ = "sensor_data"
    id = Column(Integer, primary_key=True)
    temperature = Column(Float)
    humidity = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DeviceStatus(Base):
    __tablename__ = "device_status"
    id = Column(Integer, primary_key=True)
    device_name = Column(String)
    status = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    message = Column(String)
    level = Column(String, default="info")
    timestamp = Column(DateTime, default=datetime.utcnow)

class DiscoveredHost(Base):
    __tablename__ = "discovered_hosts"
    id = Column(Integer, primary_key=True)
    ip = Column(String, unique=True)
    mac = Column(String)
    hostname = Column(String)
    status = Column(String, default="up")
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

_cfg = ConfigDict(from_attributes=True)

class SensorDataResponse(BaseModel):
    timestamp: datetime; temperature: float; humidity: float
    model_config = _cfg

class DeviceStatusResponse(BaseModel):
    device_name: str; status: str; timestamp: datetime
    model_config = _cfg

class LogResponse(BaseModel):
    timestamp: datetime; message: str; level: str
    model_config = _cfg

class DiscoveredHostResponse(BaseModel):
    id: int; ip: str; mac: str; hostname: str; status: str
    first_seen: datetime; last_seen: datetime
    model_config = _cfg

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger(__name__)

def db_log(msg: str, level: str = "info"):
    getattr(_log, level, _log.info)(msg)
    db = SessionLocal()
    try: db.add(Log(message=msg, level=level)); db.commit()
    except Exception as e: _log.error(e)
    finally: db.close()
