import random, subprocess, socket, ipaddress, platform, re, time, logging, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from db import SessionLocal, SensorData, DeviceStatus, DiscoveredHost, db_log, config

logger = logging.getLogger(__name__)

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
    from mac_vendor_lookup import MacLookup
    _mac_lookup = MacLookup(); MAC_LOOKUP_AVAILABLE = True
except ImportError:
    MAC_LOOKUP_AVAILABLE = False

SNMP_AVAILABLE = False
try:
    from pysnmp.hlapi import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
    SNMP_AVAILABLE = True
except ImportError:
    try:
        from pysnmp.hlapi.v1arch import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        SNMP_AVAILABLE = True
    except ImportError:
        pass

SIMULATION_MODE = config.get("simulation_mode", True)

# mDNS
_mdns_cache, _cache_lock = {}, threading.Lock()

class _MdnsListener(ServiceListener if ZEROCONF_AVAILABLE else object):
    def add_service(self, zc, type_, name):
        try:
            info = zc.get_service_info(type_, name, timeout=1000)
            if not info: return
            for b in info.addresses:
                ip, friendly = socket.inet_ntoa(b), name.replace(f".{type_}", "").strip(". ")
                if ip and friendly:
                    with _cache_lock:
                        _mdns_cache.setdefault(ip, friendly)
        except Exception: pass
    def remove_service(self, *a): pass
    def update_service(self, zc, t, n): self.add_service(zc, t, n)

_zc = None
def start_mdns_listener():
    global _zc
    if not ZEROCONF_AVAILABLE: return
    try:
        _zc = Zeroconf(); l = _MdnsListener()
        for s in ("_device-info._tcp.local.", "_http._tcp.local.", "_googlecast._tcp.local."):
            ServiceBrowser(_zc, s, l)
    except Exception: pass

def stop_mdns_listener():
    if _zc:
        try: _zc.close()
        except Exception: pass

# Réseau
IS_WIN = platform.system().lower() == "windows"

def ping_host(ip, timeout=1):
    try:
        args = ["ping", "-n", "1", "-w", str(timeout*1000), ip] if IS_WIN else ["ping", "-c", "1", "-W", str(timeout), ip]
        return subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except Exception: return False

def _get_subnets():
    subnets = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if not ip.startswith("127."): subnets.add(str(ipaddress.IPv4Network(f"{ip}/24", strict=False)))
    except Exception: pass
    try:
        out = subprocess.check_output(["ipconfig"] if IS_WIN else ["ip","addr","show"],
                                      encoding="cp850" if IS_WIN else "utf-8", errors="ignore")
        pat = r"IPv4[^:]*:\s*([\d\.]+)" if IS_WIN else r"inet\s+([\d\.]+)/(\d+)"
        for m in re.finditer(pat, out, re.IGNORECASE):
            try:
                a = ipaddress.IPv4Address(m.group(1).strip())
                if a.is_private and not a.is_loopback:
                    prefix = 24 if IS_WIN else int(m.group(2))
                    subnets.add(str(ipaddress.IPv4Network(f"{a}/{prefix}", strict=False)))
            except Exception: pass
    except Exception: pass
    return list(subnets) or ["192.168.1.0/24"]

def _resolve_hostname(ip, mac=""):
    try:
        n = socket.gethostbyaddr(ip)[0]
        if n and n != ip: return n
    except Exception: pass
    if IS_WIN:
        try:
            out = subprocess.check_output(["nbtstat","-A",ip], encoding="cp850", errors="ignore", timeout=1, stderr=subprocess.DEVNULL)
            m = re.search(r"^\s*([A-Za-z0-9_\-]+)\s+<00>\s+UNIQUE", out, re.MULTILINE)
            if m: return m.group(1).strip()
        except Exception: pass
    with _cache_lock:
        if ip in _mdns_cache: return _mdns_cache[ip]
    if mac and MAC_LOOKUP_AVAILABLE:
        try:
            if int(mac.replace(":","").replace("-","")[:2], 16) & 0x02: return "Mobile"
            return _mac_lookup.lookup(mac)
        except Exception: pass
    return "unknown"

def _ping_win(ip):
    return subprocess.run(["ping","-n","1","-w","300",ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

def _resolve(h):
    h["hostname"] = _resolve_hostname(h["ip"], h["mac"])

def _scan_network():
    subnets, discovered = _get_subnets(), {}
    for subnet in subnets:
        db_log(f"Scan {subnet}...", "info")
        if IS_WIN or not SCAPY_AVAILABLE:
            try:
                net = ipaddress.IPv4Network(subnet, strict=False)
                with ThreadPoolExecutor(max_workers=64) as ex:
                    list(as_completed({ex.submit(_ping_win, str(h)): h for h in net.hosts()}))
                out = subprocess.check_output(["arp","-a"], encoding="cp850", errors="ignore")
                for ip, mac, _ in re.findall(r"^\s*([\d\.]+)\s+([0-9a-fA-F\-]+)\s+(dynamic|dynamique)", out, re.IGNORECASE|re.MULTILINE):
                    try:
                        obj = ipaddress.IPv4Address(ip)
                        if obj in net and not ip.endswith(".255") and not obj.is_multicast:
                            discovered[ip] = {"ip": ip, "mac": mac.replace("-",":").lower(), "hostname": "unknown"}
                    except Exception: pass
            except Exception as e: db_log(f"Erreur scan ({subnet}): {e}", "error")
        else:
            try:
                for _, r in srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst=subnet), timeout=3, verbose=False)[0]:
                    discovered[r.psrc] = {"ip": r.psrc, "mac": r.hwsrc, "hostname": "unknown"}
            except Exception as e: db_log(f"Erreur scapy: {e}", "error")

    result = list(discovered.values())
    with ThreadPoolExecutor(max_workers=32) as ex:
        list(as_completed(ex.submit(_resolve, h) for h in result))
    db_log(f"Scan terminé : {len(result)} hôte(s).", "info")
    return result, set(subnets)

_last_subnets: set = set()

def run_network_scan():
    global _last_subnets
    discovered, subnets = _scan_network()
    db = SessionLocal()
    if _last_subnets and subnets != _last_subnets:
        db.query(DiscoveredHost).delete(); db.commit()
        db_log("Changement de réseau — hôtes réinitialisés.", "info")
    _last_subnets = subnets; db.close()

    db = SessionLocal()
    try:
        found = {h["ip"] for h in discovered}
        for h in discovered:
            ex = db.query(DiscoveredHost).filter_by(ip=h["ip"]).first()
            if ex:
                ex.last_seen, ex.status, ex.mac = datetime.utcnow(), "up", h["mac"]
                if h["hostname"] != "unknown" or ex.hostname == "unknown": ex.hostname = h["hostname"]
            else:
                db.add(DiscoveredHost(**h, status="up"))
                db_log(f"Nouvelle machine : {h['ip']}", "info")
        for host in db.query(DiscoveredHost).all():
            if host.ip not in found and host.status == "up": host.status = "down"
        db.commit()
    except Exception as e: db_log(f"Erreur BDD: {e}", "error")
    finally: db.close()

# Capteur
def _save_sensor(temp, humidity):
    db = SessionLocal()
    try: db.add(SensorData(temperature=temp, humidity=humidity)); db.commit()
    except Exception as e: db_log(f"Erreur capteur: {e}", "error")
    finally: db.close()

def read_sensor_data():
    _save_sensor(
        round(random.uniform(20.0, 35.0), 1) if SIMULATION_MODE else 22.0,
        round(random.uniform(30.0, 70.0), 1) if SIMULATION_MODE else 50.0
    )

# GPIO
_dht, _gpio_ok = None, False
GPIO_PIN = config.get("sensor", {}).get("gpio_pin", 4)

def _init_gpio():
    global _dht, _gpio_ok
    if _gpio_ok: return _dht is not None
    _gpio_ok = True
    if platform.system().lower() != "linux": return False
    try:
        import adafruit_dht, board
        _dht = adafruit_dht.DHT22({4:board.D4, 17:board.D17, 27:board.D27, 22:board.D22}.get(GPIO_PIN, board.D4), use_pulseio=False)
        return True
    except Exception: return False

def read_sensor_data_gpio():
    if not _init_gpio() or _dht is None: return
    for i in range(3):
        try:
            t, h = _dht.temperature, _dht.humidity
            if t is None or h is None: raise RuntimeError()
            _save_sensor(round(t, 1), round(h, 1)); return
        except Exception:
            if i < 2: time.sleep(0.5)
    db_log("DHT22 : lecture échouée.", "error")

# SNMP
def collect_snmp_data():
    if not SNMP_AVAILABLE: return
    community, db = config.get("snmp_community", "public"), SessionLocal()
    try:
        for d in config.get("devices", []):
            try:
                err, es, _, _ = next(getCmd(SnmpEngine(), CommunityData(community, mpModel=0),
                    UdpTransportTarget((d["ip"], 161), timeout=2, retries=1),
                    ContextData(), ObjectType(ObjectIdentity(d["oid_status"]))))
                status = "down" if (err or es) else "up"
            except Exception: status = "down"
            db.add(DeviceStatus(device_name=d["name"], status=status))
        db.commit()
    except Exception as e: db_log(f"Erreur SNMP: {e}", "error")
    finally: db.close()

# Alertes
_alert_times = {}

def _should_alert(key, cooldown=60):
    now = time.monotonic()
    if now - _alert_times.get(key, 0) >= cooldown:
        _alert_times[key] = now; return True
    return False

def run_all_checks():
    t_max = config.get("threshold_temp", 25.0)
    h_min, h_max = config.get("threshold_humidity_low", 20.0), config.get("threshold_humidity_high", 80.0)
    db = SessionLocal()
    try:
        s = db.query(SensorData).order_by(SensorData.timestamp.desc()).first()
        if s:
            if s.temperature > t_max and _should_alert("temp_high", 60): db_log(f"ALERTE TEMP : {s.temperature}°C > {t_max}°C", "warning")
            elif s.temperature <= t_max: _alert_times.pop("temp_high", None)
            if s.humidity < h_min and _should_alert("hum_low", 120): db_log(f"ALERTE HUMIDITE BASSE : {s.humidity}%", "warning")
            elif s.humidity > h_max and _should_alert("hum_high", 120): db_log(f"ALERTE HUMIDITE HAUTE : {s.humidity}%", "warning")
            else: _alert_times.pop("hum_low", None); _alert_times.pop("hum_high", None)
    finally: db.close()

    from sqlalchemy import func
    db = SessionLocal()
    try:
        sub = db.query(DeviceStatus.device_name, func.max(DeviceStatus.timestamp).label("m")).group_by(DeviceStatus.device_name).subquery()
        for d in db.query(DeviceStatus).join(sub, (DeviceStatus.device_name == sub.c.device_name) & (DeviceStatus.timestamp == sub.c.m)).all():
            if d.status == "down" and _should_alert(f"dev_{d.device_name}", 300): db_log(f"{d.device_name} injoignable", "error")
            elif d.status == "up": _alert_times.pop(f"dev_{d.device_name}", None)
    except Exception as e: logger.error(e)
    finally: db.close()
