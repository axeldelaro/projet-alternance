# Smart Monitoring RRG

Supervision centralisee (Dashboard Andon) pour Retail Renault Group (RRG) Lyon.
Permet la remontee en temps reel de l'etat du reseau informatique (via SNMP) et des parametres environnementaux (temperature/humidite).

---

## Architecture et Fonctionnement

### Base de Donnees (SQLite)
Generee automatiquement dans `database/monitoring.db`. Contient 3 tables :
- `sensor_data` : historique des releves (temperature, humidite)
- `device_status` : statut UP/DOWN des equipements reseau
- `logs` : journal des evenements et alertes

### Configuration Materielle (Raspberry Pi & Capteur DHT22)
1. Brancher le capteur DHT22 : VCC sur 3.3V, GND sur GND, DATA sur GPIO 4 (Pin 7)
2. Passer `simulation_mode: false` dans `backend/config.yaml`

### Configuration Reseau (SNMP)
Activer SNMP sur les switchs/routeurs (ex Cisco IOS : `snmp-server community public RO`)
Ajouter les IPs dans `backend/config.yaml` sous la cle `devices`.

---

## Installation & Lancement

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Configuration (config.yaml)
- `simulation_mode` : true = donnees aleatoires, false = vrai capteur
- `snmp_community` : chaine SNMP de vos equipements (ex: "public")  
- `devices` : liste des IPs a surveiller
- `threshold_temp` : seuil d'alerte en degres Celsius
