"""System health and status routes."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

from app.schemas.mission import (
    SystemHealthResponse,
    AgentStatusResponse,
    MCPServerStatusResponse,
)

router = APIRouter(prefix="/api/v1/system", tags=["System"])

# In-memory agent and MCP status tracking (updated by orchestrator)
_agent_states: dict[str, dict] = {
    "emergency_coordinator": {"state": "idle", "display_name": "Emergency Coordinator", "last_action": None, "last_updated": None},
    "route_intelligence": {"state": "idle", "display_name": "Route Intelligence", "last_action": None, "last_updated": None},
    "traffic_intelligence": {"state": "idle", "display_name": "Traffic Intelligence", "last_action": None, "last_updated": None},
    "trust_score": {"state": "idle", "display_name": "Trust Score", "last_action": None, "last_updated": None},
    "recovery": {"state": "idle", "display_name": "Recovery", "last_action": None, "last_updated": None},
}

_mcp_states: dict[str, dict] = {
    "traffic": {"status": "disconnected", "display_name": "Traffic MCP", "tools_count": 3, "last_call": None},
    "route": {"status": "disconnected", "display_name": "Route MCP", "tools_count": 3, "last_call": None},
    "hospital": {"status": "disconnected", "display_name": "Hospital MCP", "tools_count": 2, "last_call": None},
    "trust": {"status": "disconnected", "display_name": "Trust MCP", "tools_count": 2, "last_call": None},
}


def update_agent_state(agent_name: str, state: str, last_action: Optional[str] = None) -> None:
    """Update agent state (called by orchestrator)."""
    if agent_name in _agent_states:
        _agent_states[agent_name]["state"] = state
        if last_action:
            _agent_states[agent_name]["last_action"] = last_action
        _agent_states[agent_name]["last_updated"] = datetime.now(timezone.utc).isoformat()


def update_mcp_state(server_name: str, status: str) -> None:
    """Update MCP server status (called during startup/calls)."""
    if server_name in _mcp_states:
        _mcp_states[server_name]["status"] = status


def update_mcp_last_call(server_name: str) -> None:
    """Record an MCP call timestamp."""
    if server_name in _mcp_states:
        _mcp_states[server_name]["last_call"] = datetime.now(timezone.utc).isoformat()


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health():
    """Get full system health: agents, MCP servers, and active mission status."""
    agents = [
        AgentStatusResponse(
            name=name,
            display_name=data["display_name"],
            state=data["state"],
            last_action=data.get("last_action"),
            last_updated=data.get("last_updated"),
        )
        for name, data in _agent_states.items()
    ]

    mcp_servers = [
        MCPServerStatusResponse(
            name=name,
            display_name=data["display_name"],
            status=data["status"],
            tools_count=data["tools_count"],
            last_call=data.get("last_call"),
        )
        for name, data in _mcp_states.items()
    ]

    # Determine overall system status
    all_mcp_connected = all(s["status"] == "connected" for s in _mcp_states.values())
    any_agent_failed = any(s["state"] == "failed" for s in _agent_states.values())

    if any_agent_failed:
        system_status = "degraded"
    elif all_mcp_connected:
        system_status = "online"
    else:
        system_status = "degraded"

    return SystemHealthResponse(
        system_status=system_status,
        agents=agents,
        mcp_servers=mcp_servers,
    )
