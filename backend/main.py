from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models, asyncio
from routes import sensors, devices, logs, hosts
from collectors.snmp_collector import collect_snmp_data
from collectors.sensor_collector import read_sensor_data
from collectors.network_scanner import run_network_scan
from utils.logger import db_log

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Smart Monitoring RRG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensors.router, prefix="/api/sensors", tags=["Sensors"])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(hosts.router, prefix="/api/hosts", tags=["Hosts"])

@app.get("/")
def root():
    return {"message": "Dashboard Smart Monitoring RRG - Actif"}

# Scan réseau toutes les 30 secondes (plus espacé car ARP est plus lent)
NETWORK_SCAN_INTERVAL = 30

async def background_collection_task():
    scan_counter: int = 0
    while True:
        try:
            # Collecte capteur + SNMP : toutes les 5 secondes
            read_sensor_data()
            collect_snmp_data()

            # Scan réseau : toutes les 30 secondes (1 fois sur 6 cycles)
            scan_counter += 1
            if scan_counter >= (NETWORK_SCAN_INTERVAL // 5):
                run_network_scan()
                scan_counter = 0

        except Exception as e:
            db_log(f"Erreur boucle principale: {e}", "error")
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    db_log("Demarrage de l'API Smart Monitoring", "info")
    # Premier scan réseau immédiat au démarrage
    run_network_scan()
    asyncio.create_task(background_collection_task())
