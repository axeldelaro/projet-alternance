import React from 'react';
import { Server, Activity } from 'lucide-react';

export default function NetworkTable({ devices }) {
  return (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-slate-100 h-full">
      <div className="p-6 border-b border-slate-100 flex items-center gap-3">
        <Server className="text-indigo-500" />
        <h2 className="text-lg font-semibold text-slate-800">Equipements Reseau</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 text-slate-500 text-sm">
              <th className="p-4 font-medium">Nom</th>
              <th className="p-4 font-medium">Statut</th>
              <th className="p-4 font-medium">Dernier Check</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {devices.map((device, idx) => (
              <tr key={idx} className="hover:bg-slate-50 transition-colors">
                <td className="p-4 font-medium text-slate-700">{device.device_name}</td>
                <td className="p-4">
                  <div className="flex items-center gap-2">
                    <span className={`relative flex h-3 w-3`}>
                      {device.status === 'up' && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>}
                      <span className={`relative inline-flex rounded-full h-3 w-3 ${device.status === 'up' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                    </span>
                    <span className={`text-sm font-semibold uppercase ${device.status === 'up' ? 'text-green-600' : 'text-red-600'}`}>{device.status}</span>
                  </div>
                </td>
                <td className="p-4 text-sm text-slate-500">{new Date(device.timestamp).toLocaleTimeString('fr-FR')}</td>
              </tr>
            ))}
            {devices.length === 0 && (
              <tr><td colSpan="3" className="p-8 text-center text-slate-500"><Activity className="mx-auto mb-2 opacity-50" />Aucun equipement scanne</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
