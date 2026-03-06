import React, { useState } from 'react';

const API_BASE = (import.meta.env.VITE_API_URL ?? window.location.origin.replace(/:5173/, ':8000')) + "/api";

export default function HostsTable({ hosts, onRefresh }) {
    const [pinging, setPinging] = useState({});
    const [pingAll, setPingAll] = useState(false);
    const [pingAllResult, setPingAllResult] = useState(null);

    const handlePing = async (ip) => {
        setPinging(prev => ({ ...prev, [ip]: true }));
        try {
            const res = await fetch(`${API_BASE}/hosts/${ip}/ping`, { method: "POST" });
            const data = await res.json();
            if (onRefresh) onRefresh();
        } catch (err) { /* silencieux */ }
        finally { setPinging(prev => ({ ...prev, [ip]: false })); }
    };

    const handlePingAll = async () => {
        setPingAll(true);
        setPingAllResult(null);
        try {
            const res = await fetch(`${API_BASE}/hosts/ping-all`, { method: "POST" });
            const data = await res.json();
            setPingAllResult(data);
            if (onRefresh) onRefresh();
        } catch (err) {
            setPingAllResult({ error: true });
        } finally {
            setPingAll(false);
        }
    };

    const upCount = hosts.filter(h => h.status === 'up').length;
    const downCount = hosts.filter(h => h.status === 'down').length;

    return (
        <div className="h-full flex flex-col bg-white border border-gray-200 rounded-lg overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between shrink-0 bg-gray-50">
                <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-gray-700 text-sm">Machines découvertes</span>
                    <span className="text-xs text-gray-400">{hosts.length} hôte(s)</span>
                    {/* Compteurs up / down */}
                    <span className="flex items-center gap-1 text-xs">
                        <span className="inline-block w-2 h-2 rounded-full bg-green-400"></span>
                        <span className="text-green-700 font-medium">{upCount} up</span>
                    </span>
                    <span className="flex items-center gap-1 text-xs">
                        <span className="inline-block w-2 h-2 rounded-full bg-red-400"></span>
                        <span className="text-red-700 font-medium">{downCount} down</span>
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    {pingAllResult && !pingAllResult.error && (
                        <span className="text-xs text-gray-500 font-mono">
                            ↑ {pingAllResult.up}/{pingAllResult.total} répondent
                        </span>
                    )}
                    <button
                        onClick={handlePingAll}
                        disabled={pingAll || hosts.length === 0}
                        className="px-3 py-1.5 text-xs font-mono font-semibold border border-indigo-400 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                        {pingAll ? '⏳ Ping en cours...' : '⚡ Ping tout le monde'}
                    </button>
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto">
                <table className="w-full text-left text-sm">
                    <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 z-10">
                        <tr className="text-xs font-mono text-gray-500 uppercase tracking-wide">
                            <th className="px-4 py-2">IP</th>
                            <th className="px-4 py-2">MAC</th>
                            <th className="px-4 py-2">Nom / Fabricant</th>
                            <th className="px-4 py-2">Statut</th>
                            <th className="px-4 py-2">Dernier vu</th>
                            <th className="px-4 py-2"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {hosts.map(host => {
                            const isUp = host.status === 'up';
                            const isPinging = pinging[host.ip];
                            return (
                                <tr key={host.ip} className={`transition-colors ${isUp ? 'hover:bg-green-50' : 'hover:bg-red-50 bg-red-50/30'}`}>
                                    <td className="px-4 py-2 font-mono text-gray-800 font-semibold">{host.ip}</td>
                                    <td className="px-4 py-2 font-mono text-xs text-gray-400">{host.mac}</td>
                                    <td className="px-4 py-2 text-gray-600">{host.hostname}</td>
                                    <td className="px-4 py-2">
                                        <span className={`inline-flex items-center gap-1.5 text-xs font-mono font-bold uppercase ${isUp ? 'text-green-600' : 'text-red-600'}`}>
                                            <span className={`w-2 h-2 rounded-full ${isUp ? 'bg-green-400' : 'bg-red-400'}`}></span>
                                            {host.status}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2 text-xs text-gray-400 font-mono">
                                        {new Date(host.last_seen).toLocaleTimeString('fr-FR')}
                                    </td>
                                    <td className="px-4 py-2">
                                        <button
                                            onClick={() => handlePing(host.ip)}
                                            disabled={isPinging}
                                            className="px-2 py-1 text-xs font-mono border border-gray-300 text-gray-600 hover:border-indigo-400 hover:text-indigo-700 rounded disabled:opacity-40 transition-colors"
                                        >
                                            {isPinging ? '...' : 'ping'}
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                        {hosts.length === 0 && (
                            <tr>
                                <td colSpan="6" className="px-4 py-8 text-center text-gray-400 font-mono text-sm italic">
                                    scan en cours...
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
