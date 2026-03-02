from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import DiscoveredHost
from collectors.network_scanner import ping_host
from utils.logger import db_log
from pydantic import BaseModel, ConfigDict
from datetime import datetime

router = APIRouter()

class DiscoveredHostResponse(BaseModel):
    id: int
    ip: str
    mac: str
    hostname: str
    status: str
    first_seen: datetime
    last_seen: datetime
    model_config = ConfigDict(from_attributes=True)

@router.get("/", response_model=List[DiscoveredHostResponse])
def get_all_discovered_hosts(db: Session = Depends(get_db)):
    """Retourne tous les équipements découverts automatiquement par scan ARP."""
    return db.query(DiscoveredHost).order_by(DiscoveredHost.last_seen.desc()).all()

@router.post("/{ip}/ping")
def ping_device(ip: str, db: Session = Depends(get_db)):
    """
    Envoie un ping ICMP vers l'IP spécifiée.
    Met à jour son statut dans la BDD et retourne le résultat.
    """
    host = db.query(DiscoveredHost).filter_by(ip=ip).first()
    if not host:
        raise HTTPException(status_code=404, detail=f"Aucun hôte enregistré pour l'IP {ip}")

    reachable = ping_host(ip)
    new_status = "up" if reachable else "down"

    host.status = new_status
    db.commit()

    db_log(f"Ping manuel vers {ip} ({host.hostname}) : {new_status.upper()}", "info")

    return {
        "ip": ip,
        "hostname": host.hostname,
        "status": new_status,
        "reachable": reachable
    }
