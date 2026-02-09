from pysnmp.hlapi import *
from database import SessionLocal
from models import DeviceStatus
from utils.logger import db_log
from config_loader import config

def get_device_status(ip: str, community: str, oid: str) -> str:
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
        print(f"SNMP error pour {ip}: {e}")
        return "down"

def collect_snmp_data():
    devices = config.get("devices", [])
    community = config.get("snmp_community", "public")
    db = SessionLocal()
    try:
        for device in devices:
            status = get_device_status(device["ip"], community, device["oid_status"])
            db.add(DeviceStatus(device_name=device["name"], status=status))
            if status == "down":
                db_log(f"Equipement {device['name']} ({device['ip']}) est injoignable", "warning")
        db.commit()
    except Exception as e:
        db_log(f"Erreur collecte SNMP: {e}", "error")
    finally:
        db.close()
