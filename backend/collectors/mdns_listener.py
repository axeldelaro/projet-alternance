"""
Listener mDNS passif.
Écoute les annonces mDNS sur le réseau local et mémorise les noms d'hôtes
associés aux IPs. Compatible iOS (Bonjour) et Android (NSD).
"""
import threading
import socket
from db import db_log

try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

# Cache global : ip -> nom d'hôte mDNS résolu
_mdns_cache: dict[str, str] = {}
_cache_lock = threading.Lock()

# Services mDNS courants diffusés par les appareils mobiles
SERVICES_TO_BROWSE = [
    "_device-info._tcp.local.",   # iOS (iPhone, iPad)
    "_http._tcp.local.",           # Appareils généralistes
    "_googlecast._tcp.local.",     # Chromecast / Android TV
    "_androidtvremote2._tcp.local.", # Android TV
    "_companion-link._tcp.local.", # Apple Watch / Continuity
    "_rdlink._tcp.local.",         # Apple
]


class _MdnsListener(ServiceListener):
    """Reçoit les événements de découverte mDNS et met à jour le cache."""

    def add_service(self, zc: "Zeroconf", type_: str, name: str) -> None:
        try:
            info = zc.get_service_info(type_, name, timeout=1000)
            if not info:
                return
            for addr_bytes in info.addresses:
                ip = socket.inet_ntoa(addr_bytes)
                # Le nom du service sans le suffix de type (ex: "iPhone-de-Axel._device-info._tcp.local." → "iPhone-de-Axel")
                friendly = name.replace(f".{type_}", "").replace("._device-info._tcp.local.", "").strip(". ")
                if friendly and ip:
                    with _cache_lock:
                        if ip not in _mdns_cache:
                            _mdns_cache[ip] = friendly
                            db_log(f"mDNS : {ip} → {friendly}", "info")
        except Exception:
            pass

    def remove_service(self, zc, type_, name):
        pass

    def update_service(self, zc, type_, name):
        self.add_service(zc, type_, name)


# Instance unique du listener mDNS
_zeroconf_instance: "Zeroconf | None" = None
_browsers: list = []


def start_mdns_listener():
    """Démarre le listener mDNS en arrière-plan. Appelé une seule fois au démarrage."""
    global _zeroconf_instance, _browsers

    if not ZEROCONF_AVAILABLE:
        db_log("zeroconf non disponible — mDNS désactivé. Installez : pip install zeroconf", "warning")
        return

    try:
        _zeroconf_instance = Zeroconf()
        listener = _MdnsListener()
        for service in SERVICES_TO_BROWSE:
            _browsers.append(ServiceBrowser(_zeroconf_instance, service, listener))
        db_log("Listener mDNS démarré — écoute des appareils Bonjour/NSD.", "info")
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


def get_mdns_name(ip: str) -> str | None:
    """Retourne le nom mDNS connu pour une IP, ou None."""
    with _cache_lock:
        return _mdns_cache.get(ip)
