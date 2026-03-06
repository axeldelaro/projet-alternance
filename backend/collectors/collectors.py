"""
collectors.py — Collecteurs de données périodiques :
  - Capteurs environnementaux (température / humidité) : simulation ou DHT22 réel
  - Équipements réseau via SNMP
"""
import random
from db import SessionLocal, SensorData, DeviceStatus, db_log
from config_loader import config

# ---------------------------------------------------------------------------
# Capteur environnemental (DHT22 / simulation)
# ---------------------------------------------------------------------------

SIMULATION_MODE = config.get("simulation_mode", True)

if not SIMULATION_MODE:
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        db_log("RPi.GPIO absent, passage en mode simulation.", "warning")
        SIMULATION_MODE = True


def read_sensor_data():
    """Lit température + humidité (simulation ou capteur physique) et persiste en BDD."""
    if SIMULATION_MODE:
        temp = round(random.uniform(20.0, 35.0), 1)
        humidity = round(random.uniform(30.0, 70.0), 1)
    else:
        # TODO: lecture réelle DHT22 via adafruit_dht ou RPi.GPIO
        db_log("Lecture physique non implémentée, valeurs par défaut.", "info")
        temp = 22.0
        humidity = 50.0

    threshold = config.get("threshold_temp", 25.0)
    if temp > threshold:
        db_log(f"ALERTE: Température {temp}°C dépasse le seuil ({threshold}°C)", "warning")

    db = SessionLocal()
    try:
        db.add(SensorData(temperature=temp, humidity=humidity))
        db.commit()
    except Exception as e:
        db_log(f"Erreur enregistrement capteur: {e}", "error")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Collecte SNMP
# ---------------------------------------------------------------------------

SNMP_AVAILABLE = False
try:
    from pysnmp.hlapi import (
        getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
        ContextData, ObjectType, ObjectIdentity
    )
    SNMP_AVAILABLE = True
except ImportError:
    try:
        from pysnmp.hlapi.v1arch import (
            getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
            ContextData, ObjectType, ObjectIdentity
        )
        SNMP_AVAILABLE = True
    except ImportError:
        db_log("pysnmp non disponible ou version incompatible — collecte SNMP désactivée.", "warning")


def _get_device_status(ip: str, community: str, oid: str) -> str:
    if not SNMP_AVAILABLE:
        return "unknown"
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=0),
            UdpTransportTarget((ip, 161), timeout=2.0, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        if errorIndication or errorStatus:
            return "down"
        return "up"
    except Exception as e:
        db_log(f"SNMP error pour {ip}: {e}", "warning")
        return "down"


def collect_snmp_data():
    """Interroge les équipements SNMP configurés et persiste leurs statuts."""
    if not SNMP_AVAILABLE:
        return
    devices = config.get("devices", [])
    community = config.get("snmp_community", "public")
    db = SessionLocal()
    try:
        for device in devices:
            status = _get_device_status(device["ip"], community, device["oid_status"])
            db.add(DeviceStatus(device_name=device["name"], status=status))
            if status == "down":
                db_log(f"Équipement {device['name']} ({device['ip']}) est injoignable", "warning")
        db.commit()
    except Exception as e:
        db_log(f"Erreur collecte SNMP: {e}", "error")
    finally:
        db.close()
