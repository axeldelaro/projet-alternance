"""
Module de découverte automatique du réseau.
Utilise ARP (scapy) pour scanner le sous-réseau local du Raspberry Pi
et détecte tout nouvel équipement qui s'y connecte.
"""
import subprocess
import socket
import ipaddress
from database import SessionLocal
from models import DeviceStatus, DiscoveredHost
from utils.logger import db_log
from datetime import datetime

try:
    from scapy.all import ARP, Ether, srp
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False
    db_log("scapy non disponible, scan ARP désactivé. Installez-le avec : pip install scapy", "warning")


def get_local_subnet() -> str:
    """
    Détecte automatiquement le sous-réseau local du Raspberry Pi.
    Exemple : retourne "192.168.1.0/24"
    """
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        # Construire le /24 correspondant (ex: 192.168.1.42 → 192.168.1.0/24)
        network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
        return str(network)
    except Exception as e:
        db_log(f"Impossible de détecter le sous-réseau: {e}", "warning")
        return "192.168.1.0/24"  # Valeur par défaut


def ping_host(ip: str, timeout: int = 1) -> bool:
    """
    Effectue un simple ping ICMP vers une IP.
    Fonctionne sur Linux (Raspberry Pi) avec la commande système 'ping'.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result.returncode == 0
    except Exception:
        return False


def scan_network() -> list:
    """
    Scan ARP du sous-réseau local.
    Retourne la liste des équipements découverts : [{"ip": ..., "mac": ..., "hostname": ...}]
    """
    subnet = get_local_subnet()
    discovered = []

    if not SCAPY_AVAILABLE:
        db_log("Scan ARP ignoré (scapy absent)", "warning")
        return []

    try:
        db_log(f"Démarrage du scan réseau sur {subnet}...", "info")

        # Paquet ARP broadcast
        arp_request = ARP(pdst=subnet)
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast / arp_request

        # Timeout de 3 secondes pour le scan complet
        answered_list = srp(arp_request_broadcast, timeout=3, verbose=False)[0]

        for sent, received in answered_list:
            ip = received.psrc
            mac = received.hwsrc

            # Tentative de résolution DNS inverse (hostname)
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except socket.herror:
                hostname = "unknown"

            discovered.append({
                "ip": ip,
                "mac": mac,
                "hostname": hostname
            })

    except PermissionError:
        db_log("Permission refusée pour le scan ARP. Lancez le serveur avec sudo sur le Raspberry Pi.", "error")
    except Exception as e:
        db_log(f"Erreur lors du scan réseau: {e}", "error")

    return discovered


def update_discovered_hosts(discovered: list):
    """
    Insère ou met à jour les hôtes découverts dans la BDD.
    Un hôte existant est simplement mis à jour (last_seen + statut).
    Un nouvel hôte est inséré avec un log d'info.
    """
    db = SessionLocal()
    try:
        for host in discovered:
            existing = db.query(DiscoveredHost).filter_by(ip=host["ip"]).first()
            if existing:
                # Mettre à jour le dernier vu et le statut
                existing.last_seen = datetime.utcnow()
                existing.status = "up"
                existing.mac = host["mac"]
            else:
                # Nouvel équipement détecté sur le réseau
                new_host = DiscoveredHost(
                    ip=host["ip"],
                    mac=host["mac"],
                    hostname=host["hostname"],
                    status="up"
                )
                db.add(new_host)
                db_log(f"Nouvelle machine détectée : {host['ip']} ({host['hostname']}) - MAC: {host['mac']}", "info")

        # Marquer comme "down" les hôtes qui ne sont plus visibles
        all_hosts = db.query(DiscoveredHost).all()
        discovered_ips = {h["ip"] for h in discovered}
        for host in all_hosts:
            if host.ip not in discovered_ips:
                if host.status == "up":
                    host.status = "down"
                    db_log(f"Machine déconnectée : {host.ip} ({host.hostname})", "warning")

        db.commit()
    except Exception as e:
        db_log(f"Erreur mise à jour hôtes découverts: {e}", "error")
    finally:
        db.close()


def run_network_scan():
    """Point d'entrée principal : scan + mise à jour BDD."""
    discovered = scan_network()
    if discovered:
        db_log(f"Scan réseau terminé : {len(discovered)} équipement(s) détecté(s)", "info")
    update_discovered_hosts(discovered)
