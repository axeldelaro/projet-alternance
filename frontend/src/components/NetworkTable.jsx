import React from 'react';
import { Server, Activity } from 'lucide-react';

export default function NetworkTable({ devices }) {
  return (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-slate-100 flex flex-col max-h-48">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-3 shrink-0">
        <Server size={18} className="text-indigo-500" />
        <h2 className="text-sm font-semibold text-slate-800">Équipements Réseau (SNMP)</h2>
        <span className="ml-auto text-xs text-slate-400">{devices.length} équipement(s)</span>
      </div>
      <div className="overflow-y-auto flex-1">
        <table className="w-full text-left border-collapse text-sm">
          <thead className="sticky top-0 bg-slate-50 z-10">
            <tr className="text-slate-500">
              <th className="px-4 py-2 font-medium">Nom</th>
              <th className="px-4 py-2 font-medium">Statut</th>
              <th className="px-4 py-2 font-medium">Dernier Check</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {devices.map((device, idx) => (
              <tr key={idx} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-2 font-medium text-slate-700">{device.device_name}</td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2.5 w-2.5">
                      {device.status === 'up' && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>}
                      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${device.status === 'up' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                    </span>
                    <span className={`text-xs font-semibold uppercase ${device.status === 'up' ? 'text-green-600' : 'text-red-600'}`}>{device.status}</span>
                  </div>
                </td>
                <td className="px-4 py-2 text-xs text-slate-500">{new Date(device.timestamp).toLocaleTimeString('fr-FR')}</td>
              </tr>
            ))}
            {devices.length === 0 && (
              <tr><td colSpan="3" className="px-4 py-4 text-center text-slate-400 text-xs"><Activity size={16} className="inline mr-2 opacity-50" />Aucun équipement SNMP configuré</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
