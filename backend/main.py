from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models, asyncio
from routes import sensors, devices, logs
from collectors.snmp_collector import collect_snmp_data
from collectors.sensor_collector import read_sensor_data
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

@app.get("/")
def root():
    return {"message": "Dashboard Smart Monitoring RRG - Actif"}

async def background_collection_task():
    while True:
        try:
            read_sensor_data()
            collect_snmp_data()
        except Exception as e:
            db_log(f"Erreur boucle principale: {e}", "error")
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    db_log("Demarrage de l'API Smart Monitoring", "info")
    asyncio.create_task(background_collection_task())
