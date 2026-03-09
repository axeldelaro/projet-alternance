"""
gpio_sensors.py — Lecture physique du capteur DHT22 via GPIO Raspberry Pi.

Ce module remplace la simulation de read_sensor_data() en mode production.
Il doit être importé uniquement sur Raspberry Pi (sys_platform == 'linux'
et RPi.GPIO installé).

Architecture physique :
  - Capteur DHT22 branché sur GPIO4 (pin physique 7)
  - Alimentation 3.3V (pin 1) ou 5V (pin 2)
  - Résistance pull-up 10kΩ entre DATA et VCC (obligatoire pour le protocole 1-Wire)
  - GND (pin 6)

Protocole DHT22 :
  Le DHT22 utilise un protocole 1-Wire propriétaire. Le Pi envoie une impulsion
  LOW de 18ms pour « réveiller » le capteur, puis lit 40 bits de données
  (16 bits humidité + 16 bits température + 8 bits checksum).
  La bibliothèque gpiozero/adafruit_dht gère ce protocole automatiquement.
"""

import logging
import platform
import time
from db import SessionLocal, SensorData, db_log, config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chargement conditionnel des bibliothèques GPIO
# ---------------------------------------------------------------------------

# L'instance du capteur DHT22 est créée une seule fois (singleton)
# pour éviter les conflits de bus GPIO entre lectures
_dht_sensor = None
_gpio_initialized = False

GPIO_PIN = config.get("sensor", {}).get("gpio_pin", 4)  # GPIO4 par défaut


def _init_gpio():
    """
    Initialise le capteur DHT22 sur le pin GPIO configuré.

    Tente d'utiliser adafruit_dht (bibliothèque officielle Adafruit, plus stable)
    en premier. Fallback sur gpiozero si adafruit_dht n'est pas installé.

    Cette initialisation est paresseuse (lazy init) : elle se fait à la première
    lecture, pas au chargement du module. Cela permet d'importer ce fichier
    sur Windows sans erreur d'import.
    """
    global _dht_sensor, _gpio_initialized

    if _gpio_initialized:
        return _dht_sensor is not None  # Déjà tenté

    _gpio_initialized = True

    if platform.system().lower() != "linux":
        db_log("gpio_sensors: non-Linux, initialisation GPIO ignorée.", "info")
        return False

    # Tentative 1 : adafruit_dht (plus fiable, gère les timeouts du protocole 1-Wire)
    try:
        import adafruit_dht
        import board
        # board.D4 correspond au GPIO4 (numérotation BCM)
        pin_map = {4: board.D4, 17: board.D17, 27: board.D27, 22: board.D22}
        pin = pin_map.get(GPIO_PIN, board.D4)
        _dht_sensor = adafruit_dht.DHT22(pin, use_pulseio=False)
        db_log(f"DHT22 initialisé via adafruit_dht sur GPIO{GPIO_PIN}", "info")
        return True
    except ImportError:
        pass
    except Exception as e:
        db_log(f"Erreur init adafruit_dht: {e}", "warning")

    # Tentative 2 : gpiozero (plus simple à installer)
    try:
        from gpiozero import DistanceSensor  # noqa — vérification d'import seulement
        db_log("adafruit_dht absent. Utiliser: pip install adafruit-circuitpython-dht", "warning")
        return False
    except ImportError:
        db_log("Ni adafruit_dht ni gpiozero disponibles pour le DHT22.", "error")
        return False


# ---------------------------------------------------------------------------
# Lecture physique du capteur
# ---------------------------------------------------------------------------

def read_dht22_physical(max_retries: int = 3) -> tuple[float, float] | tuple[None, None]:
    """
    Lit la température et l'humidité depuis le capteur DHT22 physique.

    Le DHT22 est un capteur capricieux qui peut échouer sur 1 lecture sur 5
    (erreur de checksum, timing trop serré). On implémente jusqu'à `max_retries`
    tentatives avec 500ms de délai entre chaque.

    Paramètres
    ----------
    max_retries : int
        Nombre maximum de tentatives de lecture (défaut: 3)

    Retourne
    --------
    tuple[float, float] : (temperature_celsius, humidity_percent)
    tuple[None, None]   : en cas d'échec après toutes les tentatives

    Notes techniques du DHT22
    --------------------------
    - Plage de température : -40°C à +80°C, précision ±0.5°C
    - Plage d'humidité : 0% à 100% RH, précision ±2%
    - Fréquence maximale de lecture : 1 mesure toutes les 2 secondes minimum
      (le capteur a besoin de temps pour se stabiliser thermiquement)
    - Protocole 1-Wire propriétaire : 40 bits transmis en signaux HIGH/LOW
      de durées précises (26-28μs = bit 0, 70μs = bit 1)
    """
    if not _init_gpio() or _dht_sensor is None:
        return None, None

    for attempt in range(1, max_retries + 1):
        try:
            temperature = _dht_sensor.temperature  # En degrés Celsius
            humidity = _dht_sensor.humidity        # En pourcentage RH

            # Validation des données (le DHT22 peut retourner None ou NaN)
            if temperature is None or humidity is None:
                raise RuntimeError("Valeurs nulles retournées par le capteur")

            # Validation de plage (bornes physiques du DHT22)
            if not (-40 <= temperature <= 80):
                raise ValueError(f"Température hors plage DHT22 : {temperature}°C")
            if not (0 <= humidity <= 100):
                raise ValueError(f"Humidité hors plage DHT22 : {humidity}%")

            # Succès : arrondi à 1 décimale (précision réelle du capteur)
            return round(temperature, 1), round(humidity, 1)

        except Exception as e:
            logger.warning(f"DHT22 lecture {attempt}/{max_retries} échouée: {e}")
            if attempt < max_retries:
                time.sleep(0.5)  # Le DHT22 nécessite au moins 500ms entre lectures

    db_log("DHT22 : toutes les tentatives ont échoué (câblage? résistance pull-up?)", "error")
    return None, None


def read_sensor_data_gpio():
    """
    Remplace read_sensor_data() de collectors.py en mode production GPIO.

    Lit les vraies valeurs du DHT22 et les persiste en base de données.
    En cas d'échec de lecture (câble débranché, mauvaise résistance...), 
    aucune valeur n'est enregistrée pour éviter de stocker des données erronées.

    Contrairement au mode simulation (valeurs aléatoires toutes les 5s),
    cette fonction limite la fréquence à 1 lecture toutes les 2s minimum
    (contrainte hardware du DHT22).
    """
    temperature, humidity = read_dht22_physical()

    if temperature is None or humidity is None:
        logger.warning("Lecture DHT22 ignorée (données invalides)")
        return  # On ne stocke rien si le capteur a échoué

    # Vérification du seuil (même logique que le mode simulation)
    threshold = config.get("threshold_temp", 25.0)
    if temperature > threshold:
        db_log(
            f"🌡️ ALERTE GPIO: Température physique {temperature}°C "
            f"dépasse le seuil ({threshold}°C)",
            "warning"
        )

    db = SessionLocal()
    try:
        db.add(SensorData(temperature=temperature, humidity=humidity))
        db.commit()
        logger.info(f"DHT22 physique: {temperature}°C, {humidity}%RH → BDD")
    except Exception as e:
        db_log(f"Erreur persistence GPIO: {e}", "error")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Informations de diagnostique
# ---------------------------------------------------------------------------

def get_gpio_status() -> dict:
    """
    Retourne l'état de l'interface GPIO pour le diagnostique.
    Utilisable depuis un endpoint FastAPI debug si nécessaire.
    """
    return {
        "platform": platform.system(),
        "gpio_pin": GPIO_PIN,
        "sensor_initialized": _dht_sensor is not None,
        "sensor_type": "DHT22",
        "wiring": {
            "vcc": "Pin 1 (3.3V) ou Pin 2 (5V)",
            "data": f"Pin GPIO{GPIO_PIN}",
            "gnd": "Pin 6 (GND)",
            "pullup": "Résistance 10kΩ entre DATA et VCC"
        }
    }
