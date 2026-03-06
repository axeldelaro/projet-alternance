"""
db.py — Couche données complète :
  - Connexion SQLAlchemy (engine, SessionLocal, Base, get_db)
  - Modèles ORM (SensorData, DeviceStatus, Log, DiscoveredHost)
  - Schémas Pydantic de réponse
  - Utilitaire de log BDD (db_log)
"""
import logging
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------

SQLALCHEMY_DATABASE_URL = "sqlite:///./monitoring.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Modèles ORM
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Schémas Pydantic
# ---------------------------------------------------------------------------

class SensorDataResponse(BaseModel):
    timestamp: datetime
    temperature: float
    humidity: float
    model_config = ConfigDict(from_attributes=True)


class DeviceStatusResponse(BaseModel):
    device_name: str
    status: str
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


class LogResponse(BaseModel):
    timestamp: datetime
    message: str
    level: str
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Logger BDD
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)


def db_log(message: str, level: str = "info"):
    """Écrit dans la console ET persiste le log en base de données."""
    getattr(_logger, level, _logger.info)(message)
    db = SessionLocal()
    try:
        db.add(Log(message=message, level=level))
        db.commit()
    except Exception as e:
        _logger.error(f"Erreur log BDD: {e}")
    finally:
        db.close()
