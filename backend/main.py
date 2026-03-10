from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import Base, engine, config
from routes import sensors_router, devices_router, logs_router, hosts_router

from apscheduler.schedulers.background import BackgroundScheduler
from collectors import run_network_scan, start_mdns_listener, stop_mdns_listener
from collectors import collect_snmp_data, read_sensor_data

# Intégration GPIO et alertes (mode production Raspberry Pi)
SIMULATION_MODE = config.get("simulation_mode", True)

if not SIMULATION_MODE:
    try:
        from gpio_sensors import read_sensor_data_gpio
        _sensor_fn = read_sensor_data_gpio
    except ImportError:
        _sensor_fn = read_sensor_data
else:
    _sensor_fn = read_sensor_data

try:
    from alerts import run_all_checks as run_alert_checks
    _alerts_available = True
except ImportError:
    _alerts_available = False

# Crée toutes les tables SQLite au démarrage
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Monitoring RRG",
    description="API de supervision réseau et environnement",
    version="1.0.0"
)

# Planificateur de tâches en arrière-plan
scheduler = BackgroundScheduler()


def scheduled_network_scan():
    try:
        run_network_scan()
    except Exception as e:
        print(f"Erreur lors du scan réseau : {e}")


def scheduled_snmp_and_sensors():
    try:
        collect_snmp_data()
        _sensor_fn()          # Simulation (Windows) ou DHT22 physique (Pi)
        if _alerts_available:
            run_alert_checks()  # Vérification des seuils et envoi d'alertes
    except Exception as e:
        print(f"Erreur lors de la collecte SNMP/Capteurs : {e}")


@app.on_event("startup")
def start_scheduler():
    start_mdns_listener()
    scheduler.add_job(scheduled_network_scan, 'interval', seconds=30, max_instances=1, coalesce=True)
    scheduler.add_job(scheduled_snmp_and_sensors, 'interval', seconds=5, max_instances=1, coalesce=True)
    scheduler.start()
    # Premier scan immédiat au démarrage
    scheduler.add_job(scheduled_network_scan, 'date')


@app.on_event("shutdown")
def shutdown_scheduler():
    stop_mdns_listener()
    scheduler.shutdown()


# CORS : autorise le frontend Vite et le réseau local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(sensors_router, prefix="/api/sensors", tags=["Sensors"])
app.include_router(devices_router, prefix="/api/devices", tags=["Devices"])
app.include_router(logs_router,    prefix="/api/logs",    tags=["Logs"])
app.include_router(hosts_router,   prefix="/api/hosts",   tags=["Hosts"])


@app.get("/")
def root():
    mode = "simulation" if SIMULATION_MODE else "production (GPIO)"
    return {
        "message": "Smart Monitoring RRG — API opérationnelle",
        "mode": mode,
        "alerts_engine": _alerts_available
    }
