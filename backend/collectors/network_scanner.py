"""
Module de découverte automatique du réseau.
Compatible Windows (native arp + ping sweep) et Linux (scapy).
"""
import subprocess
import socket
import ipaddress
import platform
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from db import SessionLocal, DiscoveredHost, db_log
from datetime import datetime

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

from collectors.mdns_listener import get_mdns_name


def _is_randomized_mac(mac: str) -> bool:
    """
    Détecte si une adresse MAC est localement administrée (randomisée).
    iOS 14+ et Android 10+ utilisent des MACs aléatoires par réseau WiFi.
    Indication : le 2e bit du 1er octet est à 1 (ex: 02, 06, 0a, 0e, 12...).
    """
    try:
        first_byte = int(mac.replace(":", "").replace("-", "")[:2], 16)
        return bool(first_byte & 0x02)  # bit "locally administered"
    except Exception:
        return False


def resolve_vendor(mac: str) -> str:
    """
    Retourne le fabricant à partir de l'OUI (3 premiers octets de la MAC).
    Si la MAC est randomisée (iOS/Android privacy), on le signale directement.
    """
    if not mac:
        return ""

    if _is_randomized_mac(mac):
        return "Mobile (MAC aléatoire)"   # iOS 14+ / Android 10+ par défaut

    if not MAC_LOOKUP_AVAILABLE:
        return ""
    try:
        return _mac_lookup.lookup(mac)
    except Exception:
        return ""


def resolve_hostname(ip: str, mac: str = "") -> str:
    """
    Résolution de nom en cascade :
    1. DNS inverse (PTR)        — réseau d'entreprise avec DNS local
    2. NetBIOS (nbtstat -A)     — PC Windows sur LAN / hotspot
    3. mDNS (cache Bonjour/NSD) — iOS, Android récent
    4. Fabricant OUI (MAC)      — tous appareils (ex: "Apple Inc.")
    5. Fallback "unknown"
    """
    # --- 1. DNS inverse ---
    try:
        name = socket.gethostbyaddr(ip)[0]
        if name and name != ip:
            return name
    except (socket.herror, socket.gaierror):
        pass

    # --- 2. NetBIOS (Windows uniquement) — timeout court pour ne pas bloquer ---
    if platform.system().lower() == "windows":
        try:
            output = subprocess.check_output(
                ["nbtstat", "-A", ip],
                encoding="cp850", errors="ignore",
                timeout=1,          # 1s max, pas 3s
                stderr=subprocess.DEVNULL
            )
            match = re.search(r"^\s*([A-Za-z0-9_\-]+)\s+<00>\s+UNIQUE", output, re.MULTILINE)
            if match:
                return match.group(1).strip()
        except Exception:
            pass

    # --- 3. mDNS (cache Bonjour / NSD) ---
    mdns_name = get_mdns_name(ip)
    if mdns_name:
        return mdns_name

    # --- 4. Fabricant via OUI (MAC address) ---
    vendor = resolve_vendor(mac)
    if vendor:
        return vendor

    return "unknown"


def get_local_ip() -> str:
    """
    Retourne l'IP locale de l'interface réseau active (celle qui accède à Internet/LAN).
    Utilise une connexion UDP fictive vers 8.8.8.8 — aucun paquet n'est envoyé,
    mais l'OS choisit automatiquement la bonne interface.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None


def get_local_subnets() -> list:
    """
    Détecte automatiquement tous les sous-réseaux locaux actifs.
    Retourne une liste de chaînes de type '192.168.1.0/24'.

    Méthode 1 : UDP socket trick (interface principale)
    Méthode 2 : ipconfig (Windows) / ip addr (Linux) pour interfaces supplémentaires
    """
    subnets = set()

    # --- Méthode principale : UDP socket trick (la plus fiable) ---
    primary_ip = get_local_ip()
    if primary_ip and not primary_ip.startswith("127."):
        network = ipaddress.IPv4Network(f"{primary_ip}/24", strict=False)
        subnets.add(str(network))
        db_log(f"Sous-réseau principal détecté : {network} (IP locale : {primary_ip})", "info")

    # --- Méthode secondaire : parsing ipconfig / ip addr pour interfaces multiples ---
    try:
        is_windows = platform.system().lower() == "windows"
        if is_windows:
            output = subprocess.check_output(
                ["ipconfig"], encoding="cp850", errors="ignore"
            )
            # Chercher toutes les IPv4 valides (ex: "Adresse IPv4. . . : 192.168.1.10")
            for match in re.finditer(r"IPv4[^:]*:\s*([\d\.]+)", output, re.IGNORECASE):
                ip_str = match.group(1).strip()
                try:
                    ip = ipaddress.IPv4Address(ip_str)
                    if ip.is_private and not ip.is_loopback:
                        net = ipaddress.IPv4Network(f"{ip_str}/24", strict=False)
                        if str(net) not in subnets:
                            subnets.add(str(net))
                            db_log(f"Interface supplémentaire détectée : {net}", "info")
                except ValueError:
                    pass
        else:
            output = subprocess.check_output(
                ["ip", "addr", "show"], encoding="utf-8", errors="ignore"
            )
            for match in re.finditer(r"inet\s+([\d\.]+)/(\d+)", output):
                ip_str = match.group(1)
                prefix = int(match.group(2))
                try:
                    ip = ipaddress.IPv4Address(ip_str)
                    if ip.is_private and not ip.is_loopback:
                        net = ipaddress.IPv4Network(f"{ip_str}/{prefix}", strict=False)
                        if str(net) not in subnets:
                            subnets.add(str(net))
                            db_log(f"Interface supplémentaire détectée : {net}", "info")
                except ValueError:
                    pass
    except Exception as e:
        db_log(f"Erreur détection interfaces secondaires: {e}", "warning")

    if not subnets:
        db_log("Aucun sous-réseau détecté automatiquement, fallback sur 192.168.1.0/24", "warning")
        return ["192.168.1.0/24"]

    return list(subnets)


def ping_host(ip: str, timeout: int = 1) -> bool:
    """Effectue un ping ICMP natif adapté à Windows ou Linux."""
    try:
        if platform.system().lower() == "windows":
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout * 1000), ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", str(timeout), ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        return result.returncode == 0
    except Exception:
        return False


def _ping_sweep_windows(subnet: str, timeout_ms: int = 300) -> list:
    """
    Ping sweep parallèle sur le sous-réseau pour peupler la cache ARP Windows.
    Retourne la liste des IPs qui ont répondu.
    """
    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
        hosts = [str(ip) for ip in network.hosts()]
        alive = []

        def _ping_one(ip_str):
            result = subprocess.run(
                ["ping", "-n", "1", "-w", str(timeout_ms), ip_str],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return ip_str if result.returncode == 0 else None

        with ThreadPoolExecutor(max_workers=64) as executor:
            futures = {executor.submit(_ping_one, ip): ip for ip in hosts}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    alive.append(result)

        return alive
    except Exception as e:
        db_log(f"Erreur ping sweep ({subnet}): {e}", "warning")
        return []


def scan_network() -> list:
    """
    Scan automatique du réseau local.
    Détecte les sous-réseaux actifs sans configuration manuelle.
    - Windows : ping sweep parallèle → lecture ARP cache
    - Linux/RPi : Scapy ARP broadcast
    """
    subnets = get_local_subnets()
    discovered = {}  # ip → {ip, mac, hostname} — dict pour dédoublonner entre interfaces
    is_windows = platform.system().lower() == "windows"

    for subnet in subnets:
        db_log(f"Scan du réseau {subnet}...", "info")

        if is_windows or not SCAPY_AVAILABLE:
            # ====== MÉTHODE WINDOWS : Ping sweep + ARP cache ======
            try:
                # Étape 1 : ping sweep pour peupler la cache ARP
                alive_ips = _ping_sweep_windows(subnet)
                db_log(f"{len(alive_ips)} hôte(s) ont répondu au ping sur {subnet}", "info")

                # Étape 2 : lire la table ARP complète
                output = subprocess.check_output(
                    ["arp", "-a"], encoding="cp850", errors="ignore"
                )

                pattern = re.compile(
                    r"^\s*([\d\.]+)\s+([0-9a-fA-F\-]+)\s+(dynamic|dynamique)",
                    re.IGNORECASE | re.MULTILINE
                )
                matches = pattern.findall(output)

                subnet_net = ipaddress.IPv4Network(subnet, strict=False)

                for ip, mac, _ in matches:
                    # Filtrer les adresses de broadcast, multicast et hors-sous-réseau
                    try:
                        ip_obj = ipaddress.IPv4Address(ip)
                    except ValueError:
                        continue

                    if ip_obj not in subnet_net:
                        continue
                    if ip.endswith(".255") or ip_obj.is_multicast:
                        continue

                    mac_formatted = mac.replace("-", ":").lower()

                    if ip not in discovered:
                        discovered[ip] = {
                            "ip": ip,
                            "mac": mac_formatted,
                            "hostname": "unknown"  # Sera résolu en parallèle après
                        }

            except Exception as e:
                db_log(f"Erreur scan ARP Windows ({subnet}): {e}", "error")

        else:
            # ====== MÉTHODE LINUX / RPi : Scapy ARP broadcast ======
            try:
                arp_request = ARP(pdst=subnet)
                broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
                arp_request_broadcast = broadcast / arp_request
                answered_list = srp(arp_request_broadcast, timeout=3, verbose=False)[0]

                for sent, received in answered_list:
                    ip = received.psrc
                    mac = received.hwsrc

                    if ip not in discovered:
                        discovered[ip] = {
                            "ip": ip,
                            "mac": mac,
                            "hostname": "unknown"  # Sera résolu en parallèle après
                        }

            except PermissionError:
                db_log("Permission refusée pour scapy. Lancez avec sudo.", "error")
            except Exception as e:
                db_log(f"Erreur scan réseau Scapy ({subnet}): {e}", "error")

    result = list(discovered.values())

    # Résolution parallèle des hostnames pour ne pas bloquer le thread principal
    def _resolve_and_update(host_dict):
        host_dict["hostname"] = resolve_hostname(host_dict["ip"], host_dict["mac"])

    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = [executor.submit(_resolve_and_update, h) for h in result]
        for f in as_completed(futures):
            pass

    db_log(f"Scan terminé : {len(result)} hôte(s) découvert(s) au total.", "info")
    return result


def update_discovered_hosts(discovered: list):
    """Met à jour les hôtes détectés dans la base de données."""
    db = SessionLocal()
    try:
        for host in discovered:
            existing = db.query(DiscoveredHost).filter_by(ip=host["ip"]).first()
            if existing:
                existing.last_seen = datetime.utcnow()
                existing.status = "up"
                existing.mac = host["mac"]
                # Mettre à jour le hostname si :
                # - le nouveau nom est connu (pas "unknown"), OU
                # - l'actuel en base est encore "unknown" (on ne peut que s'améliorer)
                new_name = host["hostname"]
                if new_name != "unknown" or existing.hostname == "unknown":
                    existing.hostname = new_name
            else:
                new_host = DiscoveredHost(
                    ip=host["ip"],
                    mac=host["mac"],
                    hostname=host["hostname"],
                    status="up"
                )
                db.add(new_host)
                db_log(f"Nouvelle machine : {host['ip']} ({host['hostname']})", "info")

        # Marquer inactifs ceux absents du dernier scan
        all_hosts = db.query(DiscoveredHost).all()
        discovered_ips = {h["ip"] for h in discovered}
        for host in all_hosts:
            if host.ip not in discovered_ips and host.status == "up":
                host.status = "down"
                db_log(f"Machine inactive : {host.ip}", "warning")

        db.commit()
    except Exception as e:
        db_log(f"Erreur mise à jour hôtes: {e}", "error")
    finally:
        db.close()


def run_network_scan():
    """Point d'entrée du scan planifié."""
    discovered = scan_network()
    update_discovered_hosts(discovered)
