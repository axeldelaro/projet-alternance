import React from 'react';
import { Droplets } from 'lucide-react';

export default function HumidityCard({ humidity }) {
  return (
    <div className="bg-white p-6 rounded-2xl shadow-lg flex items-center justify-between text-slate-800">
      <div>
        <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wider">Humidite</h3>
        <p className="text-4xl font-bold mt-2 text-blue-600">{humidity}%</p>
      </div>
      <div className="bg-blue-50 text-blue-500 p-4 rounded-full">
        <Droplets size={32} />
      </div>
    </div>
  );
}
