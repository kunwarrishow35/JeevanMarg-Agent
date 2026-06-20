"""Hospital MCP Server — provides hospital and trauma center lookup via MCP protocol.

This is a real FastMCP server that exposes tools for hospital intelligence.
Agents call these tools through the MCP protocol, NOT through direct function calls.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

mcp = FastMCP(
    name="HospitalMCPServer",
    instructions="Hospital intelligence MCP server for JeevanMarg emergency corridor system. "
                 "Provides nearby hospital lookup and trauma center identification for Delhi NCR.",
)


@mcp.tool()
def get_nearby_hospitals(lat: float, lng: float, radius_km: float = 10.0) -> str:
    """Find hospitals near a given location.

    Searches the hospital database for all medical facilities within the specified
    radius and returns them sorted by distance.

    Args:
        lat: Center latitude for hospital search.
        lng: Center longitude for hospital search.
        radius_km: Search radius in kilometers (default 10.0).

    Returns:
        JSON string with list of nearby hospitals including name, type, distance,
        emergency beds, and specialties.
    """
    from data.hospital_data import get_nearby_hospitals_data

    hospitals = get_nearby_hospitals_data(lat, lng, radius_km)
    return json.dumps({
        "hospitals": hospitals,
        "total_found": len(hospitals),
        "search_center": {"lat": lat, "lng": lng},
        "search_radius_km": radius_km,
    }, indent=2)


@mcp.tool()
def get_trauma_centers(lat: float, lng: float) -> str:
    """Find Level 1 and Level 2 trauma centers near a location.

    Identifies specialized trauma facilities capable of handling critical
    emergency cases, sorted by distance from the given location.

    Args:
        lat: Latitude for trauma center search.
        lng: Longitude for trauma center search.

    Returns:
        JSON string with list of trauma centers including trauma level,
        specialties, and distance.
    """
    from data.hospital_data import get_trauma_centers_data

    centers = get_trauma_centers_data(lat, lng)
    return json.dumps({
        "trauma_centers": centers,
        "total_found": len(centers),
        "search_center": {"lat": lat, "lng": lng},
    }, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
