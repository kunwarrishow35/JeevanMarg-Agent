// API client for JeevanMarg backend
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

// --- Auth ---
export interface LoginRequest {
  username: string;
  password: string;
}

export interface UserResponse {
  id: number;
  username: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
  last_login: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

// --- Mission ---
export interface MissionCreate {
  origin_name: string;
  origin_lat: number;
  origin_lng: number;
  destination_name: string;
  destination_lat: number;
  destination_lng: number;
}

export interface MissionResponse {
  id: number;
  mission_code: string;
  status: string;
  origin_name: string;
  origin_lat: number;
  origin_lng: number;
  destination_name: string;
  destination_lat: number;
  destination_lng: number;
  trust_score: number | null;
  trust_level: string | null;
  corridor_health: number | null;
  eta_confidence: number | null;
  eta_minutes: number | null;
  congestion_factor: number | null;
  route_stability_factor: number | null;
  traffic_volatility_factor: number | null;
  corridor_continuity_factor: number | null;
  eta_confidence_factor: number | null;
  scenario: string | null;
  created_by: number;
  created_at: string | null;
  updated_at: string | null;
}

// --- Agent Activity ---
export interface AgentActivityResponse {
  id: number;
  mission_id: number;
  agent_name: string;
  agent_state: string;
  action: string;
  result: string | null;
  reasoning: string | null;
  timestamp: string | null;
}

// --- MCP Call ---
export interface MCPCallResponse {
  id: number;
  mission_id: number;
  server_name: string;
  tool_name: string;
  request_payload: Record<string, unknown> | null;
  response_payload: Record<string, unknown> | null;
  latency_ms: number | null;
  status: string;
  timestamp: string | null;
}

// --- Approval ---
export interface ApprovalResponse {
  id: number;
  mission_id: number;
  approval_type: string;
  title: string;
  description: string | null;
  recommendation: Record<string, unknown> | null;
  ai_explanation: string | null;
  trust_score_before: number | null;
  trust_score_after: number | null;
  eta_before: number | null;
  eta_after: number | null;
  status: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  created_at: string | null;
}

// --- Route ---
export interface RouteDataResponse {
  id: number;
  mission_id: number;
  route_type: string;
  route_name: string | null;
  waypoints: number[][];
  segments: Record<string, unknown>[] | null;
  distance_km: number | null;
  eta_minutes: number | null;
  is_active: boolean;
  route_source?: string;
  created_at: string | null;
}

// --- Incident ---
export interface IncidentResponse {
  id: number;
  mission_id: number | null;
  incident_type: string;
  severity: string;
  status: string;
  location_name: string;
  location_lat: number;
  location_lng: number;
  segment_id: string | null;
  segment_name: string | null;
  affected_lanes: number | null;
  total_lanes: number | null;
  estimated_delay_minutes: number | null;
  speed_before_kmh: number | null;
  speed_after_kmh: number | null;
  congestion_before: number | null;
  congestion_after: number | null;
  description: string | null;
  created_at: string | null;
  resolved_at: string | null;
}

// --- System Health ---
export interface AgentStatusResponse {
  name: string;
  display_name: string;
  state: string;
  last_action: string | null;
  last_updated: string | null;
}

export interface MCPServerStatusResponse {
  name: string;
  display_name: string;
  status: string;
  tools_count: number;
  last_call: string | null;
}

export interface SystemHealthResponse {
  system_status: string;
  agents: AgentStatusResponse[];
  mcp_servers: MCPServerStatusResponse[];
  active_mission: MissionResponse | null;
}

export interface DemoConfig {
  default_origin: { name: string; lat: number; lng: number };
  default_destination: { name: string; lat: number; lng: number };
  scenarios: { id: string; name: string; description: string }[];
  demo_credentials: Record<string, { username: string; password: string }>;
}

// --- WebSocket Event ---
export interface WSEvent {
  type: string;
  timestamp: string;
  mission_id?: number;
  agent_name?: string;
  action?: string;
  result?: string;
  reasoning?: string;
  server_name?: string;
  tool_name?: string;
  request_payload?: Record<string, unknown>;
  response_payload?: Record<string, unknown>;
  latency_ms?: number;
  trust_score?: number;
  trust_level?: string;
  corridor_health?: number;
  eta_confidence?: number;
  factors?: Record<string, number>;
  recommendation?: Record<string, unknown>;
  approval_type?: string;
  title?: string;
  description?: string;
  trust_score_before?: number;
  trust_score_after?: number;
  eta_before?: number;
  eta_after?: number;
  approval_id?: number;
  error?: string;
  // Incident events
  incident?: IncidentResponse;
  incident_id?: number;
}

// ---- API Helpers ----

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('jm_token');
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });

  if (res.status === 401 && !path.includes('/auth/login')) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('jm_token');
      localStorage.removeItem('jm_user');
      window.location.href = '/login';
      return new Promise<never>(() => {});
    }
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API Error: ${res.status}`);
  }

  return res.json();
}

// ---- Auth API ----

export const authApi = {
  login: (data: LoginRequest) =>
    apiFetch<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getMe: () => apiFetch<UserResponse>('/api/v1/auth/me'),
};

// ---- Mission API ----

export const missionApi = {
  create: (data: MissionCreate) =>
    apiFetch<MissionResponse>('/api/v1/missions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  list: () =>
    apiFetch<{ missions: MissionResponse[]; total: number }>('/api/v1/missions'),

  get: (id: number) =>
    apiFetch<MissionResponse>(`/api/v1/missions/${id}`),

  start: (id: number) =>
    apiFetch<{ status: string; mission_id: number }>(`/api/v1/missions/${id}/start`, {
      method: 'POST',
    }),

  getActivities: (id: number) =>
    apiFetch<AgentActivityResponse[]>(`/api/v1/missions/${id}/activities`),

  getMCPCalls: (id: number) =>
    apiFetch<MCPCallResponse[]>(`/api/v1/missions/${id}/mcp-calls`),

  getRoutes: (id: number) =>
    apiFetch<RouteDataResponse[]>(`/api/v1/missions/${id}/routes`),
};

// ---- Approval API ----

export const approvalApi = {
  list: (status?: string) =>
    apiFetch<ApprovalResponse[]>(
      `/api/v1/approvals${status ? `?status_filter=${status}` : ''}`
    ),

  approve: (id: number) =>
    apiFetch<ApprovalResponse>(`/api/v1/approvals/${id}/approve`, {
      method: 'POST',
    }),

  reject: (id: number) =>
    apiFetch<ApprovalResponse>(`/api/v1/approvals/${id}/reject`, {
      method: 'POST',
    }),
};

// ---- Incident API ----

export const incidentApi = {
  simulate: (incidentType: string, missionId?: number) =>
    apiFetch<IncidentResponse>('/api/v1/incidents/simulate', {
      method: 'POST',
      body: JSON.stringify({
        incident_type: incidentType,
        mission_id: missionId || null,
      }),
    }),

  list: (statusFilter?: string, missionId?: number) => {
    const params = new URLSearchParams();
    if (statusFilter) params.set('status_filter', statusFilter);
    if (missionId) params.set('mission_id', String(missionId));
    const qs = params.toString();
    return apiFetch<{ incidents: IncidentResponse[]; total: number }>(
      `/api/v1/incidents${qs ? `?${qs}` : ''}`
    );
  },

  get: (id: number) =>
    apiFetch<IncidentResponse>(`/api/v1/incidents/${id}`),

  resolve: (id: number) =>
    apiFetch<IncidentResponse>(`/api/v1/incidents/${id}/resolve`, {
      method: 'POST',
    }),
};

// ---- System API ----

export const systemApi = {
  getHealth: () => apiFetch<SystemHealthResponse>('/api/v1/system/health'),
  getDemoConfig: () => apiFetch<DemoConfig>('/api/v1/demo/config'),
};

// ---- WebSocket ----

export function createMissionWebSocket(
  missionId: number,
  onEvent: (event: WSEvent) => void,
  onError?: (error: Event) => void,
  onClose?: () => void,
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/missions/${missionId}`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as WSEvent;
      onEvent(data);
    } catch (e) {
      console.error('WebSocket parse error:', e);
    }
  };

  ws.onerror = (event) => {
    console.error('WebSocket error:', event);
    onError?.(event);
  };

  ws.onclose = () => {
    onClose?.();
  };

  return ws;
}

export function createGlobalWebSocket(
  onEvent: (event: WSEvent) => void,
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/global`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as WSEvent;
      onEvent(data);
    } catch (e) {
      console.error('WebSocket parse error:', e);
    }
  };

  return ws;
}
