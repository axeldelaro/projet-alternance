import React from 'react';
import { Thermometer } from 'lucide-react';

export default function TemperatureCard({ temperature, threshold = 25 }) {
  const isAlert = temperature > threshold;
  return (
    <div className={`p-6 rounded-2xl shadow-lg flex items-center justify-between transition-colors duration-300 ${isAlert ? 'bg-red-500 text-white' : 'bg-white text-slate-800'}`}>
      <div>
        <h3 className="text-sm font-medium opacity-80 uppercase tracking-wider">Temperature</h3>
        <p className="text-4xl font-bold mt-2">{temperature}°C</p>
      </div>
      <div className={`p-4 rounded-full ${isAlert ? 'bg-red-400 bg-opacity-50' : 'bg-blue-50 text-blue-500'}`}>
        <Thermometer size={32} />
      </div>
    </div>
  );
}
