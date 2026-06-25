'use client';

import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.css';
import 'leaflet-defaulticon-compatibility';
import type { RouteDataResponse, IncidentResponse } from '@/lib/api';
import { useMissionStore } from '@/lib/store';

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

// Incident type icons & colors
const INCIDENT_MARKER_CONFIG: Record<string, { icon: string; color: string; label: string }> = {
  major_accident:              { icon: '🚗💥', color: '#EF4444', label: 'Major Accident' },
  road_block:                  { icon: '🚧',   color: '#F97316', label: 'Road Block' },
  heavy_rain:                  { icon: '🌧️',   color: '#3B82F6', label: 'Heavy Rain' },
  festival_traffic:            { icon: '🎪',   color: '#A855F7', label: 'Festival Traffic' },
  signal_failure:              { icon: '🚦',   color: '#EAB308', label: 'Signal Failure' },
  multiple_emergency_vehicles: { icon: '🚒',   color: '#EF4444', label: 'Emergency Vehicles' },
};

function makeIncidentIcon(type: string): L.DivIcon {
  const cfg = INCIDENT_MARKER_CONFIG[type] || { icon: '⚠️', color: '#EF4444' };
  return new L.DivIcon({
    className: '',
    html: `<div style="background:${cfg.color};color:white;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;box-shadow:0 2px 10px ${cfg.color}60;animation:pulse-marker 2s ease-in-out infinite">${cfg.icon}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

function getClosestWaypointIndex(lat: number, lng: number, waypoints: number[][]): number {
  if (waypoints.length === 0) return -1;
  let minDistance = Infinity;
  let closestIndex = -1;
  for (let i = 0; i < waypoints.length; i++) {
    const [wLat, wLng] = waypoints[i];
    const dist = Math.pow(wLat - lat, 2) + Math.pow(wLng - lng, 2);
    if (dist < minDistance) {
      minDistance = dist;
      closestIndex = i;
    }
  }
  return closestIndex;
}

interface MapSectionProps {
  routes: RouteDataResponse[];
  origin?: { lat: number; lng: number; name: string };
  destination?: { lat: number; lng: number; name: string };
  incidents?: IncidentResponse[];
  missionStatus?: string | null;
  trustScore?: number | null;
  approvalStatus?: string; // 'pending' | 'approved' | 'rejected' | null
  role?: string;
  onApproveReject?: (approvalId: number, action: 'approve' | 'reject') => void;
  isApproving?: number | null;
}

function FitBounds({
  origin,
  destination,
  routes = [],
  incidents = [],
}: {
  origin?: { lat: number; lng: number };
  destination?: { lat: number; lng: number };
  routes?: RouteDataResponse[];
  incidents?: IncidentResponse[];
}) {
  const map = useMap();
  useEffect(() => {
    const points: [number, number][] = [];
    if (origin) points.push([origin.lat, origin.lng]);
    if (destination) points.push([destination.lat, destination.lng]);

    routes.forEach((route) => {
      if (route.waypoints && route.waypoints.length > 0) {
        route.waypoints.forEach((w) => {
          points.push([w[0], w[1]]);
        });
      }
    });

    incidents.forEach((inc) => {
      if (inc.status === 'active') {
        points.push([inc.location_lat, inc.location_lng]);
      }
    });

    if (points.length > 0) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [60, 60], maxZoom: 16 });
    }
  }, [origin, destination, routes, incidents, map]);
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

function InvalidateMapSize({ isFullscreen }: { isFullscreen: boolean }) {
  const map = useMap();
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 150);
    return () => clearTimeout(timer);
  }, [isFullscreen, map]);
  return null;
}

export default function MapSection({
  routes, origin, destination,
  incidents = [], missionStatus, trustScore, approvalStatus,
  role, onApproveReject, isApproving,
}: MapSectionProps) {
  const defaultCenter: [number, number] = [28.6139, 77.2090]; // Delhi
  const [isFullscreen, setIsFullscreen] = useState(false);
  const primaryRoute = routes.find(r => r.route_type === 'primary' && r.is_active);
  const altRoute = routes.find(r => r.route_type === 'alternative');
  const store = useMissionStore();

  // Logs for visual diagnostics
  console.log("Active Route", primaryRoute);
  console.log("Recovery Route", altRoute);
  console.log("Route Points", primaryRoute?.waypoints?.length);

  // Compute map bounds points
  const boundsPoints: [number, number][] = [];
  if (origin) boundsPoints.push([origin.lat, origin.lng]);
  if (destination) boundsPoints.push([destination.lat, destination.lng]);
  routes.forEach((route) => {
    if (route.waypoints && route.waypoints.length > 0) {
      route.waypoints.forEach((w) => {
        boundsPoints.push([w[0], w[1]]);
      });
    }
  });
  incidents.forEach((inc) => {
    if (inc.status === 'active') {
      boundsPoints.push([inc.location_lat, inc.location_lng]);
    }
  });

  // Find latest approval from store
  const latestApproval = store.approvals.length > 0 ? store.approvals[store.approvals.length - 1] : null;

  // Determine if corridor is degraded
  const hasActiveIncidents = incidents.filter(i => i.status === 'active').length > 0;
  const isDegraded = hasActiveIncidents || (typeof trustScore === 'number' && trustScore < 70) ||
    missionStatus === 'degraded' || missionStatus === 'awaiting_approval';
  const isRecovered = approvalStatus === 'approved' || missionStatus === 'completed';

  // Primary route color: green when healthy, red when degraded
  const primaryColor = isDegraded && !isRecovered ? '#EF4444' : '#10B981';
  const primaryWeight = 8;
  const primaryOpacity = isRecovered ? 0.0 : 0.85;

  // Recovery route color
  const altColor = '#10B981';
  const altWeight = 8;
  const altOpacity = isRecovered ? 0.95 : 0.75;

  // Compute map center from origin/destination or use default
  const center: [number, number] = origin && destination
    ? [(origin.lat + destination.lat) / 2, (origin.lng + destination.lng) / 2]
    : defaultCenter;

  // Comparison metrics calculations
  const trustBefore = latestApproval?.trust_score_before ?? Math.round(trustScore || 64);
  const trustAfter = latestApproval?.trust_score_after ?? 95;
  const etaBefore = latestApproval?.eta_before ?? primaryRoute?.eta_minutes ?? 18.7;
  const etaAfter = latestApproval?.eta_after ?? altRoute?.eta_minutes ?? 13.8;
  const trustDelta = trustAfter - trustBefore;
  const etaDelta = (etaAfter - etaBefore).toFixed(1);
  const avoidedSegments = incidents.filter(i => i.status === 'active').length || 2;

  return (
    <div 
      className="jm-card" 
      style={isFullscreen ? {
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex: 9999,
        borderRadius: 0,
        margin: 0,
        padding: 0,
        overflow: 'hidden',
        boxShadow: 'none',
      } : {
        padding: 0,
        overflow: 'hidden',
        height: '100%',
        minHeight: 420,
        position: 'relative',
      }}
    >
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border-green)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'white',
        position: 'relative',
        zIndex: 10
      }}>
        <span className="jm-card-title">🗺️ Route Intelligence Map</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 11 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 16, height: 3, background: isDegraded && !isRecovered ? '#EF4444' : '#10B981', borderRadius: 2, display: 'inline-block' }} />
            Primary{isDegraded && !isRecovered ? ' (Affected)' : ''}
          </span>
          {altRoute && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 16, height: 3, background: '#10B981', borderRadius: 2, display: 'inline-block', border: !isRecovered ? '1.5px dashed var(--forest-green)' : 'none' }} />
              Recovery
            </span>
          )}
          {hasActiveIncidents && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#EF4444', fontWeight: 600 }}>
              ⚠️ {incidents.filter(i => i.status === 'active').length} incident(s)
            </span>
          )}
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            style={{
              background: 'var(--soft-beige)',
              border: '1.5px solid var(--border-green)',
              borderRadius: '6px',
              padding: '4px 8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 4,
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--forest-green)',
              transition: 'all 0.2s ease',
            }}
            title={isFullscreen ? "Collapse Map" : "Expand Map"}
          >
            {isFullscreen ? (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M10 14l-7 7"/></svg>
                <span>Collapse</span>
              </>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                <span>Fullscreen</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Route comparison overlay */}
      {altRoute && primaryRoute && (
        <div 
          className="animate-slide-in"
          style={{
            position: 'absolute', top: 68, right: 16, zIndex: 1000,
            background: 'rgba(255, 255, 255, 0.9)', borderRadius: 12,
            padding: '16px', boxShadow: '0 8px 32px rgba(45, 80, 22, 0.15)',
            minWidth: 240, backdropFilter: 'blur(12px)',
            border: '1.5px solid var(--border-green)',
            display: 'flex', flexDirection: 'column', gap: 12
          }}
        >
          {!isRecovered ? (
            <>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--forest-green)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                ⚠️ Recovery Recommended
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px', fontSize: 12, alignItems: 'center', borderBottom: '1px solid var(--light-sage)', paddingBottom: 8 }}>
                <div></div>
                <div style={{ color: '#EF4444', fontWeight: 700, textAlign: 'center' }}>Current</div>
                <div style={{ color: '#10B981', fontWeight: 700, textAlign: 'center' }}>Recovery</div>
                
                <div style={{ color: 'var(--earth-brown)', fontWeight: 500 }}>Trust</div>
                <div style={{ color: '#EF4444', fontWeight: 600, textAlign: 'center' }}>{trustBefore}</div>
                <div style={{ color: '#10B981', fontWeight: 600, textAlign: 'center' }}>{trustAfter}</div>
                
                <div style={{ color: 'var(--earth-brown)', fontWeight: 500 }}>ETA</div>
                <div style={{ color: '#EF4444', fontWeight: 600, textAlign: 'center' }}>{typeof etaBefore === 'number' ? etaBefore.toFixed(1) : etaBefore}m</div>
                <div style={{ color: '#10B981', fontWeight: 600, textAlign: 'center' }}>{typeof etaAfter === 'number' ? etaAfter.toFixed(1) : etaAfter}m</div>
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--earth-brown)', textTransform: 'uppercase' }}>Improvements</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ background: '#E8F5E9', color: '#2E7D32', fontSize: 11, padding: '4px 8px', borderRadius: 12, fontWeight: 600 }}>
                    +{trustDelta} Trust
                  </span>
                  <span style={{ background: '#E8F5E9', color: '#2E7D32', fontSize: 11, padding: '4px 8px', borderRadius: 12, fontWeight: 600 }}>
                    {etaDelta} min ETA
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#D84315', background: '#FBE9E7', padding: '6px 10px', borderRadius: 8 }}>
                <span>🛡️</span>
                <strong>{avoidedSegments} Segments Avoided</strong>
              </div>

              {/* Map Overlay Approve/Reject buttons for Operator/Admin */}
              {role && (role === 'operator' || role === 'administrator' || role === 'admin') && onApproveReject && latestApproval && latestApproval.status === 'pending' && (
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <button
                    className="jm-btn jm-btn-success"
                    style={{ flex: 1, padding: '8px 12px', fontSize: 11, height: '32px' }}
                    disabled={isApproving === latestApproval.id}
                    onClick={() => onApproveReject(latestApproval.id, 'approve')}
                  >
                    {isApproving === latestApproval.id ? '...' : '✅ Approve'}
                  </button>
                  <button
                    className="jm-btn jm-btn-danger"
                    style={{ flex: 1, padding: '8px 12px', fontSize: 11, height: '32px' }}
                    disabled={isApproving === latestApproval.id}
                    onClick={() => onApproveReject(latestApproval.id, 'reject')}
                  >
                    ❌ Reject
                  </button>
                </div>
              )}
            </>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 700, color: 'var(--forest-green)' }}>
                <span>🎉</span> Emergency Corridor Recovered
              </div>
              
              <div style={{ background: '#E8F0D8', border: '1.5px solid var(--border-green)', borderRadius: 8, padding: '10px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ color: 'var(--earth-brown)' }}>Corridor Status:</span>
                  <span className="jm-badge jm-badge-green" style={{ fontSize: 10, padding: '2px 6px', fontWeight: 700 }}>
                    MISSION STABILIZED
                  </span>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: 'var(--earth-brown)' }}>Trust Recovery:</span>
                  <span style={{ fontWeight: 700, color: 'var(--forest-green)' }}>
                    {trustBefore} → {trustAfter}
                  </span>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: 'var(--earth-brown)' }}>ETA Restored:</span>
                  <span style={{ fontWeight: 700, color: 'var(--forest-green)' }}>
                    {typeof etaBefore === 'number' ? etaBefore.toFixed(1) : etaBefore}m → {typeof etaAfter === 'number' ? etaAfter.toFixed(1) : etaAfter}m
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      <MapContainer
          center={center}
          zoom={13}
          style={{ height: isFullscreen ? 'calc(100% - 85px)' : 'calc(100% - 80px)', width: '100%' }}
          zoomControl={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <FitBounds origin={origin} destination={destination} routes={routes} incidents={incidents} />
          <InvalidateMapSize isFullscreen={isFullscreen} />

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
              key={`${primaryColor}-${primaryOpacity}`}
              positions={primaryRoute.waypoints.map(w => [w[0], w[1]] as [number, number])}
              pathOptions={{
                color: primaryColor,
                weight: primaryWeight,
                opacity: primaryOpacity,
                className: 'jm-route-primary'
              }}
            />
            {!isDegraded && (
              <AnimatedAmbulance waypoints={primaryRoute.waypoints} />
            )}
          </>
        )}

        {/* Alternative / Recovery Route */}
        {altRoute && altRoute.waypoints.length > 0 && (
          <>
            <Polyline
              key={`${altColor}-${altOpacity}-${isRecovered ? 'rec' : 'not'}`}
              positions={altRoute.waypoints.map(w => [w[0], w[1]] as [number, number])}
              pathOptions={{
                color: altColor,
                weight: altWeight,
                opacity: altOpacity,
                dashArray: isRecovered ? undefined : '12, 8',
                className: 'jm-route-recovery'
              }}
            />
            {isRecovered && (
              <AnimatedAmbulance waypoints={altRoute.waypoints} />
            )}
          </>
        )}

        {/* Incident-Centric Highlights & Markers */}
        {incidents.filter(i => i.status === 'active').map(inc => {
          const cfg = INCIDENT_MARKER_CONFIG[inc.incident_type] || { icon: '⚠️', color: '#EF4444', label: 'Incident' };
          
          // Compute closest waypoint on primary route to incident
          const closestWpIndex = primaryRoute ? getClosestWaypointIndex(inc.location_lat, inc.location_lng, primaryRoute.waypoints) : -1;
          const closestWp = closestWpIndex !== -1 && primaryRoute ? primaryRoute.waypoints[closestWpIndex] : null;

          return (
            <div key={inc.id}>
              {/* Leader Line to Route */}
              {closestWp && (
                <Polyline
                  positions={[[inc.location_lat, inc.location_lng], [closestWp[0], closestWp[1]]]}
                  pathOptions={{
                    color: cfg.color,
                    weight: 3,
                    dashArray: '6, 6',
                    opacity: 0.85
                  }}
                />
              )}

              {/* Pulsing Warning Circle */}
              <Circle
                center={[inc.location_lat, inc.location_lng]}
                radius={150}
                pathOptions={{
                  color: cfg.color,
                  fillColor: cfg.color,
                  fillOpacity: 0.15,
                  weight: 2,
                  dashArray: '4, 4'
                }}
              />

              {/* Thick Glowing Segment Highlight */}
              {closestWpIndex !== -1 && primaryRoute && (
                <Polyline
                  positions={primaryRoute.waypoints.slice(
                    Math.max(0, closestWpIndex - 2),
                    Math.min(primaryRoute.waypoints.length, closestWpIndex + 3)
                  ).map(w => [w[0], w[1]] as [number, number])}
                  pathOptions={{
                    color: '#EF4444',
                    weight: 14,
                    opacity: 0.45,
                    lineCap: 'round'
                  }}
                />
              )}

              {/* Incident Marker */}
              <Marker
                position={[inc.location_lat, inc.location_lng]}
                icon={makeIncidentIcon(inc.incident_type)}
              >
                <Popup>
                  <div style={{ minWidth: 180 }}>
                    <strong style={{ color: cfg.color }}>{cfg.label}</strong><br />
                    <div style={{ fontSize: 12, marginTop: 4 }}>
                      <strong>Severity:</strong> {inc.severity.toUpperCase()}<br />
                      <strong>Location:</strong> {inc.location_name}<br />
                      {inc.segment_name && <><strong>Segment:</strong> {inc.segment_name}<br /></>}
                      <strong>Delay:</strong> +{inc.estimated_delay_minutes} min<br />
                      {inc.affected_lanes !== null && inc.affected_lanes > 0 && (
                        <><strong>Lanes:</strong> {inc.affected_lanes} of {inc.total_lanes} blocked<br /></>
                      )}
                      {inc.speed_before_kmh && inc.speed_after_kmh && (
                        <><strong>Speed:</strong> {inc.speed_before_kmh} → {inc.speed_after_kmh} km/h<br /></>
                      )}
                    </div>
                  </div>
                </Popup>
              </Marker>
            </div>
          );
        })}
      </MapContainer>

      {/* Route Debug Panel */}
      <div style={{
        background: 'var(--soft-beige)',
        borderTop: '1px solid var(--border-green)',
        padding: '8px 16px',
        display: 'flex',
        gap: '24px',
        fontSize: '11px',
        fontFamily: 'monospace',
        color: 'var(--earth-brown)',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 20,
        position: 'relative'
      }}>
        <div style={{ display: 'flex', gap: 16 }}>
          <span>🟢 <strong>Active Route:</strong> {primaryRoute?.waypoints?.length || 0} pts ({primaryRoute?.route_source || "Synthetic Fallback"})</span>
          <span>🔵 <strong>Recovery Route:</strong> {altRoute?.waypoints?.length || 0} pts ({altRoute?.route_source || "Synthetic Fallback"})</span>
          <span>📐 <strong>Map Bounds Points:</strong> {boundsPoints.length}</span>
        </div>
        <div style={{ fontSize: 9, opacity: 0.7, textTransform: 'uppercase', letterSpacing: 0.5 }}>
          Live Visual Diagnostics
        </div>
      </div>
    </div>
  );
}
