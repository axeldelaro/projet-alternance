import React, { useState, useEffect } from 'react';
import { fetchLatestSensors, fetchDevices } from './services/api';

export default function App() {
  const [sensors, setSensors] = useState({ temperature: 0, humidity: 0 });
  const [devices, setDevices] = useState([]);

  useEffect(() => {
    // TODO: remplacer par un vrai composant + fetch logs
    fetchLatestSensors().then(setSensors).catch(console.error);
    fetchDevices().then(setDevices).catch(console.error);
  }, []);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">Supervision RRG</h1>
      <p>Temperature: {sensors.temperature}°C</p>
      <p>Humidite: {sensors.humidity}%</p>
    </div>
  );
}
