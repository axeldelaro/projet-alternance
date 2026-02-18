const API_BASE = "http://localhost:8000/api";

// Recupere la derniere mesure capteur
export const fetchLatestSensors = async () => {
    const res = await fetch(`${API_BASE}/sensors/latest`);
    if (!res.ok) throw new Error("Erreur sensors");
    return res.json();
};

export const fetchDevices = async () => {
    const res = await fetch(`${API_BASE}/devices`);
    if (!res.ok) throw new Error("Erreur devices");
    return res.json();
};

// TODO: fetchLogs
