import React, { useState, useEffect } from 'react';
import { Activity } from 'lucide-react';
import TemperatureCard from './components/TemperatureCard';
import HumidityCard from './components/HumidityCard';
import NetworkTable from './components/NetworkTable';
import LogsPanel from './components/LogsPanel';
import AlertBanner from './components/AlertBanner';
import HostsTable from './components/HostsTable';
import { fetchLatestSensors, fetchDevices, fetchLogs, fetchHosts } from './services/api';

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
      console.error("Erreur lors du rafraichissement:", err);
    }
  };

  useEffect(() => {
    loadData();
    const intervalId = setInterval(loadData, REFRESH_INTERVAL);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-10 space-y-8">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-indigo-600 text-white rounded-xl shadow-lg shadow-indigo-200">
            <Activity size={32} />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">Supervision RRG</h1>
            <p className="text-slate-500 font-medium mt-1">Dashboard Andon Centralisé</p>
          </div>
        </div>
        {lastUpdate && (
          <div className="flex items-center gap-2 bg-white px-4 py-2 rounded-full shadow-sm border border-slate-100 text-sm font-medium text-slate-500">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            Dernière sync : {lastUpdate.toLocaleTimeString('fr-FR')}
          </div>
        )}
      </header>

      {/* Alerte température */}
      <AlertBanner temperature={sensors.temperature} threshold={25.0} />

      <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Colonne gauche : Capteurs + Logs */}
        <div className="lg:col-span-1 space-y-8 flex flex-col">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-6">
            <TemperatureCard temperature={sensors.temperature} threshold={25.0} />
            <HumidityCard humidity={sensors.humidity} />
          </div>
          <div className="flex-1 min-h-[300px]">
            <LogsPanel logs={logs} />
          </div>
        </div>

        {/* Colonne droite : Équipements SNMP configurés */}
        <div className="lg:col-span-2">
          <NetworkTable devices={devices} />
        </div>
      </main>

      {/* Tableau pleine largeur : Machines découvertes automatiquement par scan ARP */}
      <section>
        <HostsTable hosts={hosts} onRefresh={loadData} />
      </section>
    </div>
  );
}
