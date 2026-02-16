# Smart Monitoring RRG

Supervision centralisee (Dashboard Andon) pour Retail Renault Group (RRG) Lyon.

## Fonctionnalites
- Surveillance equipements reseau via SNMP
- Lecture temperature/humidite (GPIO ou simulation)
- Historisation SQLite
- API REST FastAPI
- Dashboard React en temps reel (refresh 5s)

## Lancement Backend
```bash
cd backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Lancement Frontend
```bash
cd frontend
npm install
npm run dev
```

## Configuration
Editer `backend/config.yaml` pour adapter les IPs, la communaute SNMP et le seuil de temperature.
