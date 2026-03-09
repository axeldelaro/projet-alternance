# 🚀 Smart Monitoring RRG — Guide de Démarrage

---

## Prérequis communs

| Outil | Version minimale |
|-------|-----------------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |
| Git | n'importe laquelle |

---

## 🪟 Démarrage sur Windows (développement avec VS Code)

### 1. Cloner le projet

```bash
git clone https://github.com/axeldelaro/projet-alternance.git
cd projet-alternance/smart-monitoring-rrg
```

### 2. Configurer le backend

```bash
cd backend

# Créer un environnement virtuel Python
python -m venv venv

# Activer l'environnement (PowerShell)
.\venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r requirements.txt
```

> **Note PowerShell** : si vous obtenez une erreur `scripts désactivés`, exécutez d'abord :
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Vérifier la configuration

Ouvrir `backend/config.yaml` et s'assurer que :
```yaml
simulation_mode: true   # ← obligatoire sur Windows (pas de vrai capteur)
threshold_temp: 25.0
```

### 4. Lancer le backend

```bash
# Depuis le dossier backend/, avec le venv activé
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

✅ L'API est disponible sur `http://localhost:8000`  
📖 Documentation Swagger : `http://localhost:8000/docs`

### 5. Configurer le frontend

```bash
# Dans un nouveau terminal, depuis la racine du projet
cd frontend
npm install
```

### 6. Lancer le frontend

```bash
npm run dev
```

✅ Le dashboard est disponible sur `http://localhost:5173`

---

### 🖥️ Ouvrir dans VS Code

```bash
# Depuis la racine du projet
code .
```

**Extensions recommandées :**
- Python (Microsoft)
- Pylance
- ES7+ React/Redux/React-Native snippets
- Tailwind CSS IntelliSense
- GitLens

**Terminals recommandés dans VS Code :**
- Terminal 1 : backend (`backend/` → venv activé → `uvicorn main:app --reload`)
- Terminal 2 : frontend (`frontend/` → `npm run dev`)

---

## 🍓 Démarrage sur Raspberry Pi (serveur de production)

### Matériel requis

- Raspberry Pi 3B+ ou 4 (recommandé)
- Carte microSD 16 Go minimum (Classe 10)
- Raspberry Pi OS Lite 64-bit (ou Desktop)
- Capteur DHT22 + résistance pull-up 10 kΩ
- Connexion réseau (Ethernet recommandé pour la stabilité)

### Câblage du capteur DHT22

```
Raspberry Pi          DHT22
─────────────         ─────────
Pin 1  (3.3V) ──┬──── VCC (+)
                │
               10kΩ  ← résistance pull-up obligatoire
                │
Pin 7  (GPIO4) ─┴──── DATA
Pin 6  (GND)  ─────── GND (-)
```

### 1. Préparer le Raspberry Pi

```bash
# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Installer Python 3.11+ et pip
sudo apt install -y python3 python3-pip python3-venv git

# Installer Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Activer l'interface I2C/1-Wire (pour le DHT22)
sudo raspi-config
# → Interface Options → 1-Wire → Activé
```

### 2. Cloner le projet

```bash
git clone https://github.com/axeldelaro/projet-alternance.git
cd projet-alternance/smart-monitoring-rrg
```

### 3. Configurer le backend

```bash
cd backend

# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer toutes les dépendances (incluant RPi.GPIO et gpiozero)
pip install -r requirements.txt

# Installer adafruit-dht pour le capteur DHT22
pip install adafruit-circuitpython-dht
```

### 4. Adapter la configuration

Modifier `backend/config.yaml` pour la production :

```yaml
simulation_mode: false      # ← IMPORTANT : désactiver la simulation
sensor:
  type: dht22
  gpio_pin: 4               # Pin GPIO du câblage DHT22
threshold_temp: 28.0        # Seuil d'alerte (adapter à l'environnement)
snmp_community: "public"
devices:
  - name: "Switch Principal"
    ip: "192.168.1.1"
    oid_status: "1.3.6.1.2.1.1.1.0"
```

### 5. Lancer le backend (avec droits réseau pour le scan ARP)

```bash
# Le scan ARP/Scapy nécessite les droits sudo sur Linux
sudo bash -c "source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000"
```

### 6. Builder et servir le frontend

```bash
cd ../frontend
npm install
npm run build

# Les fichiers statiques sont dans frontend/dist/
# Les servir via le backend ou un serveur simple :
npx serve dist -p 3000
```

✅ Dashboard accessible sur `http://<IP-DU-PI>:3000` depuis n'importe quelle machine du réseau.

---

### 🔄 Lancement automatique au démarrage (systemd)

Créer un service pour que le backend démarre automatiquement :

```bash
sudo nano /etc/systemd/system/smart-monitoring.service
```

```ini
[Unit]
Description=Smart Monitoring RRG Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/projet-alternance/smart-monitoring-rrg/backend
ExecStart=/home/pi/projet-alternance/smart-monitoring-rrg/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Activer et démarrer le service
sudo systemctl enable smart-monitoring
sudo systemctl start smart-monitoring

# Vérifier le statut
sudo systemctl status smart-monitoring

# Voir les logs en direct
sudo journalctl -fu smart-monitoring
```

---

## ⚙️ Variables d'environnement (optionnelles)

| Variable | Rôle | Valeur par défaut |
|----------|------|-------------------|
| `VITE_API_URL` | URL de l'API backend (frontend) | `window.location.origin:8000` |

Exemple pour pointer le frontend vers le Pi :
```bash
# Dans frontend/.env
VITE_API_URL=http://192.168.1.50:8000
```

---

## 🐛 Dépannage rapide

| Problème | Solution |
|----------|----------|
| `uvicorn: command not found` | Activer le venv : `source venv/bin/activate` |
| Erreur CORS sur le frontend | Vérifier que le backend tourne sur le port 8000 |
| Scan réseau retourne 0 hôtes | Sur Linux : relancer avec `sudo` |
| DHT22 retourne `None` | Vérifier le câblage et la résistance 10kΩ |
| `RPi.GPIO not found` | Vérifier que `simulation_mode: false` uniquement sur le Pi |
| Port 8000 déjà utilisé | `lsof -i :8000` puis `kill <PID>` |
| `npm run dev` ne démarre pas | `cd frontend && rm -rf node_modules && npm install` |
