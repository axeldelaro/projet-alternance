from pysnmp.hlapi import *
from database import SessionLocal
from models import DeviceStatus
from config_loader import config

def get_device_status(ip, community, oid):
    # Version simple sans gestion d'erreur
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community),
        UdpTransportTarget((ip, 161)),
        ContextData(),
        ObjectType(ObjectIdentity(oid))
    )
    errorIndication, errorStatus, _, _ = next(iterator)
    return "down" if (errorIndication or errorStatus) else "up"

def collect_snmp_data():
    db = SessionLocal()
    for device in config.get("devices", []):
        status = get_device_status(device["ip"], config["snmp_community"], device["oid_status"])
        db.add(DeviceStatus(device_name=device["name"], status=status))
    db.commit()
    db.close()
