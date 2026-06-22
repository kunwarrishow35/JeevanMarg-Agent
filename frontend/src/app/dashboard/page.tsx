'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { useAuthStore, useMissionStore } from '@/lib/store';
import {
  missionApi, approvalApi, systemApi, incidentApi, createGlobalWebSocket,
  type MissionResponse, type WSEvent,
} from '@/lib/api';
import IncidentSimulator from '@/components/IncidentSimulator';
import MissionTimeline from '@/components/MissionTimeline';
import LocationInput from '@/components/LocationInput';

// Dynamically import map (no SSR)
const MapSection = dynamic(() => import('@/components/MapSection'), { ssr: false });

// Agent config
const AGENTS = [
  { name: 'emergency_coordinator', display: 'Emergency Coordinator', color: 'var(--agent-coordinator)' },
  { name: 'route_intelligence', display: 'Route Intelligence', color: 'var(--agent-route)' },
  { name: 'traffic_intelligence', display: 'Traffic Intelligence', color: 'var(--agent-traffic)' },
  { name: 'trust_score', display: 'Trust Score', color: 'var(--agent-trust)' },
  { name: 'recovery', display: 'Recovery', color: 'var(--agent-recovery)' },
];

const MCP_SERVERS = [
  { name: 'traffic', display: 'Traffic MCP', color: 'var(--mcp-traffic)', icon: '🚦' },
  { name: 'route', display: 'Route MCP', color: 'var(--mcp-route)', icon: '🛣️' },
  { name: 'hospital', display: 'Hospital MCP', color: 'var(--mcp-hospital)', icon: '🏥' },
  { name: 'trust', display: 'Trust MCP', color: 'var(--mcp-trust)', icon: '🛡️' },
];

// Role visibility config
function canView(role: string, feature: string): boolean {
  const permissions: Record<string, string[]> = {
    dispatcher: ['mission_create', 'mission_status', 'map', 'agents', 'mcp', 'incidents', 'timeline', 'trust'],
    operator: ['mission_status', 'map', 'agents', 'approvals', 'recovery', 'incidents', 'timeline', 'trust'],
    administrator: ['mission_create', 'mission_status', 'map', 'agents', 'mcp', 'approvals', 'recovery', 'incidents', 'timeline', 'trust', 'system'],
  };
  return permissions[role]?.includes(feature) ?? false;
}

function getRoleBadgeClass(role: string): string {
  if (role === 'dispatcher') return 'jm-role-badge jm-role-dispatcher';
  if (role === 'operator') return 'jm-role-badge jm-role-operator';
  if (role === 'administrator') return 'jm-role-badge jm-role-administrator';
  return 'jm-role-badge';
}

function TrustScoreGauge({ score, level }: { score: number | null; level: string | null }) {
  const [displayScore, setDisplayScore] = useState<number>(0);

  useEffect(() => {
    if (score === null) {
      setDisplayScore(0);
      return;
    }

    const start = displayScore;
    const end = Math.round(score);
    if (start === end) return;

    const duration = 1500; // 1.5 seconds
    const startTime = performance.now();
    let frameId: number;

    const animate = (time: number) => {
      const elapsed = time - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutQuad
      const ease = progress * (2 - progress);
      const current = Math.round(start + (end - start) * ease);
      setDisplayScore(current);

      if (progress < 1) {
        frameId = requestAnimationFrame(animate);
      }
    };

    frameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameId);
  }, [score]);

  // Derive status/color from the active animated score
  const trustColor = displayScore >= 90 ? 'var(--trust-excellent)'
    : displayScore >= 70 ? 'var(--trust-healthy)'
    : displayScore >= 50 ? 'var(--trust-warning)'
    : displayScore > 0 ? 'var(--trust-critical)'
    : 'var(--warm-gray)';

  return (
    <div
      className="jm-trust-gauge"
      style={{
        background: `conic-gradient(${trustColor} ${displayScore * 3.6}deg, var(--light-sage) 0deg)`,
        transition: 'none'
      }}
    >
      <div className="jm-trust-gauge-inner">
        <div className="jm-trust-score-value" style={{ color: trustColor }}>
          {score !== null ? displayScore : '—'}
        </div>
        <div className="jm-trust-score-label" style={{ color: trustColor }}>
          {level || 'N/A'}
        </div>
      </div>
    </div>
  );
}

function MissionSuccessBanner({ approvedApproval }: { approvedApproval: any }) {
  const trustBefore = approvedApproval?.trust_score_before ?? 64;
  const trustAfter = approvedApproval?.trust_score_after ?? 95;
  const etaBefore = approvedApproval?.eta_before ?? 18.7;
  const etaAfter = approvedApproval?.eta_after ?? 13.8;

  return (
    <div className="jm-success-banner">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 32 }}>🎉</span>
        <div>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'white' }}>Emergency Corridor Successfully Recovered</h2>
          <p style={{ margin: '4px 0 0 0', fontSize: 12, opacity: 0.9, color: 'white' }}>
            The corridor has been stabilized and rerouted to bypass active traffic bottleneck segments.
          </p>
        </div>
      </div>
      
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <div className="jm-success-metric-card">
          <div style={{ fontSize: 9, opacity: 0.8, textTransform: 'uppercase', fontWeight: 600, color: 'white' }}>Trust Score</div>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2, color: 'white' }}>
            {trustBefore} <span style={{ fontSize: 11, opacity: 0.7 }}>→</span> {trustAfter}
          </div>
        </div>

        <div className="jm-success-metric-card">
          <div style={{ fontSize: 9, opacity: 0.8, textTransform: 'uppercase', fontWeight: 600, color: 'white' }}>Corridor ETA</div>
          <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2, color: 'white' }}>
            {typeof etaBefore === 'number' ? etaBefore.toFixed(1) : etaBefore}m <span style={{ fontSize: 11, opacity: 0.7 }}>→</span> {typeof etaAfter === 'number' ? etaAfter.toFixed(1) : etaAfter}m
          </div>
        </div>

        <div className="jm-success-metric-card" style={{ background: 'white', color: 'var(--forest-green)' }}>
          <div style={{ fontSize: 9, opacity: 0.8, textTransform: 'uppercase', fontWeight: 700 }}>Corridor Status</div>
          <div style={{ fontSize: 11, fontWeight: 800, marginTop: 4, letterSpacing: 0.3, color: 'var(--forest-green)' }}>
            STABILIZED
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, loadFromStorage, logout } = useAuthStore();
  const store = useMissionStore();

  const [origin, setOrigin] = useState<{ name: string; lat: number; lng: number } | null>(null);
  const [destination, setDestination] = useState<{ name: string; lat: number; lng: number } | null>(null);
  const [creating, setCreating] = useState(false);
  const [starting, setStarting] = useState(false);
  const [approving, setApproving] = useState<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const role = user?.role || 'dispatcher';

  // Auth check
  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  useEffect(() => {
    if (!isAuthenticated) router.push('/login');
  }, [isAuthenticated, router]);

  // WebSocket handler
  const handleWSEvent = useCallback((event: WSEvent) => {
    const state = useMissionStore.getState();
    const missionId = event.mission_id;
    if (missionId && (!state.currentMission || state.currentMission.id !== missionId)) {
      // Auto-load details of new mission in realtime
      missionApi.get(missionId).then((m) => {
        state.setCurrentMission(m);
        state.setIsRunning(m.status !== 'completed' && m.status !== 'failed');
        
        missionApi.getRoutes(missionId).then(routes => state.setRoutes(routes)).catch(() => {});
        missionApi.getActivities(missionId).then(acts => state.setActivities(acts)).catch(() => {});
        missionApi.getMCPCalls(missionId).then(calls => state.setMCPCalls(calls)).catch(() => {});
        approvalApi.list().then(approvals => {
          state.setApprovals(approvals.filter(a => a.mission_id === missionId));
        }).catch(() => {});
        incidentApi.list(undefined, missionId).then(res => {
          state.setIncidents(res.incidents);
        }).catch(() => {});
      }).catch(() => {});
    }

    state.handleWSEvent(event);

    // Query routes on demand when generated or approved
    const activeMissionId = missionId || state.currentMission?.id;
    if (activeMissionId) {
      if (
        event.type === 'route_generated' ||
        (event.type === 'agent_completed' && event.agent_name === 'route_intelligence') ||
        event.type === 'recovery_recommended' ||
        (event.type === 'approval_resolved' && event.action === 'approved')
      ) {
        missionApi.getRoutes(activeMissionId).then(routes => state.setRoutes(routes)).catch(() => {});
      }
    }
  }, []);

  // Connect WebSocket to global stream on mount
  const connectWS = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    wsRef.current = createGlobalWebSocket(handleWSEvent);
  }, [handleWSEvent]);

  // Load system health & synchronize active mission
  useEffect(() => {
    systemApi.getHealth().then((health) => {
      const state = useMissionStore.getState();
      state.setAgentStates(health.agents);
      state.setMCPServerStates(health.mcp_servers);
      state.setSystemStatus(health.system_status);

      if (health.active_mission) {
        const activeMission = health.active_mission;
        state.setCurrentMission(activeMission);
        state.setIsRunning(activeMission.status !== 'completed' && activeMission.status !== 'failed');

        if (activeMission.origin_lat && activeMission.origin_lng) {
          setOrigin({
            name: activeMission.origin_name,
            lat: activeMission.origin_lat,
            lng: activeMission.origin_lng,
          });
        }
        if (activeMission.destination_lat && activeMission.destination_lng) {
          setDestination({
            name: activeMission.destination_name,
            lat: activeMission.destination_lat,
            lng: activeMission.destination_lng,
          });
        }

        const mid = activeMission.id;
        missionApi.getRoutes(mid).then(routes => state.setRoutes(routes)).catch(() => {});
        missionApi.getActivities(mid).then(acts => state.setActivities(acts)).catch(() => {});
        missionApi.getMCPCalls(mid).then(calls => state.setMCPCalls(calls)).catch(() => {});
        approvalApi.list().then(approvals => {
          state.setApprovals(approvals.filter(a => a.mission_id === mid));
        }).catch(() => {});
        incidentApi.list(undefined, mid).then(res => {
          state.setIncidents(res.incidents);
        }).catch(() => {});

        if (activeMission.trust_score !== null) {
          state.updateTrustScore(
            activeMission.trust_score,
            activeMission.trust_level || 'healthy',
            activeMission.corridor_health || 100,
            activeMission.eta_confidence || 100,
            {
              congestion: activeMission.congestion_factor ?? 100,
              route_stability: activeMission.route_stability_factor ?? 100,
              traffic_volatility: activeMission.traffic_volatility_factor ?? 100,
              corridor_continuity: activeMission.corridor_continuity_factor ?? 100,
              eta_confidence: activeMission.eta_confidence_factor ?? 100,
            }
          );
        }
      }
    }).catch(() => {});

    connectWS();
  }, [connectWS]);

  // Create Mission
  const handleCreateMission = async () => {
    if (!origin || !destination) return;
    setCreating(true);
    try {
      const mission = await missionApi.create({
        origin_name: origin.name,
        origin_lat: origin.lat,
        origin_lng: origin.lng,
        destination_name: destination.name,
        destination_lat: destination.lat,
        destination_lng: destination.lng,
      });
      store.reset();
      store.setCurrentMission(mission);
    } catch (err) {
      console.error('Failed to create mission:', err);
    } finally {
      setCreating(false);
    }
  };

  // Start Mission
  const handleStartMission = async () => {
    if (!store.currentMission) return;
    setStarting(true);
    try {
      await missionApi.start(store.currentMission.id);
      store.setIsRunning(true);
      // Already connected to global websocket, no reconnect needed
    } catch (err) {
      console.error('Failed to start mission:', err);
    } finally {
      setStarting(false);
    }
  };

  // Approve/Reject
  const handleApproval = async (approvalId: number, action: 'approve' | 'reject') => {
    setApproving(approvalId);
    try {
      if (action === 'approve') {
        await approvalApi.approve(approvalId);
      } else {
        await approvalApi.reject(approvalId);
      }
      store.updateApproval(approvalId, action === 'approve' ? 'approved' : 'rejected');
    } catch (err) {
      console.error(`Failed to ${action}:`, err);
    } finally {
      setApproving(null);
    }
  };

  // Cleanup
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  if (!isAuthenticated || !user) return null;

  const mission = store.currentMission;
  const pendingApprovals = store.approvals.filter(a => a.status === 'pending');
  const latestApproval = store.approvals.length > 0 ? store.approvals[store.approvals.length - 1] : null;

  // Trust score display
  const trustColor = store.trustLevel === 'excellent' ? 'var(--trust-excellent)'
    : store.trustLevel === 'healthy' ? 'var(--trust-healthy)'
    : store.trustLevel === 'warning' ? 'var(--trust-warning)'
    : store.trustLevel === 'critical' ? 'var(--trust-critical)'
    : 'var(--warm-gray)';

  return (
    <div style={{ minHeight: '100vh', background: 'var(--soft-beige)' }}>
      {/* Navbar */}
      <nav style={{
        background: 'var(--forest-green)',
        color: 'white',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'rgba(255,255,255,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <div>
            <span style={{ fontWeight: 700, fontSize: 18 }}>JeevanMarg</span>
            <span style={{ fontSize: 11, opacity: 0.7, marginLeft: 8 }}>Self-Healing Emergency Corridor</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* System Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span className={`jm-status-dot jm-status-dot-${store.systemStatus === 'online' ? 'green' : 'red'} jm-status-dot-pulse`} />
            System {store.systemStatus}
          </div>

          {/* Role Badge */}
          <span className={getRoleBadgeClass(role)}>
            {role === 'dispatcher' ? '📡' : role === 'operator' ? '🔧' : '⚙️'} {role}
          </span>

          {/* User & Logout */}
          <span style={{ fontSize: 13 }}>{user.full_name}</span>
          <button
            onClick={logout}
            style={{
              background: 'rgba(255,255,255,0.15)',
              border: 'none', color: 'white', padding: '6px 12px',
              borderRadius: 6, cursor: 'pointer', fontSize: 12,
            }}
          >
            Sign Out
          </button>
        </div>
      </nav>

      {/* Dashboard */}
      <div className="jm-dashboard-grid">
        {/* Header: Mission Control */}
        <div className="jm-dashboard-header">
          {mission && mission.status === 'completed' && (
            <MissionSuccessBanner approvedApproval={latestApproval} />
          )}

          <div className="jm-card" style={{ padding: '16px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              {/* Location inputs */}
              {canView(role, 'mission_create') && (
                <>
                  <LocationInput
                    label="Origin"
                    icon="📍"
                    placeholder="Search origin location..."
                    value={origin}
                    onChange={setOrigin}
                  />
                  <span style={{ fontSize: 20, color: 'var(--sage-green)' }}>→</span>
                  <LocationInput
                    label="Destination"
                    icon="🏥"
                    placeholder="Search destination..."
                    value={destination}
                    onChange={setDestination}
                  />
                  <button
                    className="jm-btn jm-btn-primary"
                    onClick={handleCreateMission}
                    disabled={!origin || !destination || creating}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    {creating ? '⏳ Creating...' : '📋 Create Mission'}
                  </button>
                </>
              )}

              {/* Start button */}
              {mission && mission.status === 'created' && canView(role, 'mission_create') && (
                <button
                  className="jm-btn jm-btn-success"
                  onClick={handleStartMission}
                  disabled={starting || store.isRunning}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  {starting ? '⏳ Starting...' : '🚀 Start Mission'}
                </button>
              )}

              {/* Mission Status */}
              {mission && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginLeft: 'auto' }}>
                  <span className="jm-badge jm-badge-green" style={{ fontSize: 11 }}>
                    {mission.mission_code}
                  </span>
                  <span className={`jm-badge ${
                    mission.status === 'completed' ? 'jm-badge-green' :
                    mission.status === 'degraded' || mission.status === 'failed' ? 'jm-badge-critical' :
                    mission.status === 'awaiting_approval' ? 'jm-badge-warning' :
                    'jm-badge-olive'
                  }`}>
                    {mission.status === 'completed' ? 'MISSION STABILIZED' : mission.status.replace(/_/g, ' ').toUpperCase()}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Map */}
        <div className="jm-dashboard-map">
          <MapSection
            routes={store.routes}
            origin={origin || (mission ? { lat: mission.origin_lat, lng: mission.origin_lng, name: mission.origin_name } : undefined)}
            destination={destination || (mission ? { lat: mission.destination_lat, lng: mission.destination_lng, name: mission.destination_name } : undefined)}
            incidents={store.incidents}
            missionStatus={mission?.status}
            trustScore={store.trustScore}
            approvalStatus={latestApproval?.status}
          />
        </div>

        {/* Sidebar */}
        <div className="jm-dashboard-sidebar">
          {/* Trust Score Gauge */}
          {canView(role, 'trust') && (
            <div className="jm-card" style={{ textAlign: 'center' }}>
              <div className="jm-card-header">
                <span className="jm-card-title">🛡️ Corridor Trust Score</span>
              </div>
              <TrustScoreGauge score={store.trustScore} level={store.trustLevel} />

              {/* Factor breakdown */}
              {Object.keys(store.trustFactors).length > 0 && (
                <div style={{ marginTop: 16, textAlign: 'left' }}>
                  {Object.entries(store.trustFactors).map(([key, val]) => (
                    <div key={key} style={{ marginBottom: 8 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                        <span style={{ color: 'var(--earth-brown)', textTransform: 'capitalize' }}>
                          {key.replace(/_/g, ' ')}
                        </span>
                        <span style={{ fontWeight: 600, color: val < 50 ? 'var(--trust-critical)' : 'var(--forest-green)' }}>
                          {Math.round(val)}%
                        </span>
                      </div>
                      <div className="jm-progress">
                        <div className="jm-progress-bar" style={{
                          width: `${val}%`,
                          background: val >= 70 ? 'var(--olive-green)' : val >= 50 ? 'var(--trust-warning)' : 'var(--trust-critical)',
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Incident Simulator */}
          {canView(role, 'incidents') && (
            <IncidentSimulator />
          )}

          {/* System Health */}
          {canView(role, 'system') && (
            <div className="jm-card">
              <div className="jm-card-header">
                <span className="jm-card-title">⚡ System Health</span>
                <span className={`jm-badge ${store.systemStatus === 'online' ? 'jm-badge-green' : 'jm-badge-critical'}`}>
                  {store.systemStatus}
                </span>
              </div>

              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--earth-brown)', marginBottom: 6, textTransform: 'uppercase' }}>
                Agents
              </div>
              {AGENTS.map(a => {
                const agentState = store.agentStates.find(s => s.name === a.name);
                const state = agentState?.state || 'idle';
                return (
                  <div key={a.name} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '6px 0', fontSize: 12,
                  }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: a.color, display: 'inline-block' }} />
                      {a.display}
                    </span>
                    <span className={`jm-badge ${state === 'running' ? 'jm-badge-olive' : state === 'completed' ? 'jm-badge-green' : state === 'failed' ? 'jm-badge-critical' : 'jm-badge-gray'}`}
                      style={{ fontSize: 10, padding: '2px 6px' }}>
                      {state}
                    </span>
                  </div>
                );
              })}

              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--earth-brown)', margin: '12px 0 6px', textTransform: 'uppercase' }}>
                MCP Servers
              </div>
              {MCP_SERVERS.map(s => {
                const serverState = store.mcpServerStates.find(ms => ms.name === s.name);
                const status = serverState?.status || 'disconnected';
                return (
                  <div key={s.name} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '4px 0', fontSize: 12,
                  }}>
                    <span>{s.icon} {s.display}</span>
                    <span className={`jm-badge ${status === 'connected' ? 'jm-badge-green' : 'jm-badge-gray'}`}
                      style={{ fontSize: 10, padding: '2px 6px' }}>
                      {status}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Bottom Left: Timeline + Agent Activity */}
        <div className="jm-dashboard-bottom-left">
          {/* Mission Timeline */}
          {canView(role, 'timeline') && <MissionTimeline />}

          {/* Agent Activity */}
          {canView(role, 'agents') && (
            <div className="jm-card" style={{ maxHeight: 500, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div className="jm-card-header">
                <span className="jm-card-title">🤖 Agent Activity</span>
                <span className="jm-badge jm-badge-gray">{store.activities.length}</span>
              </div>
              <div style={{ overflowY: 'auto', flex: 1 }}>
                <div className="jm-timeline">
                  {store.activities.slice().reverse().slice(0, 30).map((activity, i) => {
                    const agent = AGENTS.find(a => a.name === activity.agent_name);
                    const color = agent?.color || 'var(--warm-gray)';
                    return (
                      <div key={activity.id || i} className="jm-timeline-item">
                        <div className="jm-timeline-dot" style={{ background: color }} />
                        <div style={{ fontSize: 12, fontWeight: 600, color }}>
                          {agent?.display || activity.agent_name}
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--forest-green)', marginTop: 2 }}>
                          {activity.action}
                        </div>
                        {activity.result && (
                          <div style={{ fontSize: 11, color: 'var(--earth-brown)', marginTop: 2 }}>
                            {activity.result}
                          </div>
                        )}
                        {activity.reasoning && (
                          <div style={{ fontSize: 11, color: 'var(--warm-gray)', marginTop: 2, fontStyle: 'italic' }}>
                            {activity.reasoning.length > 200
                              ? activity.reasoning.substring(0, 200) + '...'
                              : activity.reasoning}
                          </div>
                        )}
                        {activity.timestamp && (
                          <div style={{ fontSize: 10, color: 'var(--warm-gray)', marginTop: 3 }}>
                            {new Date(activity.timestamp).toLocaleTimeString()}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {store.activities.length === 0 && (
                    <p style={{ color: 'var(--warm-gray)', fontSize: 12, textAlign: 'center', padding: 20 }}>
                      Start a mission to see agent activity
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Full: Recovery + MCP + Approvals */}
        <div className="jm-dashboard-bottom-full">
          {/* MCP Activity */}
          {canView(role, 'mcp') && (
            <div className="jm-card" style={{ maxHeight: 400, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div className="jm-card-header">
                <span className="jm-card-title">🔧 MCP Tool Calls</span>
                <span className="jm-badge jm-badge-gray">{store.mcpCalls.length}</span>
              </div>
              <div style={{ overflowY: 'auto', flex: 1 }}>
                <table className="jm-table">
                  <thead>
                    <tr>
                      <th>Server</th>
                      <th>Tool</th>
                      <th>Latency</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {store.mcpCalls.slice().reverse().slice(0, 20).map((call, i) => {
                      const server = MCP_SERVERS.find(s => s.name === call.server_name);
                      return (
                        <tr key={call.id || i}>
                          <td style={{ fontSize: 12 }}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                              {server?.icon || '🔧'} {server?.display || call.server_name}
                            </span>
                          </td>
                          <td style={{ fontSize: 12, fontFamily: 'monospace' }}>{call.tool_name}</td>
                          <td style={{ fontSize: 12 }}>{call.latency_ms || '—'} ms</td>
                          <td>
                            <span className={`jm-badge ${call.status === 'success' ? 'jm-badge-green' : 'jm-badge-critical'}`}
                              style={{ fontSize: 10, padding: '2px 6px' }}>
                              {call.status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {store.mcpCalls.length === 0 && (
                  <p style={{ color: 'var(--warm-gray)', fontSize: 12, textAlign: 'center', padding: 20 }}>
                    No MCP calls yet
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Human-in-the-Loop Approvals */}
          {(canView(role, 'approvals') || canView(role, 'recovery')) && (
            <div className="jm-card" style={{ maxHeight: 400, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div className="jm-card-header">
                <span className="jm-card-title">🧑‍⚖️ Human-in-the-Loop</span>
                {pendingApprovals.length > 0 && (
                  <span className="jm-badge jm-badge-warning" style={{ animation: 'pulse-green 2s infinite' }}>
                    {pendingApprovals.length} pending
                  </span>
                )}
              </div>
              <div style={{ overflowY: 'auto', flex: 1 }}>
                {store.approvals.slice().reverse().map((approval, i) => (
                  <div key={approval.id || i} className="animate-slide-in" style={{
                    padding: 14, borderRadius: 10, marginBottom: 10,
                    background: approval.status === 'pending' ? '#FFFBE8' : approval.status === 'approved' ? '#F0F8E8' : '#FDE8E4',
                    border: `1px solid ${approval.status === 'pending' ? '#E6D88D' : approval.status === 'approved' ? 'var(--border-green)' : '#E8B4A8'}`,
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--forest-green)', marginBottom: 6 }}>
                      {approval.title}
                    </div>

                    {approval.description && (
                      <div style={{ fontSize: 11, color: 'var(--earth-brown)', marginBottom: 8, lineHeight: 1.5 }}>
                        {approval.description.length > 300
                          ? approval.description.substring(0, 300) + '...'
                          : approval.description}
                      </div>
                    )}

                    {/* Trust score comparison */}
                    {approval.trust_score_before !== null && approval.trust_score_after !== null && (
                      <div style={{
                        display: 'flex', gap: 16, marginBottom: 10,
                        padding: '8px 12px', borderRadius: 6,
                        background: 'rgba(255,255,255,0.7)',
                      }}>
                        <div style={{ flex: 1, textAlign: 'center' }}>
                          <div style={{ fontSize: 10, color: 'var(--trust-critical)', fontWeight: 600 }}>BEFORE</div>
                          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--trust-critical)' }}>
                            {Math.round(approval.trust_score_before)}
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', fontSize: 18, color: 'var(--sage-green)' }}>→</div>
                        <div style={{ flex: 1, textAlign: 'center' }}>
                          <div style={{ fontSize: 10, color: 'var(--trust-excellent)', fontWeight: 600 }}>AFTER</div>
                          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--trust-excellent)' }}>
                            {Math.round(approval.trust_score_after)}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* ETA comparison */}
                    {approval.eta_before !== null && approval.eta_after !== null && (
                      <div style={{ fontSize: 11, color: 'var(--earth-brown)', marginBottom: 8 }}>
                        ETA: {approval.eta_before} min → {approval.eta_after} min
                      </div>
                    )}

                    {/* Action buttons */}
                    {approval.status === 'pending' && canView(role, 'approvals') && (
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          className="jm-btn jm-btn-success"
                          style={{ flex: 1, padding: '8px 12px', fontSize: 12 }}
                          disabled={approving === approval.id}
                          onClick={() => handleApproval(approval.id, 'approve')}
                        >
                          {approving === approval.id ? '...' : '✅ Approve'}
                        </button>
                        <button
                          className="jm-btn jm-btn-danger"
                          style={{ flex: 1, padding: '8px 12px', fontSize: 12 }}
                          disabled={approving === approval.id}
                          onClick={() => handleApproval(approval.id, 'reject')}
                        >
                          ❌ Reject
                        </button>
                      </div>
                    )}

                    {/* Status badges */}
                    {approval.status !== 'pending' && (
                      <span className={`jm-badge ${approval.status === 'approved' ? 'jm-badge-green' : 'jm-badge-critical'}`}>
                        {approval.status === 'approved' ? '✅ Approved' : '❌ Rejected'}
                      </span>
                    )}
                  </div>
                ))}

                {store.approvals.length === 0 && (
                  <p style={{ color: 'var(--warm-gray)', fontSize: 12, textAlign: 'center', padding: 20 }}>
                    No approval requests yet
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
