import random
from database import SessionLocal
from models import SensorData
from utils.logger import db_log
from config_loader import config

# Pour l'instant toujours en simulation
def read_sensor_data():
    temp = round(random.uniform(20.0, 35.0), 1)
    humidity = round(random.uniform(30.0, 70.0), 1)

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
