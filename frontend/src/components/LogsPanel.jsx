import React from 'react';
import { Terminal } from 'lucide-react';

export default function LogsPanel({ logs }) {
  return (
    <div className="bg-slate-900 rounded-2xl shadow-lg overflow-hidden text-slate-300 font-mono text-sm h-full max-h-[600px] flex flex-col">
      <div className="p-4 border-b border-slate-700 bg-slate-800 flex items-center gap-3 shrink-0">
        <Terminal size={18} className="text-emerald-400" />
        <h2 className="font-semibold text-slate-100">Terminal (Logs / Alertes)</h2>
      </div>
      <div className="p-4 overflow-y-auto flex-1 space-y-2">
        {logs.map((log, idx) => {
          let colorClass = "text-slate-400";
          if (log.level === "warning") colorClass = "text-yellow-400";
          if (log.level === "error") colorClass = "text-red-400";
          if (log.level === "info") colorClass = "text-emerald-400";
          return (
            <div key={idx} className="flex gap-4">
              <span className="text-slate-500 shrink-0">[{new Date(log.timestamp).toLocaleTimeString('fr-FR')}]</span>
              <span className={`font-medium w-20 shrink-0 ${colorClass}`}>{log.level.toUpperCase()}</span>
              <span className="text-slate-300 break-all">{log.message}</span>
            </div>
          );
        })}
        {logs.length === 0 && <div className="text-slate-500 italic">Aucun log disponible...</div>}
      </div>
    </div>
  );
}
