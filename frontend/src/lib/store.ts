'use client';

import { create } from 'zustand';
import type {
  UserResponse,
  MissionResponse,
  AgentActivityResponse,
  MCPCallResponse,
  ApprovalResponse,
  RouteDataResponse,
  AgentStatusResponse,
  MCPServerStatusResponse,
  IncidentResponse,
  WSEvent,
} from '@/lib/api';

// --- Auth Store ---
interface AuthState {
  user: UserResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  setAuth: (user: UserResponse, token: string) => void;
  logout: () => void;
  loadFromStorage: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,

  setAuth: (user, token) => {
    localStorage.setItem('jm_token', token);
    localStorage.setItem('jm_user', JSON.stringify(user));
    set({ user, token, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('jm_token');
    localStorage.removeItem('jm_user');
    set({ user: null, token: null, isAuthenticated: false });
  },

  loadFromStorage: () => {
    const token = localStorage.getItem('jm_token');
    const userStr = localStorage.getItem('jm_user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr) as UserResponse;
        set({ user, token, isAuthenticated: true });
      } catch {
        set({ user: null, token: null, isAuthenticated: false });
      }
    }
  },
}));

// --- Mission Store ---
interface MissionState {
  currentMission: MissionResponse | null;
  missions: MissionResponse[];
  activities: AgentActivityResponse[];
  mcpCalls: MCPCallResponse[];
  approvals: ApprovalResponse[];
  routes: RouteDataResponse[];
  agentStates: AgentStatusResponse[];
  mcpServerStates: MCPServerStatusResponse[];
  incidents: IncidentResponse[];
  systemStatus: string;
  isRunning: boolean;
  trustScore: number | null;
  trustLevel: string | null;
  corridorHealth: number | null;
  etaConfidence: number | null;
  trustFactors: Record<string, number>;

  setCurrentMission: (mission: MissionResponse | null) => void;
  setMissions: (missions: MissionResponse[]) => void;
  addActivity: (activity: AgentActivityResponse) => void;
  setActivities: (activities: AgentActivityResponse[]) => void;
  addMCPCall: (call: MCPCallResponse) => void;
  setMCPCalls: (calls: MCPCallResponse[]) => void;
  setApprovals: (approvals: ApprovalResponse[]) => void;
  updateApproval: (id: number, status: string) => void;
  addApproval: (approval: ApprovalResponse) => void;
  setRoutes: (routes: RouteDataResponse[]) => void;
  addRoute: (route: RouteDataResponse) => void;
  setAgentStates: (states: AgentStatusResponse[]) => void;
  setMCPServerStates: (states: MCPServerStatusResponse[]) => void;
  setIncidents: (incidents: IncidentResponse[]) => void;
  addIncident: (incident: IncidentResponse) => void;
  resolveIncident: (id: number) => void;
  setSystemStatus: (status: string) => void;
  setIsRunning: (running: boolean) => void;
  updateTrustScore: (score: number, level: string, health: number, confidence: number, factors: Record<string, number>) => void;
  handleWSEvent: (event: WSEvent) => void;
  reset: () => void;
}

export const useMissionStore = create<MissionState>((set, get) => ({
  currentMission: null,
  missions: [],
  activities: [],
  mcpCalls: [],
  approvals: [],
  routes: [],
  agentStates: [],
  mcpServerStates: [],
  incidents: [],
  systemStatus: 'online',
  isRunning: false,
  trustScore: null,
  trustLevel: null,
  corridorHealth: null,
  etaConfidence: null,
  trustFactors: {},

  setCurrentMission: (mission) => set({ currentMission: mission }),
  setMissions: (missions) => set({ missions }),
  addActivity: (activity) => set((s) => ({ activities: [...s.activities, activity] })),
  setActivities: (activities) => set({ activities }),
  addMCPCall: (call) => set((s) => ({ mcpCalls: [...s.mcpCalls, call] })),
  setMCPCalls: (calls) => set({ mcpCalls: calls }),
  setApprovals: (approvals) => set({ approvals }),
  updateApproval: (id, status) =>
    set((s) => ({
      approvals: s.approvals.map((a) =>
        a.id === id ? { ...a, status } : a
      ),
    })),
  addApproval: (approval) =>
    set((s) => {
      const exists = s.approvals.some((a) => a.id === approval.id);
      if (exists) {
        return {
          approvals: s.approvals.map((a) => (a.id === approval.id ? approval : a)),
        };
      }
      return { approvals: [...s.approvals, approval] };
    }),
  setRoutes: (routes) => set({ routes }),
  addRoute: (route) => set((s) => ({ routes: [...s.routes, route] })),
  setAgentStates: (states) => set({ agentStates: states }),
  setMCPServerStates: (states) => set({ mcpServerStates: states }),
  setIncidents: (incidents) => set({ incidents }),
  addIncident: (incident) => set((s) => ({ incidents: [...s.incidents, incident] })),
  resolveIncident: (id) =>
    set((s) => ({
      incidents: s.incidents.map((i) =>
        i.id === id ? { ...i, status: 'resolved' } : i
      ),
    })),
  setSystemStatus: (status) => set({ systemStatus: status }),
  setIsRunning: (running) => set({ isRunning: running }),
  updateTrustScore: (score, level, health, confidence, factors) =>
    set({ trustScore: score, trustLevel: level, corridorHealth: health, etaConfidence: confidence, trustFactors: factors }),

  handleWSEvent: (event: WSEvent) => {
    const state = get();
    const now = event.timestamp || new Date().toISOString();

    switch (event.type) {
      case 'agent_started':
      case 'agent_completed':
      case 'agent_reasoning':
        set((s) => ({
          activities: [
            ...s.activities,
            {
              id: Date.now(),
              mission_id: event.mission_id || 0,
              agent_name: event.agent_name || 'unknown',
              agent_state: event.type === 'agent_started' ? 'running'
                : event.type === 'agent_completed' ? 'completed' : 'running',
              action: event.action || event.type,
              result: event.result || null,
              reasoning: event.reasoning || null,
              timestamp: now,
            },
          ],
          agentStates: s.agentStates.map((a) =>
            a.name === event.agent_name
              ? {
                  ...a,
                  state: event.type === 'agent_started' ? 'running'
                    : event.type === 'agent_completed' ? 'completed' : a.state,
                  last_action: event.action || a.last_action,
                  last_updated: now,
                }
              : a
          ),
        }));
        break;

      case 'mcp_call_started':
      case 'mcp_call_completed':
        if (event.type === 'mcp_call_completed') {
          set((s) => ({
            mcpCalls: [
              ...s.mcpCalls,
              {
                id: Date.now(),
                mission_id: event.mission_id || 0,
                server_name: event.server_name || 'unknown',
                tool_name: event.tool_name || 'unknown',
                request_payload: event.request_payload || null,
                response_payload: event.response_payload || null,
                latency_ms: event.latency_ms || null,
                status: 'success',
                timestamp: now,
              },
            ],
          }));
        }
        break;

      case 'trust_score_updated':
        set({
          trustScore: event.trust_score ?? null,
          trustLevel: event.trust_level ?? null,
          corridorHealth: event.corridor_health ?? null,
          etaConfidence: event.eta_confidence ?? null,
          trustFactors: event.factors || {},
        });
        if (state.currentMission && event.trust_score !== undefined) {
          set({
            currentMission: {
              ...state.currentMission,
              trust_score: event.trust_score ?? null,
              trust_level: event.trust_level ?? null,
              corridor_health: event.corridor_health ?? null,
              eta_confidence: event.eta_confidence ?? null,
            },
          });
        }
        break;

      case 'approval_requested':
        set((s) => {
          const approvalId = event.approval_id || Date.now();
          const newApproval = {
            id: approvalId,
            mission_id: event.mission_id || 0,
            approval_type: event.approval_type || 'route_change',
            title: event.title || 'Recovery Recommendation',
            description: event.description || null,
            recommendation: null,
            ai_explanation: event.description || null,
            trust_score_before: event.trust_score_before ?? null,
            trust_score_after: event.trust_score_after ?? null,
            eta_before: event.eta_before ?? null,
            eta_after: event.eta_after ?? null,
            status: 'pending',
            reviewed_by: null,
            reviewed_at: null,
            created_at: now,
          };
          const exists = s.approvals.some((a) => a.id === approvalId);
          if (exists) {
            return {
              approvals: s.approvals.map((a) => (a.id === approvalId ? newApproval : a)),
            };
          }
          return {
            approvals: [...s.approvals, newApproval],
          };
        });
        break;

      case 'approval_resolved':
        set((s) => ({
          approvals: s.approvals.map((a) =>
            a.id === event.approval_id || (a.mission_id === event.mission_id && a.status === 'pending')
              ? { ...a, status: event.action === 'approved' ? 'approved' : 'rejected' }
              : a
          ),
        }));
        if (event.action === 'approved' && event.trust_score_after && state.currentMission) {
          set({
            trustScore: event.trust_score_after,
            trustLevel: event.trust_score_after >= 90 ? 'excellent'
              : event.trust_score_after >= 70 ? 'healthy'
              : event.trust_score_after >= 50 ? 'warning' : 'critical',
            currentMission: {
              ...state.currentMission,
              trust_score: event.trust_score_after,
              status: 'completed',
              scenario: 'recovered',
            },
          });
        }
        break;

      case 'scenario_started':
        set((s) => ({
          activities: [
            ...s.activities,
            {
              id: Date.now(),
              mission_id: event.mission_id || 0,
              agent_name: 'system',
              agent_state: 'running',
              action: `Scenario: ${(event as unknown as Record<string, unknown>).scenario || 'unknown'}`,
              result: null,
              reasoning: `Starting ${(event as unknown as Record<string, unknown>).scenario} scenario analysis`,
              timestamp: now,
            },
          ],
        }));
        break;

      case 'incident_created':
        if (event.incident) {
          set((s) => ({
            incidents: [...s.incidents, event.incident as IncidentResponse],
            activities: [
              ...s.activities,
              {
                id: Date.now(),
                mission_id: event.mission_id || 0,
                agent_name: 'system',
                agent_state: 'running',
                action: `🚨 Incident: ${(event.incident as IncidentResponse).incident_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}`,
                result: `${(event.incident as IncidentResponse).description}`,
                reasoning: `${(event.incident as IncidentResponse).severity.toUpperCase()} severity at ${(event.incident as IncidentResponse).location_name}. Estimated delay: +${(event.incident as IncidentResponse).estimated_delay_minutes} minutes.`,
                timestamp: now,
              },
            ],
          }));
        }
        break;

      case 'incident_resolved':
        if (event.incident_id) {
          set((s) => ({
            incidents: s.incidents.map((i) =>
              i.id === event.incident_id ? { ...i, status: 'resolved' } : i
            ),
          }));
        }
        break;

      case 'mission_completed':
        set({ isRunning: false });
        if (state.currentMission) {
          set({
            currentMission: {
              ...state.currentMission,
              status: state.currentMission.status === 'awaiting_approval'
                ? 'awaiting_approval' : 'completed',
            },
          });
        }
        break;

      case 'mission_failed':
        set({ isRunning: false });
        if (state.currentMission) {
          set({
            currentMission: { ...state.currentMission, status: 'failed' },
          });
        }
        break;

      case 'recovery_recommended':
        // Route data will come through separately
        break;
    }
  },

  reset: () =>
    set({
      currentMission: null,
      activities: [],
      mcpCalls: [],
      approvals: [],
      routes: [],
      incidents: [],
      isRunning: false,
      trustScore: null,
      trustLevel: null,
      corridorHealth: null,
      etaConfidence: null,
      trustFactors: {},
    }),
}));
