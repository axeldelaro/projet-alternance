import React, { useEffect, useRef } from 'react';
import { Terminal } from 'lucide-react';

export default function LogsPanel({ logs }) {
  const bottomRef = useRef(null);

  // Auto-scroll vers le bas à chaque nouveau log
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="bg-slate-900 rounded-2xl shadow-lg overflow-hidden text-slate-300 font-mono text-xs h-full flex flex-col">
      <div className="px-4 py-3 border-b border-slate-700 bg-slate-800 flex items-center gap-3 shrink-0">
        <Terminal size={16} className="text-emerald-400" />
        <h2 className="font-semibold text-slate-100 text-sm">Journal / Alertes</h2>
        <span className="ml-auto text-xs text-slate-500">{logs.length} entrée(s)</span>
      </div>
      <div className="p-3 overflow-y-auto flex-1 space-y-1.5">
        {logs.map((log, idx) => {
          let colorClass = "text-slate-400";
          if (log.level === "warning") colorClass = "text-yellow-400";
          if (log.level === "error") colorClass = "text-red-400";
          if (log.level === "info") colorClass = "text-emerald-400";
          return (
            <div key={idx} className="flex gap-2 leading-relaxed">
              <span className="text-slate-600 shrink-0">[{new Date(log.timestamp).toLocaleTimeString('fr-FR')}]</span>
              <span className={`font-bold shrink-0 w-16 ${colorClass}`}>{log.level.toUpperCase()}</span>
              <span className="text-slate-300 break-all">{log.message}</span>
            </div>
          );
        })}
        {logs.length === 0 && <div className="text-slate-600 italic">Aucun log disponible...</div>}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
