'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore, useMissionStore } from '@/lib/store';
import {
  missionApi, approvalApi, systemApi, createMissionWebSocket,
  type WSEvent, type MissionResponse,
} from '@/lib/api';
import dynamic from 'next/dynamic';

const MapSection = dynamic(() => import('@/components/MapSection'), { ssr: false, loading: () => <div className="jm-card" style={{ minHeight: 420, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><p style={{ color: 'var(--warm-gray)' }}>Loading map...</p></div> });

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, loadFromStorage, logout } = useAuthStore();
  const store = useMissionStore();
  const wsRef = useRef<WebSocket | null>(null);
  const [starting, setStarting] = useState(false);
  const activitiesEndRef = useRef<HTMLDivElement>(null);

  // Auth check
  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  useEffect(() => {
    if (!isAuthenticated) router.push('/login');
  }, [isAuthenticated, router]);

  // Load system health on mount
  useEffect(() => {
    systemApi.getHealth().then((health) => {
      store.setAgentStates(health.agents);
      store.setMCPServerStates(health.mcp_servers);
      store.setSystemStatus(health.system_status);
    }).catch(() => {});
    // Load existing approvals
    approvalApi.list().then(store.setApprovals).catch(() => {});
  }, []);

  // Auto-scroll activities
  useEffect(() => {
    activitiesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [store.activities]);

  // WebSocket connection
  const connectWS = useCallback((missionId: number) => {
    if (wsRef.current) wsRef.current.close();
    wsRef.current = createMissionWebSocket(
      missionId,
      (event: WSEvent) => store.handleWSEvent(event),
      () => console.error('WS error'),
      () => console.log('WS closed'),
    );
  }, [store]);

  // Start mission
  const handleStartMission = async () => {
    setStarting(true);
    store.reset();

    try {
      // Create mission with demo coordinates
      const mission = await missionApi.create({
        origin_name: 'Connaught Place, Delhi',
        origin_lat: 28.6315,
        origin_lng: 77.2167,
        destination_name: 'AIIMS Hospital, Delhi',
        destination_lat: 28.5672,
        destination_lng: 77.2100,
      });

      store.setCurrentMission(mission);
      store.setIsRunning(true);

      // Connect WebSocket
      connectWS(mission.id);

      // Start mission
      await missionApi.start(mission.id);
    } catch (err) {
      console.error('Failed to start mission:', err);
      store.setIsRunning(false);
    } finally {
      setStarting(false);
    }
  };

  // Approve/Reject
  const handleApprove = async (approvalId: number) => {
    try {
      await approvalApi.approve(approvalId);
      const updated = await approvalApi.list();
      store.setApprovals(updated);
      // Refresh mission
      if (store.currentMission) {
        const m = await missionApi.get(store.currentMission.id);
        store.setCurrentMission(m);
        if (m.trust_score) {
          store.updateTrustScore(
            m.trust_score,
            m.trust_level || 'unknown',
            m.corridor_health || 0,
            m.eta_confidence || 0,
            {},
          );
        }
      }
    } catch (err) { console.error(err); }
  };

  const handleReject = async (approvalId: number) => {
    try {
      await approvalApi.reject(approvalId);
      const updated = await approvalApi.list();
      store.setApprovals(updated);
    } catch (err) { console.error(err); }
  };

  const agentColor = (name: string): string => {
    const colors: Record<string, string> = {
      emergency_coordinator: 'var(--agent-coordinator)',
      route_intelligence: 'var(--agent-route)',
      traffic_intelligence: 'var(--agent-traffic)',
      trust_score: 'var(--agent-trust)',
      recovery: 'var(--agent-recovery)',
      system: 'var(--warm-gray)',
    };
    return colors[name] || 'var(--sage-green)';
  };

  const trustColor = (level: string | null): string => {
    const colors: Record<string, string> = {
      excellent: 'var(--trust-excellent)',
      healthy: 'var(--trust-healthy)',
      warning: 'var(--trust-warning)',
      critical: 'var(--trust-critical)',
    };
    return colors[level || ''] || 'var(--warm-gray)';
  };

  const stateColor = (state: string): string => {
    const colors: Record<string, string> = {
      idle: 'var(--warm-gray)',
      running: 'var(--olive-green)',
      waiting: 'var(--trust-warning)',
      completed: 'var(--forest-green)',
      failed: 'var(--trust-critical)',
      connected: 'var(--olive-green)',
      disconnected: 'var(--trust-critical)',
    };
    return colors[state] || 'var(--warm-gray)';
  };

  const pendingApprovals = store.approvals.filter(a => a.status === 'pending');
  const missionApprovals = store.currentMission
    ? store.approvals.filter(a => a.mission_id === store.currentMission!.id)
    : [];

  if (!isAuthenticated) return null;

  return (
    <div style={{ minHeight: '100vh', background: 'var(--soft-beige)' }}>
      {/* Top Nav */}
      <nav style={{
        background: 'var(--forest-green)', color: 'white', padding: '0 20px',
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          <span style={{ fontWeight: 700, fontSize: 18 }}>JeevanMarg</span>
          <span style={{ fontSize: 12, opacity: 0.7, marginLeft: 8 }}>Emergency Corridor Agent</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 13, opacity: 0.8 }}>
            {user?.full_name} ({user?.role})
          </span>
          <button onClick={logout} className="jm-btn" style={{
            background: 'rgba(255,255,255,0.15)', color: 'white',
            padding: '6px 14px', fontSize: 13,
          }}>
            Sign Out
          </button>
        </div>
      </nav>

      {/* Dashboard Grid */}
      <div className="jm-dashboard-grid">
        {/* Section 1: Mission Control Header */}
        <div className="jm-dashboard-header">
          <div className="jm-card" style={{ padding: '16px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
                {/* System Status */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className={`jm-status-dot ${store.systemStatus === 'online' ? 'jm-status-dot-green jm-status-dot-pulse' : 'jm-status-dot-yellow'}`} />
                  <span style={{ fontSize: 13, fontWeight: 600 }}>
                    System: {store.systemStatus.toUpperCase()}
                  </span>
                </div>

                {/* Agent Status */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, color: 'var(--warm-gray)' }}>Agents:</span>
                  {store.agentStates.map(a => (
                    <span key={a.name} title={`${a.display_name}: ${a.state}`}
                      className="jm-status-dot" style={{ background: stateColor(a.state) }} />
                  ))}
                </div>

                {/* MCP Status */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, color: 'var(--warm-gray)' }}>MCP:</span>
                  {store.mcpServerStates.map(s => (
                    <span key={s.name} title={`${s.display_name}: ${s.status}`}
                      className="jm-status-dot" style={{ background: stateColor(s.status) }} />
                  ))}
                </div>

                {/* Mission */}
                {store.currentMission && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className={`jm-badge ${store.currentMission.status === 'completed' ? 'jm-badge-green' : store.currentMission.status === 'running' ? 'jm-badge-olive' : store.currentMission.status === 'degraded' || store.currentMission.status === 'awaiting_approval' ? 'jm-badge-warning' : 'jm-badge-gray'}`}>
                      {store.currentMission.mission_code} • {store.currentMission.status}
                    </span>
                  </div>
                )}
              </div>

              {/* Start Mission Button */}
              <button
                onClick={handleStartMission}
                disabled={starting || store.isRunning}
                className="jm-btn jm-btn-primary jm-btn-lg"
                style={{ minWidth: 220 }}
              >
                {starting ? '⏳ Creating Mission...' : store.isRunning ? '🔄 Mission Running...' : '🚑 Start Emergency Mission'}
              </button>
            </div>
          </div>
        </div>

        {/* Section 2: Map */}
        <div className="jm-dashboard-map">
          <MapSection
            routes={store.routes}
            origin={store.currentMission ? { lat: store.currentMission.origin_lat, lng: store.currentMission.origin_lng, name: store.currentMission.origin_name } : undefined}
            destination={store.currentMission ? { lat: store.currentMission.destination_lat, lng: store.currentMission.destination_lng, name: store.currentMission.destination_name } : undefined}
          />
        </div>

        {/* Sidebar */}
        <div className="jm-dashboard-sidebar">
          {/* Section 3: Trust Score Panel */}
          <div className="jm-card">
            <div className="jm-card-header">
              <span className="jm-card-title">🛡️ Corridor Trust Score</span>
              {store.trustLevel && (
                <span className={`jm-badge ${store.trustLevel === 'excellent' ? 'jm-badge-green' : store.trustLevel === 'healthy' ? 'jm-badge-olive' : store.trustLevel === 'warning' ? 'jm-badge-warning' : 'jm-badge-critical'}`}>
                  {store.trustLevel}
                </span>
              )}
            </div>

            {/* Gauge */}
            <div className="jm-trust-gauge" style={{
              background: `conic-gradient(${trustColor(store.trustLevel)} ${(store.trustScore || 0) * 3.6}deg, var(--light-sage) 0deg)`,
            }}>
              <div className="jm-trust-gauge-inner">
                <span className="jm-trust-score-value" style={{ color: trustColor(store.trustLevel) }}>
                  {store.trustScore !== null ? Math.round(store.trustScore) : '--'}
                </span>
                <span className="jm-trust-score-label" style={{ color: trustColor(store.trustLevel) }}>
                  {store.trustLevel || 'Awaiting'}
                </span>
              </div>
            </div>

            {/* Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 16 }}>
              <div style={{ textAlign: 'center', padding: 8, background: 'var(--light-sage)', borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: 'var(--warm-gray)' }}>Corridor Health</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--forest-green)' }}>
                  {store.corridorHealth !== null ? `${Math.round(store.corridorHealth)}%` : '--'}
                </div>
              </div>
              <div style={{ textAlign: 'center', padding: 8, background: 'var(--light-sage)', borderRadius: 8 }}>
                <div style={{ fontSize: 11, color: 'var(--warm-gray)' }}>ETA Confidence</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--forest-green)' }}>
                  {store.etaConfidence !== null ? `${Math.round(store.etaConfidence)}%` : '--'}
                </div>
              </div>
            </div>

            {/* Factor Bars */}
            {Object.keys(store.trustFactors).length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 11, color: 'var(--warm-gray)', marginBottom: 8, textTransform: 'uppercase' }}>Factor Breakdown</div>
                {Object.entries(store.trustFactors).map(([key, value]) => (
                  <div key={key} style={{ marginBottom: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                      <span style={{ color: 'var(--earth-brown)', textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</span>
                      <span style={{ fontWeight: 600, color: 'var(--forest-green)' }}>{Math.round(value)}%</span>
                    </div>
                    <div className="jm-progress">
                      <div className="jm-progress-bar" style={{
                        width: `${value}%`,
                        background: value >= 70 ? 'var(--olive-green)' : value >= 50 ? 'var(--trust-warning)' : 'var(--trust-critical)',
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Section 8: System Health */}
          <div className="jm-card">
            <div className="jm-card-header">
              <span className="jm-card-title">⚙️ System Health</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {store.agentStates.map(a => (
                <div key={a.name} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '8px 12px', background: 'var(--light-sage)', borderRadius: 8,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="jm-status-dot" style={{ background: stateColor(a.state) }} />
                    <span style={{ fontSize: 12, fontWeight: 500 }}>{a.display_name}</span>
                  </div>
                  <span className={`jm-badge ${a.state === 'completed' ? 'jm-badge-green' : a.state === 'running' ? 'jm-badge-olive' : a.state === 'failed' ? 'jm-badge-critical' : 'jm-badge-gray'}`}
                    style={{ fontSize: 10, padding: '2px 8px' }}>
                    {a.state}
                  </span>
                </div>
              ))}
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--warm-gray)', textTransform: 'uppercase' }}>MCP Servers</div>
              {store.mcpServerStates.map(s => (
                <div key={s.name} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 12px', background: 'var(--light-sage)', borderRadius: 8,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="jm-status-dot" style={{ background: stateColor(s.status) }} />
                    <span style={{ fontSize: 12 }}>{s.display_name}</span>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--warm-gray)' }}>{s.tools_count} tools</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom sections */}
        <div className="jm-dashboard-bottom-left">
          {/* Section 4: Agent Activity Timeline */}
          <div className="jm-card" style={{ maxHeight: 400, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div className="jm-card-header">
              <span className="jm-card-title">🤖 Agent Activity</span>
              <span className="jm-badge jm-badge-gray">{store.activities.length}</span>
            </div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {store.activities.length === 0 ? (
                <p style={{ color: 'var(--warm-gray)', fontSize: 13, textAlign: 'center', padding: 20 }}>
                  Start a mission to see agent activity
                </p>
              ) : (
                <div className="jm-timeline">
                  {store.activities.map((a, i) => (
                    <div key={`${a.id}-${i}`} className="jm-timeline-item animate-slide-in">
                      <div className="jm-timeline-dot" style={{ background: agentColor(a.agent_name) }} />
                      <div style={{ fontSize: 10, color: 'var(--warm-gray)', marginBottom: 2 }}>
                        {a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : '--'}
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: agentColor(a.agent_name), marginBottom: 2 }}>
                        {a.agent_name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--forest-green)' }}>{a.action}</div>
                      {a.result && (
                        <div style={{ fontSize: 11, color: 'var(--earth-brown)', marginTop: 2, fontStyle: 'italic' }}>
                          {a.result.substring(0, 150)}{a.result.length > 150 ? '...' : ''}
                        </div>
                      )}
                      {a.reasoning && (
                        <div style={{ fontSize: 11, color: 'var(--warm-gray)', marginTop: 2, padding: '4px 8px', background: 'var(--light-sage)', borderRadius: 4 }}>
                          💭 {a.reasoning.substring(0, 200)}{a.reasoning.length > 200 ? '...' : ''}
                        </div>
                      )}
                    </div>
                  ))}
                  <div ref={activitiesEndRef} />
                </div>
              )}
            </div>
          </div>

          {/* Section 5: MCP Activity Monitor */}
          <div className="jm-card" style={{ maxHeight: 400, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <div className="jm-card-header">
              <span className="jm-card-title">🔌 MCP Activity</span>
              <span className="jm-badge jm-badge-gray">{store.mcpCalls.length}</span>
            </div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {store.mcpCalls.length === 0 ? (
                <p style={{ color: 'var(--warm-gray)', fontSize: 13, textAlign: 'center', padding: 20 }}>
                  MCP calls will appear here during mission execution
                </p>
              ) : (
                <table className="jm-table">
                  <thead>
                    <tr>
                      <th>Server</th>
                      <th>Tool</th>
                      <th>Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {store.mcpCalls.map((c, i) => (
                      <tr key={`${c.id}-${i}`} className="animate-slide-in">
                        <td>
                          <span className="jm-badge" style={{
                            background: c.server_name === 'traffic' ? '#E8F0D8' : c.server_name === 'route' ? '#D8E8C8' : c.server_name === 'hospital' ? '#FDE8E4' : '#E8F0E0',
                            color: c.server_name === 'hospital' ? 'var(--trust-critical)' : 'var(--forest-green)',
                            fontSize: 10,
                            padding: '2px 8px',
                          }}>
                            {c.server_name}
                          </span>
                        </td>
                        <td style={{ fontSize: 12, fontFamily: 'monospace' }}>{c.tool_name}</td>
                        <td style={{ fontSize: 12, color: 'var(--warm-gray)' }}>{c.latency_ms || 0}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        <div className="jm-dashboard-bottom-full">
          {/* Section 6: Recovery Recommendation Center */}
          <div className="jm-card">
            <div className="jm-card-header">
              <span className="jm-card-title">🔄 Recovery Recommendations</span>
            </div>
            {missionApprovals.length === 0 ? (
              <p style={{ color: 'var(--warm-gray)', fontSize: 13, textAlign: 'center', padding: 20 }}>
                Recovery recommendations will appear when corridor degrades
              </p>
            ) : (
              missionApprovals.map((a, i) => (
                <div key={`${a.id}-${i}`} className="animate-scale-in" style={{
                  padding: 16, background: 'var(--light-sage)', borderRadius: 8, marginBottom: 12,
                  border: a.status === 'pending' ? '2px solid var(--trust-warning)' : '1px solid var(--border-green)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 12 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0, color: 'var(--forest-green)' }}>
                      {a.title}
                    </h3>
                    <span className={`jm-badge ${a.status === 'pending' ? 'jm-badge-warning' : a.status === 'approved' ? 'jm-badge-green' : 'jm-badge-critical'}`}>
                      {a.status}
                    </span>
                  </div>

                  {/* Improvement metrics */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                    <div style={{ padding: 10, background: 'white', borderRadius: 8, textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--warm-gray)' }}>Trust Score</div>
                      <div style={{ fontSize: 16, fontWeight: 700 }}>
                        <span style={{ color: 'var(--trust-warning)' }}>{a.trust_score_before}</span>
                        <span style={{ margin: '0 6px', color: 'var(--warm-gray)' }}>→</span>
                        <span style={{ color: 'var(--trust-healthy)' }}>{a.trust_score_after}</span>
                      </div>
                    </div>
                    <div style={{ padding: 10, background: 'white', borderRadius: 8, textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--warm-gray)' }}>ETA (minutes)</div>
                      <div style={{ fontSize: 16, fontWeight: 700 }}>
                        <span style={{ color: 'var(--trust-warning)' }}>{a.eta_before}</span>
                        <span style={{ margin: '0 6px', color: 'var(--warm-gray)' }}>→</span>
                        <span style={{ color: 'var(--trust-healthy)' }}>{a.eta_after}</span>
                      </div>
                    </div>
                  </div>

                  {/* AI Explanation */}
                  {a.description && (
                    <div style={{ fontSize: 12, color: 'var(--earth-brown)', marginBottom: 12, lineHeight: 1.5 }}>
                      <strong>AI Analysis:</strong> {a.description}
                    </div>
                  )}

                  {/* Action Buttons */}
                  {a.status === 'pending' && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => handleApprove(a.id)} className="jm-btn jm-btn-success" style={{ flex: 1 }}>
                        ✅ Approve Route Change
                      </button>
                      <button onClick={() => handleReject(a.id)} className="jm-btn jm-btn-danger" style={{ flex: 1 }}>
                        ❌ Reject
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Section 7: Human-in-the-Loop Panel */}
          <div className="jm-card">
            <div className="jm-card-header">
              <span className="jm-card-title">👤 Human-in-the-Loop</span>
              {pendingApprovals.length > 0 && (
                <span className="jm-badge jm-badge-warning">{pendingApprovals.length} pending</span>
              )}
            </div>
            {pendingApprovals.length === 0 ? (
              <p style={{ color: 'var(--warm-gray)', fontSize: 13, textAlign: 'center', padding: 20 }}>
                No pending approvals. The system will request human input when corridor recovery is needed.
              </p>
            ) : (
              pendingApprovals.map((a, i) => (
                <div key={`${a.id}-${i}`} style={{
                  padding: 12, background: '#FFF8E8', borderRadius: 8, marginBottom: 8,
                  border: '1px solid var(--trust-warning)',
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--forest-green)', marginBottom: 4 }}>
                    ⚠️ {a.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--earth-brown)', marginBottom: 8 }}>
                    {a.approval_type === 'route_change' ? 'Route change approval required' : a.approval_type}
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => handleApprove(a.id)} className="jm-btn jm-btn-success" style={{ padding: '6px 14px', fontSize: 12 }}>
                      Approve
                    </button>
                    <button onClick={() => handleReject(a.id)} className="jm-btn jm-btn-danger" style={{ padding: '6px 14px', fontSize: 12 }}>
                      Reject
                    </button>
                  </div>
                </div>
              ))
            )}

            {/* Approval History */}
            {store.approvals.filter(a => a.status !== 'pending').length > 0 && (
              <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--light-sage)' }}>
                <div style={{ fontSize: 11, color: 'var(--warm-gray)', marginBottom: 8, textTransform: 'uppercase' }}>History</div>
                {store.approvals.filter(a => a.status !== 'pending').map((a, i) => (
                  <div key={`hist-${a.id}-${i}`} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '6px 10px', background: 'var(--light-sage)', borderRadius: 6, marginBottom: 4,
                  }}>
                    <span style={{ fontSize: 12, color: 'var(--forest-green)' }}>{a.title.substring(0, 40)}</span>
                    <span className={`jm-badge ${a.status === 'approved' ? 'jm-badge-green' : 'jm-badge-critical'}`}
                      style={{ fontSize: 10, padding: '2px 6px' }}>
                      {a.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
