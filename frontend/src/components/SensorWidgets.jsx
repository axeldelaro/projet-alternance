import React, { useEffect, useRef } from 'react';
import { AlertTriangle, Thermometer, Droplets } from 'lucide-react';

// ── Alerte critique température ──────────────────────────────────────────────
export function AlertBanner({ temperature, threshold = 25 }) {
    if (temperature <= threshold) return null;
    return (
        <div className="bg-red-500 text-white p-4 rounded-xl shadow-md flex items-center gap-3 animate-pulse mb-6">
            <AlertTriangle />
            <span className="font-semibold">Alerte Critique :</span>
            <span>Temperature {temperature}°C depasse le seuil de {threshold}°C !</span>
        </div>
    );
}

// ── Carte Température ─────────────────────────────────────────────────────────
export function TemperatureCard({ temperature, threshold = 25 }) {
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

// ── Carte Humidité ────────────────────────────────────────────────────────────
export function HumidityCard({ humidity }) {
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
