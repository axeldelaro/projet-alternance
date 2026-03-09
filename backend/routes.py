"""
routes.py — Tous les endpoints API regroupés :
  /api/sensors  — données capteurs (température, humidité)
  /api/devices  — équipements SNMP
  /api/logs     — journal d'événements
  /api/hosts    — hôtes découverts par scan réseau
"""
from datetime import datetime
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict

from db import get_db, SensorData, DeviceStatus, Log, DiscoveredHost
from db import SensorDataResponse, DeviceStatusResponse, LogResponse
from db import db_log
from collectors import ping_host

# ---------------------------------------------------------------------------
# /api/sensors
# ---------------------------------------------------------------------------
sensors_router = APIRouter()


@sensors_router.get("/latest", response_model=SensorDataResponse)
def get_latest(db: Session = Depends(get_db)):
    latest = db.query(SensorData).order_by(SensorData.timestamp.desc()).first()
    if not latest:
        return SensorData(temperature=0.0, humidity=0.0, timestamp=datetime.utcnow())
    return latest


@sensors_router.get("/history", response_model=List[SensorDataResponse])
def get_history(limit: int = 20, db: Session = Depends(get_db)):
    return db.query(SensorData).order_by(SensorData.timestamp.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# /api/devices
# ---------------------------------------------------------------------------
devices_router = APIRouter()


@devices_router.get("/", response_model=List[DeviceStatusResponse])
def get_all_devices(db: Session = Depends(get_db)):
    subquery = db.query(
        DeviceStatus.device_name,
        func.max(DeviceStatus.timestamp).label("max_timestamp")
    ).group_by(DeviceStatus.device_name).subquery()

    return db.query(DeviceStatus).join(
        subquery,
        (DeviceStatus.device_name == subquery.c.device_name) &
        (DeviceStatus.timestamp == subquery.c.max_timestamp)
    ).all()


# ---------------------------------------------------------------------------
# /api/logs
# ---------------------------------------------------------------------------
logs_router = APIRouter()


@logs_router.get("/", response_model=List[LogResponse])
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Log).order_by(Log.timestamp.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# /api/hosts
# ---------------------------------------------------------------------------
hosts_router = APIRouter()


class DiscoveredHostResponse(BaseModel):
    id: int
    ip: str
    mac: str
    hostname: str
    status: str
    first_seen: datetime
    last_seen: datetime
    model_config = ConfigDict(from_attributes=True)


@hosts_router.get("/", response_model=List[DiscoveredHostResponse])
def get_all_discovered_hosts(db: Session = Depends(get_db)):
    """Retourne tous les équipements découverts automatiquement par scan ARP."""
    return db.query(DiscoveredHost).order_by(DiscoveredHost.last_seen.desc()).all()


@hosts_router.post("/{ip}/ping")
def ping_device(ip: str, db: Session = Depends(get_db)):
    """Envoie un ping ICMP vers l'IP spécifiée et met à jour son statut."""
    host = db.query(DiscoveredHost).filter_by(ip=ip).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Aucun hôte enregistré pour l'IP {ip}")

    reachable = ping_host(ip)
    new_status = "up" if reachable else "down"
    host.status = new_status
    db.commit()
    db_log(f"Ping manuel vers {ip} ({host.hostname}) : {new_status.upper()}", "info")
    return {"ip": ip, "hostname": host.hostname, "status": new_status, "reachable": reachable}


@hosts_router.post("/ping-all")
def ping_all_devices(db: Session = Depends(get_db)):
    """Ping tous les hôtes connus en parallèle et retourne un résumé."""
    hosts = db.query(DiscoveredHost).all()
    if not hosts:
        return {"total": 0, "up": 0, "down": 0, "results": []}

    def _ping_one(host):
        reachable = ping_host(host.ip)
        return host.ip, host.hostname, "up" if reachable else "down"

    results = []
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(_ping_one, h): h for h in hosts}
        for future in as_completed(futures):
            ip, hostname, status = future.result()
            results.append({"ip": ip, "hostname": hostname, "status": status})

    status_map = {r["ip"]: r["status"] for r in results}
    for host in hosts:
        new_status = status_map.get(host.ip, host.status)
        if host.status != new_status:
            host.status = new_status
            db_log(f"Ping-all : {host.ip} ({host.hostname}) → {new_status.upper()}", "info")
    db.commit()

    up_count = sum(1 for r in results if r["status"] == "up")
    return {
        "total": len(results),
        "up": up_count,
        "down": len(results) - up_count,
        "results": results
    }
