'use client';

import { useState } from 'react';
import { incidentApi, type IncidentResponse } from '@/lib/api';
import { useMissionStore } from '@/lib/store';

const INCIDENT_TYPES = [
  { id: 'major_accident', label: 'Major Accident', icon: '🚗💥', color: '#B54A32', bg: '#FDE8E4' },
  { id: 'road_block', label: 'Road Block', icon: '🚧', color: '#D4740A', bg: '#FFF3D6' },
  { id: 'heavy_rain', label: 'Heavy Rain', icon: '🌧️', color: '#2E6DA4', bg: '#E3F0FA' },
  { id: 'festival_traffic', label: 'Festival Traffic', icon: '🎪', color: '#7B3FA0', bg: '#F3E8FA' },
  { id: 'signal_failure', label: 'Signal Failure', icon: '🚦', color: '#B59B1F', bg: '#FFF8D6' },
  { id: 'multiple_emergency_vehicles', label: 'Emergency Vehicles', icon: '🚒', color: '#B54A32', bg: '#FDE8E4' },
];

export default function IncidentSimulator() {
  const store = useMissionStore();
  const [simulating, setSimulating] = useState<string | null>(null);

  const activeIncidents = store.incidents.filter(i => i.status === 'active');
  const missionId = store.currentMission?.id;

  const handleSimulate = async (type: string) => {
    setSimulating(type);
    try {
      await incidentApi.simulate(type, missionId || undefined);
    } catch (err) {
      console.error('Failed to simulate incident:', err);
    } finally {
      setSimulating(null);
    }
  };

  const handleResolve = async (id: number) => {
    try {
      await incidentApi.resolve(id);
      store.resolveIncident(id);
    } catch (err) {
      console.error('Failed to resolve incident:', err);
    }
  };

  const severityBorder = (sev: string) => {
    if (sev === 'high') return '#B54A32';
    if (sev === 'medium') return '#D4740A';
    return '#B59B1F';
  };

  return (
    <div className="jm-card">
      <div className="jm-card-header">
        <span className="jm-card-title">🚨 Emergency Event Simulator</span>
        {activeIncidents.length > 0 && (
          <span className="jm-badge jm-badge-critical">{activeIncidents.length} active</span>
        )}
      </div>

      {/* Incident Buttons */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: activeIncidents.length > 0 ? 16 : 0 }}>
        {INCIDENT_TYPES.map(t => (
          <button
            key={t.id}
            onClick={() => handleSimulate(t.id)}
            disabled={simulating !== null}
            className="jm-incident-btn"
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 12px', borderRadius: 8,
              border: `1.5px solid ${t.color}20`,
              background: simulating === t.id ? t.color : t.bg,
              color: simulating === t.id ? 'white' : t.color,
              cursor: simulating ? 'not-allowed' : 'pointer',
              fontSize: 12, fontWeight: 600,
              transition: 'all 0.2s ease',
              opacity: simulating && simulating !== t.id ? 0.5 : 1,
            }}
          >
            <span style={{ fontSize: 16 }}>{t.icon}</span>
            <span>{simulating === t.id ? 'Simulating...' : t.label}</span>
          </button>
        ))}
      </div>

      {/* Active Incidents */}
      {activeIncidents.map(inc => (
        <div
          key={inc.id}
          className="animate-scale-in"
          style={{
            padding: 14, borderRadius: 10, marginBottom: 10,
            background: '#FFF9F5',
            borderLeft: `4px solid ${severityBorder(inc.severity)}`,
            boxShadow: '0 2px 8px rgba(181, 74, 50, 0.08)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: severityBorder(inc.severity) }}>
              {inc.incident_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </span>
            <span className={`jm-badge ${inc.severity === 'high' ? 'jm-badge-critical' : inc.severity === 'medium' ? 'jm-badge-warning' : 'jm-badge-gray'}`}
              style={{ fontSize: 10, padding: '2px 8px' }}>
              {inc.severity.toUpperCase()}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11, color: 'var(--earth-brown)' }}>
            <div><strong>Location:</strong> {inc.location_name}</div>
            <div><strong>Segment:</strong> {inc.segment_name || inc.segment_id || '—'}</div>
            {inc.affected_lanes !== null && inc.affected_lanes > 0 && (
              <div><strong>Affected:</strong> {inc.affected_lanes} of {inc.total_lanes} lanes</div>
            )}
            <div><strong>Delay:</strong> +{inc.estimated_delay_minutes} min</div>
            {inc.speed_before_kmh && inc.speed_after_kmh && (
              <div><strong>Speed:</strong> {inc.speed_before_kmh} → {inc.speed_after_kmh} km/h</div>
            )}
            {inc.congestion_before !== null && inc.congestion_after !== null && (
              <div><strong>Congestion:</strong> {Math.round(inc.congestion_before * 100)}% → {Math.round(inc.congestion_after * 100)}%</div>
            )}
          </div>

          {inc.description && (
            <div style={{ fontSize: 11, color: 'var(--warm-gray)', marginTop: 6, fontStyle: 'italic' }}>
              {inc.description}
            </div>
          )}

          <button
            onClick={() => handleResolve(inc.id)}
            className="jm-btn jm-btn-outline"
            style={{ width: '100%', marginTop: 10, padding: '6px 12px', fontSize: 11 }}
          >
            ✅ Resolve Incident
          </button>
        </div>
      ))}
    </div>
  );
}
