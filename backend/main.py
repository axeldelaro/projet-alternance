from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
from routes import sensors, devices, logs, hosts

from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
from collectors.network_scanner import run_network_scan

# Crée toutes les tables SQLite au démarrage
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Monitoring RRG",
    description="API de supervision réseau et environnement",
    version="1.0.0"
)

# Planificateur de tâches en arrière-plan
scheduler = BackgroundScheduler()

# Fonction wrapper pour exécuter le scan dans une boucle d'événement (si besoin de async)
def scheduled_network_scan():
    try:
        run_network_scan()
    except Exception as e:
        print(f"Erreur lors du scan programmé : {e}")

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(scheduled_network_scan, 'interval', seconds=10)
    scheduler.start()

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()

# CORS : autorise le frontend Vite (localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(sensors.router, prefix="/api/sensors", tags=["Sensors"])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
app.include_router(logs.router,    prefix="/api/logs",    tags=["Logs"])
app.include_router(hosts.router,   prefix="/api/hosts",   tags=["Hosts"])


@app.get("/")
def root():
    return {"message": "Smart Monitoring RRG — API opérationnelle"}
