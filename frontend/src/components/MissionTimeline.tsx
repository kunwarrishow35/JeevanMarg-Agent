'use client';

import { useMissionStore } from '@/lib/store';
import type { AgentActivityResponse, ApprovalResponse, IncidentResponse } from '@/lib/api';

interface MilestoneNode {
  icon: string;
  title: string;
  description: string;
  timestamp: string | null;
  color: string;
  completed: boolean;
}

function buildMilestones(
  activities: AgentActivityResponse[],
  approvals: ApprovalResponse[],
  incidents: IncidentResponse[],
  missionCode: string | null,
  missionStatus: string | null,
): MilestoneNode[] {
  const milestones: MilestoneNode[] = [];

  // 1. Mission Created
  const missionCreated = activities.find(a => a.agent_name === 'emergency_coordinator' && a.action?.includes('Starting'));
  if (missionCreated || missionCode) {
    milestones.push({
      icon: '🎯',
      title: 'Mission Created',
      description: missionCode
        ? `Emergency corridor mission ${missionCode} initiated.`
        : 'Emergency mission created.',
      timestamp: missionCreated?.timestamp || null,
      color: 'var(--forest-green)',
      completed: true,
    });
  }

  // 2. Route Generated
  const routeGen = activities.find(a => a.agent_name === 'route_intelligence' && a.agent_state === 'completed');
  if (routeGen) {
    milestones.push({
      icon: '🗺️',
      title: 'Route Generated',
      description: routeGen.result || 'Primary route calculated for emergency corridor.',
      timestamp: routeGen.timestamp,
      color: 'var(--agent-route)',
      completed: true,
    });
  }

  // 3. Traffic Incident Detected (from incidents or activities)
  const activeIncident = incidents.find(i => i.status === 'active');
  const trafficActivity = activities.find(a =>
    a.agent_name === 'traffic_intelligence' && a.agent_state === 'completed' &&
    (a.reasoning?.includes('Detected') || a.reasoning?.includes('incident') || a.reasoning?.includes('bottleneck'))
  );
  if (activeIncident) {
    milestones.push({
      icon: '🚨',
      title: 'Traffic Incident Detected',
      description: activeIncident.description ||
        `${activeIncident.incident_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} at ${activeIncident.location_name}. ${activeIncident.affected_lanes || 0} of ${activeIncident.total_lanes || 4} lanes affected.`,
      timestamp: activeIncident.created_at,
      color: 'var(--trust-critical)',
      completed: true,
    });
  } else if (trafficActivity && trafficActivity.reasoning?.includes('bottleneck')) {
    milestones.push({
      icon: '🚨',
      title: 'Traffic Degradation Detected',
      description: trafficActivity.reasoning?.substring(0, 200) || 'Traffic conditions have degraded.',
      timestamp: trafficActivity.timestamp,
      color: 'var(--trust-critical)',
      completed: true,
    });
  }

  // 4. Trust Score Degraded
  const trustDegraded = activities.find(a =>
    a.agent_name === 'trust_score' && a.agent_state === 'completed' &&
    a.result && parseFloat(a.result.match(/Trust Score: ([\d.]+)/)?.[1] || '100') < 70
  );
  if (trustDegraded) {
    const scoreMatch = trustDegraded.result?.match(/Trust Score: ([\d.]+)/);
    const score = scoreMatch ? scoreMatch[1] : '?';
    milestones.push({
      icon: '📉',
      title: 'Trust Score Degraded',
      description: `Corridor trust score dropped to ${score}/100. ${trustDegraded.reasoning?.substring(0, 150) || 'Recovery protocols activated.'}`,
      timestamp: trustDegraded.timestamp,
      color: 'var(--trust-warning)',
      completed: true,
    });
  }

  // 5. Recovery Agent Activated
  const recoveryStarted = activities.find(a => a.agent_name === 'recovery' && a.agent_state === 'running');
  if (recoveryStarted) {
    milestones.push({
      icon: '🔄',
      title: 'Recovery Agent Activated',
      description: recoveryStarted.reasoning || 'Recovery agent analyzing alternative corridors...',
      timestamp: recoveryStarted.timestamp,
      color: 'var(--agent-recovery)',
      completed: true,
    });
  }

  // 6. Alternative Route Generated
  const recoveryComplete = activities.find(a => a.agent_name === 'recovery' && a.agent_state === 'completed');
  if (recoveryComplete) {
    milestones.push({
      icon: '🛤️',
      title: 'Alternative Route Generated',
      description: recoveryComplete.result || 'Recovery route calculated avoiding congested segments.',
      timestamp: recoveryComplete.timestamp,
      color: 'var(--olive-green)',
      completed: true,
    });
  }

  // 7. Human Approval
  const pendingApproval = approvals.find(a => a.status === 'pending');
  const approvedApproval = approvals.find(a => a.status === 'approved');
  const rejectedApproval = approvals.find(a => a.status === 'rejected');

  if (approvedApproval) {
    milestones.push({
      icon: '✅',
      title: 'Human Approval Granted',
      description: `Route change approved. Trust score expected to recover to ${approvedApproval.trust_score_after}/100.`,
      timestamp: approvedApproval.reviewed_at || approvedApproval.created_at,
      color: 'var(--forest-green)',
      completed: true,
    });
  } else if (rejectedApproval) {
    milestones.push({
      icon: '❌',
      title: 'Human Approval Rejected',
      description: 'Route change was rejected by operator. Original degraded route maintained.',
      timestamp: rejectedApproval.reviewed_at || rejectedApproval.created_at,
      color: 'var(--trust-critical)',
      completed: true,
    });
  } else if (pendingApproval) {
    milestones.push({
      icon: '⏳',
      title: 'Awaiting Human Approval',
      description: pendingApproval.title || 'Route change recommendation pending operator review.',
      timestamp: pendingApproval.created_at,
      color: 'var(--trust-warning)',
      completed: false,
    });
  }

  // 8. Mission Recovered / Completed
  if (missionStatus === 'completed' && approvedApproval) {
    milestones.push({
      icon: '🏁',
      title: 'Mission Stabilized',
      description: `Emergency corridor recovered. Trust score restored from ${approvedApproval.trust_score_before || 64} to ${approvedApproval.trust_score_after || 95}/100. ETA optimized from ${approvedApproval.eta_before || 18.7}m to ${approvedApproval.eta_after || 13.8}m.`,
      timestamp: null,
      color: 'var(--forest-green)',
      completed: true,
    });
  } else if (missionStatus === 'completed') {
    milestones.push({
      icon: '🏁',
      title: 'Mission Stabilized',
      description: 'Emergency corridor recovered. Route stabilization completed successfully.',
      timestamp: null,
      color: 'var(--forest-green)',
      completed: true,
    });
  }

  return milestones;
}

export default function MissionTimeline() {
  const store = useMissionStore();

  const milestones = buildMilestones(
    store.activities,
    store.approvals,
    store.incidents,
    store.currentMission?.mission_code || null,
    store.currentMission?.status || null,
  );

  if (milestones.length === 0) {
    return (
      <div className="jm-card">
        <div className="jm-card-header">
          <span className="jm-card-title">📖 Mission Story</span>
        </div>
        <p style={{ color: 'var(--warm-gray)', fontSize: 13, textAlign: 'center', padding: 20 }}>
          Start a mission to see the narrative timeline
        </p>
      </div>
    );
  }

  return (
    <div className="jm-card" style={{ maxHeight: 500, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="jm-card-header">
        <span className="jm-card-title">📖 Mission Story</span>
        <span className="jm-badge jm-badge-gray">{milestones.length} events</span>
      </div>
      <div style={{ overflowY: 'auto', flex: 1 }}>
        <div className="jm-story-timeline">
          {milestones.map((m, i) => (
            <div key={i} className={`jm-story-node animate-slide-in ${m.completed ? 'completed' : 'pending'}`}>
              {/* Connector line */}
              {i < milestones.length - 1 && (
                <div className="jm-story-connector" style={{
                  background: m.completed ? m.color : 'var(--border-green)',
                }} />
              )}

              {/* Icon circle */}
              <div className="jm-story-icon" style={{
                background: m.completed ? m.color : 'var(--light-sage)',
                color: m.completed ? 'white' : 'var(--warm-gray)',
                borderColor: m.color,
                boxShadow: m.completed ? `0 0 0 3px ${m.color}20` : 'none',
              }}>
                {m.icon}
              </div>

              {/* Content */}
              <div className="jm-story-content">
                <div style={{
                  fontSize: 13, fontWeight: 700, color: m.color,
                  marginBottom: 3,
                }}>
                  {m.title}
                </div>
                <div style={{
                  fontSize: 11, color: 'var(--earth-brown)',
                  lineHeight: 1.5,
                }}>
                  {m.description.length > 200 ? m.description.substring(0, 200) + '...' : m.description}
                </div>
                {m.timestamp && (
                  <div style={{ fontSize: 10, color: 'var(--warm-gray)', marginTop: 4 }}>
                    {new Date(m.timestamp).toLocaleTimeString()}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
