import React, { useState, useEffect } from 'react';
import { TemperatureCard, HumidityCard, AlertBanner } from './components/SensorWidgets';
import NetworkTable from './components/NetworkTable';
import LogsPanel from './components/LogsPanel';
import HostsTable from './components/HostsTable';

// ---------------------------------------------------------------------------
// API — appels vers le backend FastAPI
// ---------------------------------------------------------------------------
const API_BASE = (import.meta.env.VITE_API_URL ?? window.location.origin.replace(/:5173/, ':8000')) + "/api";

const fetchLatestSensors = () => fetch(`${API_BASE}/sensors/latest`).then(r => { if (!r.ok) throw new Error("Erreur sensors"); return r.json(); });
const fetchDevices = () => fetch(`${API_BASE}/devices`).then(r => { if (!r.ok) throw new Error("Erreur devices"); return r.json(); });
const fetchLogs = () => fetch(`${API_BASE}/logs`).then(r => { if (!r.ok) throw new Error("Erreur logs"); return r.json(); });
const fetchHosts = () => fetch(`${API_BASE}/hosts`).then(r => { if (!r.ok) throw new Error("Erreur hosts"); return r.json(); });

// ---------------------------------------------------------------------------
// Application principale
// ---------------------------------------------------------------------------
export default function App() {
  const [sensors, setSensors] = useState({ temperature: 0, humidity: 0 });
  const [devices, setDevices] = useState([]);
  const [logs, setLogs] = useState([]);
  const [hosts, setHosts] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);

  const REFRESH_INTERVAL = 5000;

  const loadData = async () => {
    try {
      const [sensorData, deviceData, logData, hostData] = await Promise.all([
        fetchLatestSensors(),
        fetchDevices(),
        fetchLogs(),
        fetchHosts()
      ]);
      setSensors(sensorData);
      setDevices(deviceData);
      setLogs(logData);
      setHosts(hostData);
      setLastUpdate(new Date());
    } catch (err) {
      console.error("Erreur rafraîchissement:", err);
    }
  };

  useEffect(() => {
    loadData();
    const id = setInterval(loadData, REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-gray-50 font-mono">

      {/* ── Header ── */}
      <header className="shrink-0 border-b border-gray-200 bg-white px-5 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-base font-bold text-gray-800 tracking-tight">
            📡 Supervision RRG
          </h1>
          <p className="text-xs text-gray-400">Dashboard de supervision réseau</p>
        </div>
        <span className="text-xs text-gray-400">
          {lastUpdate
            ? <span>⟳ {lastUpdate.toLocaleTimeString('fr-FR')}</span>
            : <span className="italic">connexion...</span>
          }
        </span>
      </header>

      {/* ── Alerte ── */}
      <div className="shrink-0 px-4 pt-3">
        <AlertBanner temperature={sensors.temperature} threshold={25.0} />
      </div>

      {/* ── Corps principal ── */}
      <div className="flex-1 min-h-0 grid grid-cols-12 gap-3 p-3">

        {/* Colonne gauche */}
        <div className="col-span-3 flex flex-col gap-3 min-h-0">
          <TemperatureCard temperature={sensors.temperature} threshold={25.0} />
          <HumidityCard humidity={sensors.humidity} />
          <div className="flex-1 min-h-0">
            <LogsPanel logs={logs} />
          </div>
        </div>

        {/* Colonne droite */}
        <div className="col-span-9 flex flex-col gap-3 min-h-0">
          <div className="shrink-0">
            <NetworkTable devices={devices} />
          </div>
          <div className="flex-1 min-h-0">
            <HostsTable hosts={hosts} onRefresh={loadData} />
          </div>
        </div>

      </div>
    </div>
  );
}
