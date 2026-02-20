import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function AlertBanner({ temperature, threshold = 25 }) {
  if (temperature <= threshold) return null;
  return (
    <div className="bg-red-500 text-white p-4 rounded-xl shadow-md flex items-center gap-3 animate-pulse mb-6">
      <AlertTriangle />
      <span className="font-semibold">Alerte Critique :</span>
      <span>Temperature {temperature}°C depasse le seuil de {threshold}°C !</span>
    </div>
  );
}
