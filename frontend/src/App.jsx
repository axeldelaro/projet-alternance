import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';

const API = (import.meta.env.VITE_API_URL ?? window.location.origin.replace(/:5173/, ':8000')) + "/api";
const get = url => fetch(url).then(r => r.ok ? r.json() : Promise.reject());
// Force l'interprétation UTC : ajoute 'Z' si le timestamp n'a pas d'info de fuseau
const utcDate = s => new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z');

function AlertBanner({ temp }) {
    if (temp <= 25) return null;
    return <div className="alert-banner">Alerte temperature : {temp}°C (seuil 25°C)</div>;
}

function SensorCard({ label, value, unit }) {
    return (
        <div className="sensor-card">
            <div className="sensor-card-label">{label}</div>
            <div className="sensor-card-value">{value}<span className="sensor-card-unit"> {unit}</span></div>
        </div>
    );
}

function HostsTable({ hosts, onRefresh }) {
    const [pinging, setPinging] = useState({});
    const [pingAll, setPingAll] = useState(false);
    const [pingResult, setPingResult] = useState(null);
    const [clearing, setClearing] = useState(false);

    const doPing = async (ip) => {
        setPinging(p => ({ ...p, [ip]: true }));
        try { await fetch(`${API}/hosts/${ip}/ping`, { method: 'POST' }); onRefresh?.(); }
        catch (e) {}
        finally { setPinging(p => ({ ...p, [ip]: false })); }
    };

    const doPingAll = async () => {
        setPingAll(true); setPingResult(null);
        try { const r = await fetch(`${API}/hosts/ping-all`, { method: 'POST' }); setPingResult(await r.json()); onRefresh?.(); }
        catch (e) { setPingResult({ error: true }); }
        finally { setPingAll(false); }
    };

    const exportLogs = async () => {
        const logs = await get(`${API}/logs?limit=1000`);
        const txt = logs.map(l => `${utcDate(l.timestamp).toLocaleString('fr-FR')} [${l.level.toUpperCase()}] ${l.message}`).join('\n');
        const a = Object.assign(document.createElement('a'), {
            href: URL.createObjectURL(new Blob([txt], { type: 'text/plain' })),
            download: `logs-${new Date().toISOString().slice(0, 10)}.txt`
        });
        a.click();
    };

    const doClear = async () => {
        if (!confirm('Vider la liste des machines ? Un nouveau scan se lancera automatiquement.')) return;
        setClearing(true);
        try { await fetch(`${API}/hosts`, { method: 'DELETE' }); onRefresh?.(); }
        catch (e) {}
        finally { setClearing(false); }
    };

    const up = hosts.filter(h => h.status === 'up').length;
    return (
        <div className="panel hosts-table">
            <div className="panel-header">
                <span>Machines detectees — {hosts.length} &nbsp;
                    <span className="status-up">{up} up</span> / <span className="status-down">{hosts.length - up} down</span>
                </span>
                <span className="header-actions">
                    {pingResult && !pingResult.error && <span className="ping-result">{pingResult.up}/{pingResult.total} repondent</span>}
                    <button className="btn" onClick={exportLogs}>Exporter logs</button>
                    <button className="btn" onClick={doPingAll} disabled={pingAll || !hosts.length}>{pingAll ? 'en cours...' : 'Ping All'}</button>
                    <button className="btn btn-danger" onClick={doClear} disabled={clearing || !hosts.length}>{clearing ? '...' : 'Vider'}</button>
                </span>
            </div>
            <div className="hosts-scroll">
                <table className="text-mono">
                    <thead><tr><th>IP</th><th>MAC</th><th>Nom</th><th>Statut</th><th>Vu</th><th></th></tr></thead>
                    <tbody>
                        {hosts.map(h => (
                            <tr key={h.ip} className={h.status === 'down' ? 'row-down' : ''}>
                                <td><strong>{h.ip}</strong></td>
                                <td className="text-muted">{h.mac}</td>
                                <td>{h.hostname}</td>
                                <td><span className={`status-${h.status}`}>{h.status}</span></td>
                                <td className="text-muted">{utcDate(h.last_seen).toLocaleTimeString('fr-FR')}</td>
                                <td><button className="btn-sm" onClick={() => doPing(h.ip)} disabled={pinging[h.ip]}>{pinging[h.ip] ? '...' : 'ping'}</button></td>
                            </tr>
                        ))}
                        {!hosts.length && <tr className="empty-row"><td colSpan={6}>scan en cours...</td></tr>}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function App() {
    const [sensors, setSensors] = useState({ temperature: 0, humidity: 0 });
    const [hosts, setHosts]     = useState([]);
    const [lastUpdate, setLastUpdate] = useState(null);

    const load = async () => {
        try {
            const [s, h] = await Promise.all([get(`${API}/sensors/latest`), get(`${API}/hosts`)]);
            setSensors(s); setHosts(h); setLastUpdate(new Date());
        } catch (e) {}
    };

    useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, []);

    return (
        <div className="app">
            <header className="app-header">
                <div>
                    <span className="app-title">Supervision RRG</span>
                    <span className="app-sub">Dashboard de monitoring reseau</span>
                </div>
                <span className="app-time">{lastUpdate ? `maj : ${lastUpdate.toLocaleTimeString('fr-FR')}` : 'connexion...'}</span>
            </header>
            <div className="app-body">
                <div className="col-left">
                    <AlertBanner temp={sensors.temperature} />
                    <SensorCard label="Temperature" value={sensors.temperature} unit="°C" />
                    <SensorCard label="Humidite" value={sensors.humidity} unit="%" />
                </div>
                <div className="col-right">
                    <HostsTable hosts={hosts} onRefresh={load} />
                </div>
            </div>
        </div>
    );
}

ReactDOM.createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
