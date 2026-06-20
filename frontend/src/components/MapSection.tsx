'use client';

import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.css';
import 'leaflet-defaulticon-compatibility';
import type { RouteDataResponse } from '@/lib/api';

// Custom icons
const ambulanceIcon = new L.DivIcon({
  className: '',
  html: `<div style="background:#2D5016;color:white;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;border:2px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3)">🚑</div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

const hospitalIcon = new L.DivIcon({
  className: '',
  html: `<div style="background:#B54A32;color:white;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3)">🏥</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

const originIcon = new L.DivIcon({
  className: '',
  html: `<div style="background:#6B8F23;color:white;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3)">📍</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

interface MapSectionProps {
  routes: RouteDataResponse[];
  origin?: { lat: number; lng: number; name: string };
  destination?: { lat: number; lng: number; name: string };
}

function FitBounds({ origin, destination }: { origin?: { lat: number; lng: number }; destination?: { lat: number; lng: number } }) {
  const map = useMap();
  useEffect(() => {
    if (origin && destination) {
      const bounds = L.latLngBounds([
        [origin.lat, origin.lng],
        [destination.lat, destination.lng],
      ]);
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [origin, destination, map]);
  return null;
}

function AnimatedAmbulance({ waypoints }: { waypoints: number[][] }) {
  const [position, setPosition] = useState<[number, number]>(
    waypoints[0] as [number, number]
  );
  const [waypointIndex, setWaypointIndex] = useState(0);

  useEffect(() => {
    if (waypoints.length < 2) return;

    const interval = setInterval(() => {
      setWaypointIndex((prev) => {
        const next = prev + 1;
        if (next >= waypoints.length) {
          clearInterval(interval);
          return prev;
        }
        setPosition(waypoints[next] as [number, number]);
        return next;
      });
    }, 800);

    return () => clearInterval(interval);
  }, [waypoints]);

  return (
    <Marker position={position} icon={ambulanceIcon}>
      <Popup>
        <strong>🚑 Ambulance</strong><br />
        Position: {position[0].toFixed(4)}, {position[1].toFixed(4)}<br />
        Waypoint: {waypointIndex + 1}/{waypoints.length}
      </Popup>
    </Marker>
  );
}

export default function MapSection({ routes, origin, destination }: MapSectionProps) {
  const defaultCenter: [number, number] = [28.6139, 77.2090]; // Delhi
  const primaryRoute = routes.find(r => r.route_type === 'primary' && r.is_active);
  const altRoute = routes.find(r => r.route_type === 'alternative');

  // Hospital data (hardcoded subset for map markers)
  const hospitals = [
    { name: 'AIIMS Delhi', lat: 28.5672, lng: 77.2100 },
    { name: 'Safdarjung Hospital', lat: 28.5685, lng: 77.2065 },
    { name: 'RML Hospital', lat: 28.6270, lng: 77.2050 },
    { name: 'Lok Nayak Hospital', lat: 28.6370, lng: 77.2390 },
  ];

  return (
    <div className="jm-card" style={{ padding: 0, overflow: 'hidden', height: '100%', minHeight: 420 }}>
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border-green)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span className="jm-card-title">🗺️ Route Intelligence Map</span>
        <div style={{ display: 'flex', gap: 12, fontSize: 11 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 16, height: 3, background: '#2D5016', borderRadius: 2, display: 'inline-block' }} />
            Primary
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 16, height: 0, background: '#C4A35A', borderRadius: 2, display: 'inline-block', borderTop: '2px dashed #C4A35A' }} />
            Alternative
          </span>
        </div>
      </div>
      <MapContainer
        center={defaultCenter}
        zoom={13}
        style={{ height: 'calc(100% - 48px)', width: '100%' }}
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <FitBounds origin={origin} destination={destination} />

        {/* Origin Marker */}
        {origin && (
          <Marker position={[origin.lat, origin.lng]} icon={originIcon}>
            <Popup><strong>📍 Origin</strong><br />{origin.name}</Popup>
          </Marker>
        )}

        {/* Destination Marker */}
        {destination && (
          <Marker position={[destination.lat, destination.lng]} icon={hospitalIcon}>
            <Popup><strong>🏥 Destination</strong><br />{destination.name}</Popup>
          </Marker>
        )}

        {/* Primary Route */}
        {primaryRoute && primaryRoute.waypoints.length > 0 && (
          <>
            <Polyline
              positions={primaryRoute.waypoints.map(w => [w[0], w[1]] as [number, number])}
              pathOptions={{ color: '#2D5016', weight: 5, opacity: 0.8 }}
            />
            <AnimatedAmbulance waypoints={primaryRoute.waypoints} />
          </>
        )}

        {/* Alternative Route */}
        {altRoute && altRoute.waypoints.length > 0 && (
          <Polyline
            positions={altRoute.waypoints.map(w => [w[0], w[1]] as [number, number])}
            pathOptions={{ color: '#C4A35A', weight: 4, opacity: 0.7, dashArray: '10, 8' }}
          />
        )}

        {/* Hospital Markers */}
        {hospitals.map((h, i) => (
          <Marker key={i} position={[h.lat, h.lng]} icon={hospitalIcon}>
            <Popup><strong>🏥 {h.name}</strong></Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
