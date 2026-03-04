from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import Base, engine
from routes import sensors, devices, logs, hosts

# Crée toutes les tables SQLite au démarrage
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Monitoring RRG",
    description="API de supervision réseau et environnement",
    version="1.0.0"
)

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
