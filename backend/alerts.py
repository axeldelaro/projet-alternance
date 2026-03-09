"""
alerts.py — Moteur d'alertes du système Smart Monitoring RRG.

Ce module centralise toute la logique d'alerte :
  - Seuils configurables (température, humidité, SNMP down)
  - Dé-rebond (anti-flood) : une alerte ne se répète pas avant N secondes
  - Extensible : plug d'alerte email, Slack, SMS (hooks)

Ce fichier est conçu pour être intégré sur le Raspberry Pi.
Sur Windows, il fonctionne sans RPi.GPIO grâce au mode simulation de db.py.
"""

import time
import logging
from db import SessionLocal, Log, SensorData, DeviceStatus, db_log, config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# État interne : timestamps des dernières alertes (dé-rebond)
# ---------------------------------------------------------------------------
# Dictionnaire : clé = identifiant de type d'alerte, valeur = timestamp UNIX
# de la dernière émission. Permet de ne pas spammer les mêmes alertes.
_last_alert_times: dict[str, float] = {}

# Cooldown par défaut entre deux alertes identiques (en secondes)
DEFAULT_COOLDOWN_SECONDS = 60


def _should_alert(alert_key: str, cooldown: int = DEFAULT_COOLDOWN_SECONDS) -> bool:
    """
    Dé-rebond (debounce) : retourne True si l'alerte peut être envoyée.

    Une alerte avec la même clé ne peut se déclencher qu'une fois par période
    de cooldown. Cela évite de spammer les logs/notifications si la température
    reste élevée pendant 10 minutes (ce qui déclencherait 120 alertes à 5s d'intervalle).

    Paramètres
    ----------
    alert_key : str
        Identifiant unique du type d'alerte (ex: "temp_high", "device_down_192.168.1.1")
    cooldown : int
        Nombre de secondes minimum entre deux alertes identiques.

    Retourne
    --------
    bool : True si l'alerte doit être émise, False si elle est encore en cooldown.
    """
    now = time.monotonic()  # Horloge monotonique (non affectée par les changements d'heure système)
    last = _last_alert_times.get(alert_key, 0.0)
    if now - last >= cooldown:
        _last_alert_times[alert_key] = now
        return True
    return False


# ---------------------------------------------------------------------------
# Fonctions d'alerte métier
# ---------------------------------------------------------------------------

def check_temperature_alert():
    """
    Vérifie la dernière valeur de température et génère une alerte si le
    seuil configuré est dépassé.

    Logique :
    1. Lit la dernière mesure de la table sensor_data
    2. Compare avec config["threshold_temp"] (défaut 25.0°C)
    3. Si dépassement ET cooldown écoulé → log WARNING dans la BDD
    4. Appelle le hook d'extension (email, Slack...) si défini

    Appelée par APScheduler toutes les 5 secondes (via main.py).
    """
    threshold = config.get("threshold_temp", 25.0)
    db = SessionLocal()
    try:
        latest = db.query(SensorData).order_by(SensorData.timestamp.desc()).first()
        if latest is None:
            return  # Pas encore de données

        if latest.temperature > threshold:
            alert_key = "temp_high"
            if _should_alert(alert_key, cooldown=60):
                message = (
                    f"🌡️ ALERTE TEMPÉRATURE : {latest.temperature}°C "
                    f"dépasse le seuil de {threshold}°C"
                )
                db_log(message, "warning")
                _dispatch_alert("temperature", message, {
                    "value": latest.temperature,
                    "threshold": threshold,
                    "unit": "°C"
                })
        else:
            # Reset du dé-rebond si la température est revenue à la normale
            # (permet une nouvelle alerte dès le prochain dépassement)
            _last_alert_times.pop("temp_high", None)

    finally:
        db.close()


def check_humidity_alert():
    """
    Vérifie l'humidité. Alerte si en dehors de la plage [20%, 80%].

    Une humidité trop basse (<20%) = risque d'électricité statique (matériel)
    Une humidité trop haute (>80%) = risque de condensation sur le matériel
    """
    db = SessionLocal()
    try:
        latest = db.query(SensorData).order_by(SensorData.timestamp.desc()).first()
        if latest is None:
            return

        low_threshold = config.get("threshold_humidity_low", 20.0)
        high_threshold = config.get("threshold_humidity_high", 80.0)

        if latest.humidity < low_threshold:
            if _should_alert("humidity_low", cooldown=120):
                msg = f"💧 ALERTE HUMIDITÉ BASSE : {latest.humidity}% (seuil {low_threshold}%)"
                db_log(msg, "warning")
                _dispatch_alert("humidity_low", msg, {"value": latest.humidity})

        elif latest.humidity > high_threshold:
            if _should_alert("humidity_high", cooldown=120):
                msg = f"💧 ALERTE HUMIDITÉ HAUTE : {latest.humidity}% (seuil {high_threshold}%)"
                db_log(msg, "warning")
                _dispatch_alert("humidity_high", msg, {"value": latest.humidity})

        else:
            # Plage normale : reset des dé-rebonds
            _last_alert_times.pop("humidity_low", None)
            _last_alert_times.pop("humidity_high", None)

    finally:
        db.close()


def check_device_alerts():
    """
    Vérifie tous les équipements SNMP et génère des alertes pour ceux qui sont down.

    Le cooldown par device est géré individuellement : si 3 switchs sont down,
    on génère 3 alertes distinctes (clés : "device_down_192.168.1.1", etc.)
    """
    db = SessionLocal()
    try:
        # Récupère uniquement les derniers statuts (un par équipement)
        from sqlalchemy import func
        subquery = db.query(
            DeviceStatus.device_name,
            func.max(DeviceStatus.timestamp).label("max_timestamp")
        ).group_by(DeviceStatus.device_name).subquery()

        latest_statuses = db.query(DeviceStatus).join(
            subquery,
            (DeviceStatus.device_name == subquery.c.device_name) &
            (DeviceStatus.timestamp == subquery.c.max_timestamp)
        ).all()

        for device in latest_statuses:
            if device.status == "down":
                alert_key = f"device_down_{device.device_name}"
                if _should_alert(alert_key, cooldown=300):  # Alerte max toutes les 5 min
                    msg = f"🔴 ÉQUIPEMENT HORS LIGNE : {device.device_name} est injoignable"
                    db_log(msg, "error")
                    _dispatch_alert("device_down", msg, {
                        "device": device.device_name,
                        "since": device.timestamp.isoformat()
                    })
            else:
                # L'équipement est revenu : reset du dé-rebond
                _last_alert_times.pop(f"device_down_{device.device_name}", None)

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Hook d'extension (Slack, Email, SMS...)
# ---------------------------------------------------------------------------

def _dispatch_alert(alert_type: str, message: str, context: dict):
    """
    Point d'extension pour les notifications externes.

    Actuellement : log console uniquement.
    En production, ce hook pourrait envoyer :
      - Un email via smtplib (SMTP)
      - Un message Slack via webhook HTTP
      - Un SMS via API Twilio
      - Une notification Pushover pour smartphone

    Paramètres
    ----------
    alert_type : str
        Type de l'alerte (ex: "temperature", "humidity_high", "device_down")
    message : str
        Message lisible destiné à l'opérateur
    context : dict
        Données structurées supplémentaires (valeur mesurée, seuil, device...)
    """
    logger.warning(f"[ALERT:{alert_type.upper()}] {message} | context={context}")
    # TODO: implémenter les canaux de notification (email, Slack, SMS)
    # Exemple Slack (webhook) :
    # import requests
    # requests.post(SLACK_WEBHOOK_URL, json={"text": message})


# ---------------------------------------------------------------------------
# Fonction principale appelée par APScheduler
# ---------------------------------------------------------------------------

def run_all_checks():
    """
    Point d'entrée unique du moteur d'alertes.
    Exécute tous les checks dans l'ordre. Appelé par APScheduler toutes les 10s.
    """
    try:
        check_temperature_alert()
        check_humidity_alert()
        check_device_alerts()
    except Exception as e:
        logger.error(f"Erreur moteur d'alertes : {e}")
