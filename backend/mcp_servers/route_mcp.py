"""Route MCP Server — provides route generation and ETA tools via MCP protocol.

This is a real FastMCP server that exposes tools for route intelligence.
Agents call these tools through the MCP protocol, NOT through direct function calls.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

mcp = FastMCP(
    name="RouteMCPServer",
    instructions="Route intelligence MCP server for JeevanMarg emergency corridor system. "
                 "Provides route generation, ETA estimation, and alternative route planning.",
)


@mcp.tool()
def generate_route(origin_lat: float, origin_lng: float, origin_name: str,
                   destination_lat: float, destination_lng: float, destination_name: str) -> str:
    """Generate an optimal route between two points.

    Calculates the best emergency corridor route considering road network,
    segment data, and distance.

    Args:
        origin_lat: Origin latitude.
        origin_lng: Origin longitude.
        origin_name: Human-readable origin name.
        destination_lat: Destination latitude.
        destination_lng: Destination longitude.
        destination_name: Human-readable destination name.

    Returns:
        JSON string with route waypoints, segments, distance, and base ETA.
    """
    from data.route_sim import generate_route_data

    origin = {"lat": origin_lat, "lng": origin_lng, "name": origin_name}
    destination = {"lat": destination_lat, "lng": destination_lng, "name": destination_name}
    result = generate_route_data(origin, destination, route_key="connaught_to_aiims")
    return json.dumps(result, indent=2)


@mcp.tool()
def estimate_eta(route_segments: str, traffic_data: str = "{}") -> str:
    """Estimate arrival time considering current traffic conditions.

    Uses segment-level traffic data to calculate a more accurate ETA
    than the base distance/speed estimation.

    Args:
        route_segments: JSON string of route segments with 'id', 'length_km', 'speed_limit'.
        traffic_data: JSON string of traffic conditions including 'congestion_level'.

    Returns:
        JSON string with estimated ETA in minutes, confidence, and calculation details.
    """
    from data.route_sim import estimate_eta_data

    segments = json.loads(route_segments) if isinstance(route_segments, str) else route_segments
    traffic = json.loads(traffic_data) if isinstance(traffic_data, str) else traffic_data
    result = estimate_eta_data(segments, traffic)
    return json.dumps(result, indent=2)


@mcp.tool()
def generate_alternative_route(origin_lat: float, origin_lng: float, origin_name: str,
                                destination_lat: float, destination_lng: float,
                                destination_name: str, avoid_segments: str = "[]") -> str:
    """Generate an alternative route avoiding congested or blocked segments.

    Creates a different path to the destination that avoids specified road segments,
    typically used when the primary corridor is degraded.

    Args:
        origin_lat: Origin latitude.
        origin_lng: Origin longitude.
        origin_name: Human-readable origin name.
        destination_lat: Destination latitude.
        destination_lng: Destination longitude.
        destination_name: Human-readable destination name.
        avoid_segments: JSON string of segment IDs to avoid.

    Returns:
        JSON string with alternative route waypoints, segments, distance, and ETA.
    """
    from data.route_sim import generate_alternative_route_data

    origin = {"lat": origin_lat, "lng": origin_lng, "name": origin_name}
    destination = {"lat": destination_lat, "lng": destination_lng, "name": destination_name}
    avoid = json.loads(avoid_segments) if isinstance(avoid_segments, str) else avoid_segments
    result = generate_alternative_route_data(origin, destination, avoid)
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
