import React, { useState } from 'react';
import { Wifi, WifiOff, Loader, Monitor } from 'lucide-react';

const API_BASE = "http://localhost:8000/api";

export default function HostsTable({ hosts, onRefresh }) {
    const [pinging, setPinging] = useState({});
    const [pingResults, setPingResults] = useState({});

    const handlePing = async (ip) => {
        setPinging(prev => ({ ...prev, [ip]: true }));
        try {
            const res = await fetch(`${API_BASE}/hosts/${ip}/ping`, { method: "POST" });
            const data = await res.json();
            setPingResults(prev => ({ ...prev, [ip]: data }));
            if (onRefresh) onRefresh(); // Rafraîchir la liste après le ping
        } catch (err) {
            setPingResults(prev => ({ ...prev, [ip]: { status: "error", reachable: false } }));
        } finally {
            setPinging(prev => ({ ...prev, [ip]: false }));
        }
    };

    return (
        <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-slate-100">
            <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Monitor className="text-teal-500" />
                    <h2 className="text-lg font-semibold text-slate-800">Machines découvertes sur le réseau</h2>
                </div>
                <span className="text-sm text-slate-400 font-medium">{hosts.length} hôte(s)</span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-slate-50 text-slate-500 text-sm">
                            <th className="p-4 font-medium">Adresse IP</th>
                            <th className="p-4 font-medium">Adresse MAC</th>
                            <th className="p-4 font-medium">Hostname</th>
                            <th className="p-4 font-medium">Statut</th>
                            <th className="p-4 font-medium">Dernier vu</th>
                            <th className="p-4 font-medium">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {hosts.map((host) => {
                            const isPinging = pinging[host.ip];
                            const result = pingResults[host.ip];
                            const displayStatus = result ? result.status : host.status;

                            return (
                                <tr key={host.ip} className="hover:bg-slate-50 transition-colors">
                                    <td className="p-4 font-mono text-slate-700 font-medium">{host.ip}</td>
                                    <td className="p-4 font-mono text-xs text-slate-500">{host.mac}</td>
                                    <td className="p-4 text-slate-600">{host.hostname}</td>
                                    <td className="p-4">
                                        <div className="flex items-center gap-2">
                                            {displayStatus === 'up'
                                                ? <Wifi size={16} className="text-green-500" />
                                                : <WifiOff size={16} className="text-red-500" />
                                            }
                                            <span className={`text-sm font-semibold uppercase ${displayStatus === 'up' ? 'text-green-600' : 'text-red-600'}`}>
                                                {displayStatus}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="p-4 text-sm text-slate-500">
                                        {new Date(host.last_seen).toLocaleTimeString('fr-FR')}
                                    </td>
                                    <td className="p-4">
                                        <button
                                            onClick={() => handlePing(host.ip)}
                                            disabled={isPinging}
                                            className="flex items-center gap-2 px-3 py-1.5 bg-teal-50 hover:bg-teal-100 text-teal-700 font-medium text-sm rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {isPinging
                                                ? <><Loader size={14} className="animate-spin" /> Ping...</>
                                                : <><Wifi size={14} /> Ping</>
                                            }
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                        {hosts.length === 0 && (
                            <tr>
                                <td colSpan="6" className="p-8 text-center text-slate-500">
                                    <Monitor className="mx-auto mb-2 opacity-30" size={32} />
                                    Aucune machine découverte encore... (scan en cours)
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
