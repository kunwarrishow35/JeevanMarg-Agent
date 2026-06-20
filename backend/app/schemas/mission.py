"""Mission and related Pydantic schemas."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# --- Mission Schemas ---

class MissionCreate(BaseModel):
    """Create a new mission."""
    origin_name: str = Field(..., min_length=2, max_length=200)
    origin_lat: float = Field(..., ge=-90, le=90)
    origin_lng: float = Field(..., ge=-180, le=180)
    destination_name: str = Field(..., min_length=2, max_length=200)
    destination_lat: float = Field(..., ge=-90, le=90)
    destination_lng: float = Field(..., ge=-180, le=180)


class MissionResponse(BaseModel):
    """Mission details."""
    id: int
    mission_code: str
    status: str
    origin_name: str
    origin_lat: float
    origin_lng: float
    destination_name: str
    destination_lat: float
    destination_lng: float
    trust_score: Optional[float] = None
    trust_level: Optional[str] = None
    corridor_health: Optional[float] = None
    eta_confidence: Optional[float] = None
    eta_minutes: Optional[float] = None
    congestion_factor: Optional[float] = None
    route_stability_factor: Optional[float] = None
    traffic_volatility_factor: Optional[float] = None
    corridor_continuity_factor: Optional[float] = None
    eta_confidence_factor: Optional[float] = None
    scenario: Optional[str] = None
    created_by: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MissionListResponse(BaseModel):
    """List of missions."""
    missions: list[MissionResponse]
    total: int


# --- Agent Activity Schemas ---

class AgentActivityResponse(BaseModel):
    """Agent activity log entry."""
    id: int
    mission_id: int
    agent_name: str
    agent_state: str
    action: str
    result: Optional[str] = None
    reasoning: Optional[str] = None
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- MCP Call Schemas ---

class MCPCallResponse(BaseModel):
    """MCP call log entry."""
    id: int
    mission_id: int
    server_name: str
    tool_name: str
    request_payload: Optional[Any] = None
    response_payload: Optional[Any] = None
    latency_ms: Optional[int] = None
    status: str
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Approval Schemas ---

class ApprovalResponse(BaseModel):
    """Approval request details."""
    id: int
    mission_id: int
    approval_type: str
    title: str
    description: Optional[str] = None
    recommendation: Optional[Any] = None
    ai_explanation: Optional[str] = None
    trust_score_before: Optional[float] = None
    trust_score_after: Optional[float] = None
    eta_before: Optional[float] = None
    eta_after: Optional[float] = None
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalAction(BaseModel):
    """Approve or reject request."""
    action: str = Field(..., pattern="^(approve|reject)$")
    reason: Optional[str] = None


# --- Route Data Schemas ---

class RouteDataResponse(BaseModel):
    """Route data."""
    id: int
    mission_id: int
    route_type: str
    route_name: Optional[str] = None
    waypoints: list[list[float]]
    segments: Optional[Any] = None
    distance_km: Optional[float] = None
    eta_minutes: Optional[float] = None
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Trust Score Schemas ---

class TrustScoreResponse(BaseModel):
    """Trust score breakdown."""
    score: float
    level: str
    corridor_health: float
    eta_confidence: float
    factors: dict[str, float]


# --- System Health Schemas ---

class AgentStatusResponse(BaseModel):
    """Individual agent status."""
    name: str
    display_name: str
    state: str
    last_action: Optional[str] = None
    last_updated: Optional[datetime] = None


class MCPServerStatusResponse(BaseModel):
    """MCP server status."""
    name: str
    display_name: str
    status: str  # connected/disconnected
    tools_count: int
    last_call: Optional[datetime] = None


class SystemHealthResponse(BaseModel):
    """Full system health status."""
    system_status: str  # online/degraded/offline
    agents: list[AgentStatusResponse]
    mcp_servers: list[MCPServerStatusResponse]
    active_mission: Optional[MissionResponse] = None
