import random
from database import SessionLocal
from models import SensorData
from utils.logger import db_log
from config_loader import config

SIMULATION_MODE = config.get("simulation_mode", True)

if not SIMULATION_MODE:
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        db_log("RPi.GPIO absent, passage en mode simulation.", "warning")
        SIMULATION_MODE = True

def read_sensor_data():
    if SIMULATION_MODE:
        temp = round(random.uniform(20.0, 35.0), 1)
        humidity = round(random.uniform(30.0, 70.0), 1)
    else:
        # TODO: lecture reelle DHT22 via adafruit_dht ou RPi.GPIO
        db_log("Lecture physique non implementee, valeurs par defaut.", "info")
        temp = 22.0
        humidity = 50.0

    threshold = config.get("threshold_temp", 25.0)
    if temp > threshold:
        db_log(f"ALERTE: Temperature {temp}C depasse le seuil ({threshold}C)", "warning")

    db = SessionLocal()
    try:
        db.add(SensorData(temperature=temp, humidity=humidity))
        db.commit()
    except Exception as e:
        db_log(f"Erreur enregistrement capteur: {e}", "error")
    finally:
        db.close()
