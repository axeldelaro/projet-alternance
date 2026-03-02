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

class DiscoveredHost(Base):
    """
    Représente un équipement découvert automatiquement par scan ARP.
    Alimenté par le module collectors/network_scanner.py.
    """
    __tablename__ = "discovered_hosts"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, unique=True, index=True)       # Adresse IP de l'hôte
    mac = Column(String)                               # Adresse MAC (identifiant matériel)
    hostname = Column(String, default="unknown")       # Nom DNS résolu si disponible
    status = Column(String, default="up")             # "up" ou "down"
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
