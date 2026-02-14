from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models
from routes import sensors, devices, logs

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Smart Monitoring RRG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensors.router, prefix="/api/sensors", tags=["Sensors"])
app.include_router(devices.router, prefix="/api/devices", tags=["Devices"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])

@app.get("/")
def root():
    return {"message": "Smart Monitoring RRG - Actif"}

# TODO: ajouter la boucle de collecte en fond
