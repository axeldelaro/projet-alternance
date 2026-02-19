const API_BASE = "http://localhost:8000/api";

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

export const fetchLogs = async () => {
    const res = await fetch(`${API_BASE}/logs`);
    if (!res.ok) throw new Error("Erreur logs");
    return res.json();
};
