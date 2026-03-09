"""
collectors.py — Découverte réseau & collecte de données environnementales.

Contient :
  1. Listener mDNS  : écoute passive des annonces Bonjour/NSD sur le LAN
  2. Scanner réseau : ping sweep + lecture ARP → découverte automatique des hôtes
  3. Capteur DHT22  : lecture température/humidité (simulation ou GPIO réel)
  4. Collecte SNMP  : interrogation des équipements réseau configurés
"""

# ============================================================================
# Imports
# ============================================================================
import random
import subprocess
import socket
import ipaddress
import platform
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from db import SessionLocal, SensorData, DeviceStatus, DiscoveredHost, db_log, config

# ---------------------------------------------------------------------------
# Bibliothèques optionnelles
# ---------------------------------------------------------------------------
try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

try:
    from scapy.all import ARP, Ether, srp
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

try:
    from mac_vendor_lookup import MacLookup, VendorNotFoundError
    _mac_lookup = MacLookup()
    MAC_LOOKUP_AVAILABLE = True
except ImportError:
    MAC_LOOKUP_AVAILABLE = False

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
        db_log("pysnmp non disponible — collecte SNMP désactivée.", "warning")

SIMULATION_MODE = config.get("simulation_mode", True)
if not SIMULATION_MODE:
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        db_log("RPi.GPIO absent, passage en mode simulation.", "warning")
        SIMULATION_MODE = True


# ============================================================================
# 1. LISTENER mDNS (Bonjour / NSD)
# ============================================================================

# Cache IP → nom d'hôte résolu par mDNS
_mdns_cache: dict[str, str] = {}
_cache_lock = threading.Lock()

SERVICES_TO_BROWSE = [
    "_device-info._tcp.local.",    # iOS (iPhone, iPad)
    "_http._tcp.local.",            # Appareils généralistes
    "_googlecast._tcp.local.",      # Chromecast / Android TV
    "_androidtvremote2._tcp.local.", # Android TV
    "_companion-link._tcp.local.",  # Apple Watch / Continuity
    "_rdlink._tcp.local.",          # Apple
]


class _MdnsListener(ServiceListener if ZEROCONF_AVAILABLE else object):
    """Reçoit les événements mDNS et met à jour le cache IP → nom."""

    def add_service(self, zc, type_: str, name: str) -> None:
        try:
            info = zc.get_service_info(type_, name, timeout=1000)
            if not info:
                return
            for addr_bytes in info.addresses:
                ip = socket.inet_ntoa(addr_bytes)
                friendly = name.replace(f".{type_}", "").replace("._device-info._tcp.local.", "").strip(". ")
                if friendly and ip:
                    with _cache_lock:
                        if ip not in _mdns_cache:
                            _mdns_cache[ip] = friendly
                            db_log(f"mDNS : {ip} → {friendly}", "info")
        except Exception:
            pass

    def remove_service(self, zc, type_, name): pass
    def update_service(self, zc, type_, name): self.add_service(zc, type_, name)


_zeroconf_instance = None
_browsers: list = []


def start_mdns_listener():
    """Démarre l'écoute mDNS en arrière-plan (appelé au démarrage du serveur)."""
    global _zeroconf_instance, _browsers
    if not ZEROCONF_AVAILABLE:
        db_log("zeroconf non disponible — mDNS désactivé. pip install zeroconf", "warning")
        return
    try:
        _zeroconf_instance = Zeroconf()
        listener = _MdnsListener()
        for service in SERVICES_TO_BROWSE:
            _browsers.append(ServiceBrowser(_zeroconf_instance, service, listener))
        db_log("Listener mDNS démarré — écoute Bonjour/NSD.", "info")
    except Exception as e:
        db_log(f"Erreur démarrage mDNS: {e}", "warning")


def stop_mdns_listener():
    """Arrête proprement le listener mDNS."""
    global _zeroconf_instance
    if _zeroconf_instance:
        try:
            _zeroconf_instance.close()
        except Exception:
            pass


def _get_mdns_name(ip: str) -> str | None:
    """Retourne le nom mDNS connu pour une IP (depuis le cache)."""
    with _cache_lock:
        return _mdns_cache.get(ip)


# ============================================================================
# 2. SCANNER RÉSEAU (ping sweep + ARP)
# ============================================================================

def _is_randomized_mac(mac: str) -> bool:
    """Détecte une MAC localement administrée (iOS 14+ / Android 10+)."""
    try:
        first_byte = int(mac.replace(":", "").replace("-", "")[:2], 16)
        return bool(first_byte & 0x02)
    except Exception:
        return False


def _resolve_vendor(mac: str) -> str:
    """Retourne le fabricant via OUI. Signale les MACs randomisées."""
    if not mac:
        return ""
    if _is_randomized_mac(mac):
        return "Mobile (MAC aléatoire)"
    if not MAC_LOOKUP_AVAILABLE:
        return ""
    try:
        return _mac_lookup.lookup(mac)
    except Exception:
        return ""


def _resolve_hostname(ip: str, mac: str = "") -> str:
    """
    Résolution de nom en cascade :
    1. DNS inverse (PTR)
    2. NetBIOS (nbtstat -A) — Windows
    3. Cache mDNS (Bonjour/NSD)
    4. Fabricant OUI (MAC)
    5. Fallback 'unknown'
    """
    try:
        name = socket.gethostbyaddr(ip)[0]
        if name and name != ip:
            return name
    except (socket.herror, socket.gaierror):
        pass

    if platform.system().lower() == "windows":
        try:
            output = subprocess.check_output(
                ["nbtstat", "-A", ip],
                encoding="cp850", errors="ignore", timeout=1, stderr=subprocess.DEVNULL
            )
            match = re.search(r"^\s*([A-Za-z0-9_\-]+)\s+<00>\s+UNIQUE", output, re.MULTILINE)
            if match:
                return match.group(1).strip()
        except Exception:
            pass

    mdns_name = _get_mdns_name(ip)
    if mdns_name:
        return mdns_name

    vendor = _resolve_vendor(mac)
    if vendor:
        return vendor

    return "unknown"


def ping_host(ip: str, timeout: int = 1) -> bool:
    """Ping ICMP natif (compatible Windows et Linux)."""
    try:
        if platform.system().lower() == "windows":
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout * 1000), ip],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(timeout), ip],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        return result.returncode == 0
    except Exception:
        return False


def _get_local_ip() -> str:
    """Retourne l'IP de l'interface réseau principale (trick UDP fictif vers 8.8.8.8)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None


def _get_local_subnets() -> list:
    """Détecte automatiquement tous les sous-réseaux locaux actifs."""
    subnets = set()

    primary_ip = _get_local_ip()
    if primary_ip and not primary_ip.startswith("127."):
        network = ipaddress.IPv4Network(f"{primary_ip}/24", strict=False)
        subnets.add(str(network))
        db_log(f"Sous-réseau principal : {network} (IP locale : {primary_ip})", "info")

    try:
        is_windows = platform.system().lower() == "windows"
        if is_windows:
            output = subprocess.check_output(["ipconfig"], encoding="cp850", errors="ignore")
            for match in re.finditer(r"IPv4[^:]*:\s*([\d\.]+)", output, re.IGNORECASE):
                ip_str = match.group(1).strip()
                try:
                    ip = ipaddress.IPv4Address(ip_str)
                    if ip.is_private and not ip.is_loopback:
                        net = ipaddress.IPv4Network(f"{ip_str}/24", strict=False)
                        if str(net) not in subnets:
                            subnets.add(str(net))
                            db_log(f"Interface supplémentaire : {net}", "info")
                except ValueError:
                    pass
        else:
            output = subprocess.check_output(["ip", "addr", "show"], encoding="utf-8", errors="ignore")
            for match in re.finditer(r"inet\s+([\d\.]+)/(\d+)", output):
                ip_str, prefix = match.group(1), int(match.group(2))
                try:
                    ip = ipaddress.IPv4Address(ip_str)
                    if ip.is_private and not ip.is_loopback:
                        net = ipaddress.IPv4Network(f"{ip_str}/{prefix}", strict=False)
                        if str(net) not in subnets:
                            subnets.add(str(net))
                except ValueError:
                    pass
    except Exception as e:
        db_log(f"Erreur détection interfaces : {e}", "warning")

    if not subnets:
        db_log("Aucun sous-réseau détecté, fallback 192.168.1.0/24", "warning")
        return ["192.168.1.0/24"]
    return list(subnets)


def _ping_sweep_windows(subnet: str, timeout_ms: int = 300) -> list:
    """Ping sweep parallèle pour peupler le cache ARP Windows."""
    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
        hosts = [str(ip) for ip in network.hosts()]

        def _ping_one(ip_str):
            r = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout_ms), ip_str],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return ip_str if r.returncode == 0 else None

        alive = []
        with ThreadPoolExecutor(max_workers=64) as executor:
            for result in as_completed({executor.submit(_ping_one, ip): ip for ip in hosts}):
                if result.result():
                    alive.append(result.result())
        return alive
    except Exception as e:
        db_log(f"Erreur ping sweep ({subnet}): {e}", "warning")
        return []


def _scan_network() -> list:
    """
    Scan du réseau local. Retourne une liste de dicts {ip, mac, hostname}.
    - Windows : ping sweep parallèle → lecture table ARP
    - Linux/RPi : broadcast ARP Scapy
    """
    subnets = _get_local_subnets()
    discovered = {}
    is_windows = platform.system().lower() == "windows"

    for subnet in subnets:
        db_log(f"Scan de {subnet}...", "info")

        if is_windows or not SCAPY_AVAILABLE:
            try:
                alive_ips = _ping_sweep_windows(subnet)
                db_log(f"{len(alive_ips)} hôte(s) ont répondu au ping sur {subnet}", "info")
                output = subprocess.check_output(["arp", "-a"], encoding="cp850", errors="ignore")
                pattern = re.compile(
                    r"^\s*([\d\.]+)\s+([0-9a-fA-F\-]+)\s+(dynamic|dynamique)",
                    re.IGNORECASE | re.MULTILINE
                )
                subnet_net = ipaddress.IPv4Network(subnet, strict=False)
                for ip, mac, _ in pattern.findall(output):
                    try:
                        ip_obj = ipaddress.IPv4Address(ip)
                    except ValueError:
                        continue
                    if ip_obj not in subnet_net or ip.endswith(".255") or ip_obj.is_multicast:
                        continue
                    if ip not in discovered:
                        discovered[ip] = {"ip": ip, "mac": mac.replace("-", ":").lower(), "hostname": "unknown"}
            except Exception as e:
                db_log(f"Erreur scan ARP Windows ({subnet}): {e}", "error")
        else:
            try:
                answered = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet), timeout=3, verbose=False)[0]
                for _, received in answered:
                    ip, mac = received.psrc, received.hwsrc
                    if ip not in discovered:
                        discovered[ip] = {"ip": ip, "mac": mac, "hostname": "unknown"}
            except PermissionError:
                db_log("Permission refusée pour scapy. Lancez avec sudo.", "error")
            except Exception as e:
                db_log(f"Erreur scan Scapy ({subnet}): {e}", "error")

    result = list(discovered.values())

    def _resolve(host_dict):
        host_dict["hostname"] = _resolve_hostname(host_dict["ip"], host_dict["mac"])

    with ThreadPoolExecutor(max_workers=32) as executor:
        for _ in as_completed([executor.submit(_resolve, h) for h in result]):
            pass

    db_log(f"Scan terminé : {len(result)} hôte(s) découvert(s).", "info")
    return result


def _update_discovered_hosts(discovered: list):
    """Met à jour la base de données avec les hôtes détectés."""
    db = SessionLocal()
    try:
        for host in discovered:
            existing = db.query(DiscoveredHost).filter_by(ip=host["ip"]).first()
            if existing:
                existing.last_seen = datetime.utcnow()
                existing.status = "up"
                existing.mac = host["mac"]
                if host["hostname"] != "unknown" or existing.hostname == "unknown":
                    existing.hostname = host["hostname"]
            else:
                db.add(DiscoveredHost(ip=host["ip"], mac=host["mac"], hostname=host["hostname"], status="up"))
                db_log(f"Nouvelle machine : {host['ip']} ({host['hostname']})", "info")

        discovered_ips = {h["ip"] for h in discovered}
        for host in db.query(DiscoveredHost).all():
            if host.ip not in discovered_ips and host.status == "up":
                host.status = "down"
                db_log(f"Machine inactive : {host.ip}", "warning")

        db.commit()
    except Exception as e:
        db_log(f"Erreur mise à jour hôtes: {e}", "error")
    finally:
        db.close()


def run_network_scan():
    """Point d'entrée du scan planifié (appelé toutes les 30 secondes)."""
    _update_discovered_hosts(_scan_network())


# ============================================================================
# 3. CAPTEUR DHT22 (température / humidité)
# ============================================================================

def read_sensor_data():
    """Lit température + humidité et persiste en BDD (simulation ou GPIO réel)."""
    if SIMULATION_MODE:
        temp = round(random.uniform(20.0, 35.0), 1)
        humidity = round(random.uniform(30.0, 70.0), 1)
    else:
        db_log("Lecture physique non implémentée, valeurs par défaut.", "info")
        temp, humidity = 22.0, 50.0

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


# ============================================================================
# 4. COLLECTE SNMP
# ============================================================================

def _get_device_status(ip: str, community: str, oid: str) -> str:
    """Interroge un équipement SNMP et retourne 'up' ou 'down'."""
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
        errorIndication, errorStatus, _, _ = next(iterator)
        return "down" if (errorIndication or errorStatus) else "up"
    except Exception as e:
        db_log(f"SNMP error pour {ip}: {e}", "warning")
        return "down"


def collect_snmp_data():
    """Interroge tous les équipements SNMP configurés et persiste leurs statuts."""
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
                db_log(f"Équipement {device['name']} ({device['ip']}) injoignable", "warning")
        db.commit()
    except Exception as e:
        db_log(f"Erreur collecte SNMP: {e}", "error")
    finally:
        db.close()
