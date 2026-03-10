# Smart Monitoring RRG — Guide de démarrage

## Prérequis

| Outil | Version |
|-------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

---

## Structure du projet

```
smart-monitoring-rrg/
├── backend/
│   ├── main.py          # API FastAPI + toutes les routes + scheduler
│   ├── db.py            # Base de données SQLite, modèles ORM, schémas Pydantic
│   ├── collectors.py    # Scan réseau, capteur DHT22, SNMP, alertes, mDNS
│   ├── config.yaml      # Configuration (seuils, équipements SNMP, mode)
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── App.jsx      # Interface React complète (composants + point d'entrée)
        └── index.css    # Styles CSS
```

---

## Démarrage sur Windows (développement)

### 1. Backend

```powershell
cd backend

# Créer et activer le venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# Si erreur "scripts désactivés" :
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Installer les dépendances
pip install -r requirements.txt

# Lancer le serveur (port 8000)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> API disponible sur `http://localhost:8000`  
> Documentation Swagger : `http://localhost:8000/docs`

### 2. Frontend

```powershell
# Dans un nouveau terminal
cd frontend
npm install
npm run dev
```

> Dashboard disponible sur `http://localhost:5173`

---

## Démarrage sur Raspberry Pi (production)

### Matériel requis

- Raspberry Pi 3B+ ou 4
- Capteur DHT22 + résistance pull-up 10 kΩ
- Câblage :

```
Pi Pin 1  (3.3V) ──┬──── VCC
                  10kΩ
Pi Pin 7  (GPIO4) ─┴──── DATA
Pi Pin 6  (GND)  ─────── GND
```

### Installation

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv nodejs git

cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install adafruit-circuitpython-dht
```

### Configuration (`backend/config.yaml`)

```yaml
simulation_mode: false   # true sur Windows, false sur Pi
sensor:
  gpio_pin: 4
threshold_temp: 28.0
threshold_humidity_low: 20.0
threshold_humidity_high: 80.0
snmp_community: "public"
devices:
  - name: "Switch"
    ip: "192.168.1.1"
    oid_status: "1.3.6.1.2.1.1.1.0"
```

### Lancer le backend (scan ARP nécessite sudo sur Linux)

```bash
sudo bash -c "source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000"
```

### Lancement automatique (systemd)

```bash
sudo nano /etc/systemd/system/smart-monitoring.service
```

```ini
[Unit]
Description=Smart Monitoring RRG
After=network.target

[Service]
User=root
WorkingDirectory=/home/pi/smart-monitoring-rrg/backend
ExecStart=/home/pi/smart-monitoring-rrg/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable smart-monitoring
sudo systemctl start smart-monitoring
```

---

## Fonctionnalités

| Fonctionnalité | Description |
|---------------|-------------|
| Scan réseau automatique | Ping sweep + lecture ARP toutes les 30 secondes |
| Détection changement réseau | Si le sous-réseau change, les anciens hôtes sont supprimés |
| Résolution de noms | DNS inverse, NetBIOS (Windows), mDNS (Bonjour), fabricant OUI |
| Capteur DHT22 | Simulation sur Windows, lecture GPIO physique sur Raspberry Pi |
| Alertes seuils | Température et humidité avec anti-flood (cooldown configurable) |
| SNMP | Monitoring d'équipements réseau configurés dans `config.yaml` |
| Export logs | Bouton dans l'interface pour télécharger les logs en `.txt` |
| Ping manuel | Bouton "ping" par hôte ou "Ping All" pour tous en parallèle |

---

## Routes API

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/api/sensors/latest` | Dernière mesure temp/humidité |
| GET | `/api/sensors/history?limit=N` | Historique des mesures |
| GET | `/api/logs?limit=N` | Journal d'événements |
| GET | `/api/hosts` | Liste des hôtes découverts |
| POST | `/api/hosts/{ip}/ping` | Ping d'un hôte spécifique |
| POST | `/api/hosts/ping-all` | Ping de tous les hôtes en parallèle |

---

## Dépannage

| Problème | Solution |
|----------|----------|
| `uvicorn: command not found` | Activer le venv : `.\venv\Scripts\Activate.ps1` |
| Erreur CORS | Vérifier que le backend tourne sur le port 8000 |
| 0 hôtes détectés sur Linux | Relancer avec `sudo` |
| DHT22 retourne None | Vérifier câblage et résistance 10kΩ |
| `npm run dev` ne démarre pas | `cd frontend && rm -rf node_modules && npm install` |
| Port 8000 occupé | `netstat -ano \| findstr :8000` puis arrêter le process |
