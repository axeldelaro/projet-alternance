from contextlib import asynccontextmanager
from datetime import datetime
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from db import Base, engine, config, get_db, SessionLocal
from db import SensorData, DeviceStatus, Log, DiscoveredHost
from db import SensorDataResponse, DeviceStatusResponse, LogResponse, DiscoveredHostResponse, db_log
from collectors import run_network_scan, start_mdns_listener, stop_mdns_listener
from collectors import collect_snmp_data, read_sensor_data, read_sensor_data_gpio, run_all_checks, ping_host

SIMULATION_MODE = config.get("simulation_mode", True)
_sensor_fn = read_sensor_data if SIMULATION_MODE else read_sensor_data_gpio

Base.metadata.create_all(bind=engine)

scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_mdns_listener()
    scheduler.add_job(run_network_scan, 'interval', seconds=30, max_instances=1, coalesce=True)
    scheduler.add_job(lambda: (collect_snmp_data(), _sensor_fn(), run_all_checks()), 'interval', seconds=5, max_instances=1, coalesce=True)
    scheduler.start()
    scheduler.add_job(run_network_scan, 'date')
    yield
    stop_mdns_listener()
    scheduler.shutdown()

app = FastAPI(title="Smart Monitoring RRG", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"message": "Smart Monitoring RRG", "mode": "simulation" if SIMULATION_MODE else "production"}

# Sensors
@app.get("/api/sensors/latest", response_model=SensorDataResponse)
def get_latest(db: Session = Depends(get_db)):
    s = db.query(SensorData).order_by(SensorData.timestamp.desc()).first()
    return s or SensorData(temperature=0.0, humidity=0.0, timestamp=datetime.utcnow())

@app.get("/api/sensors/history", response_model=List[SensorDataResponse])
def get_history(limit: int = 20, db: Session = Depends(get_db)):
    return db.query(SensorData).order_by(SensorData.timestamp.desc()).limit(limit).all()

# Logs
@app.get("/api/logs", response_model=List[LogResponse])
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Log).order_by(Log.timestamp.desc()).limit(limit).all()

# Hosts
@app.get("/api/hosts", response_model=List[DiscoveredHostResponse])
def get_hosts(db: Session = Depends(get_db)):
    return db.query(DiscoveredHost).order_by(DiscoveredHost.last_seen.desc()).all()

@app.post("/api/hosts/{ip}/ping")
def ping_one(ip: str, db: Session = Depends(get_db)):
    host = db.query(DiscoveredHost).filter_by(ip=ip).first()
    if not host:
        raise HTTPException(404, f"Hôte {ip} inconnu")
    status = "up" if ping_host(ip) else "down"
    host.status = status; db.commit()
    db_log(f"Ping {ip} ({host.hostname}) : {status.upper()}", "info")
    return {"ip": ip, "hostname": host.hostname, "status": status}

@app.post("/api/hosts/ping-all")
def ping_all(db: Session = Depends(get_db)):
    hosts = db.query(DiscoveredHost).all()
    if not hosts:
        return {"total": 0, "up": 0, "down": 0, "results": []}

    def _ping(h):
        return h.ip, h.hostname, "up" if ping_host(h.ip) else "down"

    results = []
    with ThreadPoolExecutor(max_workers=32) as ex:
        for ip, hostname, status in [f.result() for f in as_completed(ex.submit(_ping, h) for h in hosts)]:
            results.append({"ip": ip, "hostname": hostname, "status": status})

    status_map = {r["ip"]: r["status"] for r in results}
    for h in hosts:
        if h.status != status_map.get(h.ip, h.status):
            h.status = status_map[h.ip]
            db_log(f"Ping-all : {h.ip} → {h.status.upper()}", "info")
    db.commit()
    up = sum(1 for r in results if r["status"] == "up")
    return {"total": len(results), "up": up, "down": len(results) - up, "results": results}
