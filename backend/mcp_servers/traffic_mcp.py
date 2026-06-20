"""Traffic MCP Server — provides traffic intelligence tools via MCP protocol.

This is a real FastMCP server that exposes tools for traffic analysis.
Agents call these tools through the MCP protocol, NOT through direct function calls.
"""

import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

mcp = FastMCP(
    name="TrafficMCPServer",
    instructions="Traffic intelligence MCP server for JeevanMarg emergency corridor system. "
                 "Provides real-time traffic status, congestion risk assessment, and segment speed data.",
)


@mcp.tool()
def get_traffic_status(route_segments: str) -> str:
    """Get current traffic status for route segments.

    Analyzes traffic conditions across all segments of a route and provides
    congestion levels, speed data, and corridor assessment.

    Args:
        route_segments: JSON string of route segments, each with 'id', 'name', 'speed_limit', 'length_km'.

    Returns:
        JSON string with traffic status per segment and overall corridor assessment.
    """
    from data.traffic_sim import get_traffic_status_data

    segments = json.loads(route_segments) if isinstance(route_segments, str) else route_segments
    result = get_traffic_status_data(segments)
    return json.dumps(result, indent=2)


@mcp.tool()
def get_congestion_risk(lat: float, lng: float, radius_km: float = 2.0) -> str:
    """Assess congestion risk in an area around a given coordinate.

    Evaluates the likelihood and severity of congestion based on current conditions,
    incidents, and historical patterns.

    Args:
        lat: Center latitude of the area to assess.
        lng: Center longitude of the area to assess.
        radius_km: Radius in kilometers to assess (default 2.0).

    Returns:
        JSON string with risk level, risk category, active incidents, and historical patterns.
    """
    from data.traffic_sim import get_congestion_risk_data

    result = get_congestion_risk_data(lat, lng, radius_km)
    return json.dumps(result, indent=2)


@mcp.tool()
def get_segment_speed(segment_id: str) -> str:
    """Get real-time speed data for a specific route segment.

    Returns current speed, free-flow speed, congestion level, and flow status
    for the specified road segment.

    Args:
        segment_id: Unique identifier of the route segment (e.g., 'seg_01').

    Returns:
        JSON string with speed data, congestion level, and flow status.
    """
    from data.traffic_sim import get_segment_speed_data

    result = get_segment_speed_data(segment_id)
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
