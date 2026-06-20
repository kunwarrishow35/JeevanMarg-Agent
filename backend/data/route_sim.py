"""Simulated route data generator for Delhi NCR."""

import math
import random
from typing import Optional


# Pre-defined routes in Delhi NCR
ROUTE_TEMPLATES = {
    "connaught_to_aiims": {
        "name": "Connaught Place → AIIMS via Aurobindo Marg",
        "waypoints": [
            [28.6315, 77.2167],  # Connaught Place
            [28.6280, 77.2150],  # Janpath
            [28.6200, 77.2130],  # Mandi House area
            [28.6100, 77.2100],  # India Gate nearby
            [28.5980, 77.2090],  # Lodhi Road
            [28.5880, 77.2080],  # Safdarjung area
            [28.5780, 77.2070],  # Green Park
            [28.5672, 77.2100],  # AIIMS
        ],
        "segments": [
            {"id": "seg_01", "name": "Janpath Road", "length_km": 0.5, "lanes": 4, "speed_limit": 50},
            {"id": "seg_02", "name": "Barakhamba Road", "length_km": 0.8, "lanes": 4, "speed_limit": 50},
            {"id": "seg_03", "name": "Mandi House Flyover", "length_km": 1.2, "lanes": 3, "speed_limit": 60},
            {"id": "seg_04", "name": "Lodhi Road", "length_km": 1.5, "lanes": 4, "speed_limit": 60},
            {"id": "seg_05", "name": "Safdarjung Flyover", "length_km": 1.0, "lanes": 3, "speed_limit": 50},
            {"id": "seg_06", "name": "Aurobindo Marg", "length_km": 1.2, "lanes": 4, "speed_limit": 50},
            {"id": "seg_07", "name": "AIIMS Approach", "length_km": 0.8, "lanes": 3, "speed_limit": 40},
        ],
        "distance_km": 7.0,
        "base_eta_minutes": 14,
    },
    "connaught_to_aiims_alt": {
        "name": "Connaught Place → AIIMS via Ring Road",
        "waypoints": [
            [28.6315, 77.2167],  # Connaught Place
            [28.6350, 77.2200],  # Minto Road
            [28.6400, 77.2300],  # ITO
            [28.6350, 77.2450],  # Ring Road North
            [28.6150, 77.2500],  # Ring Road East
            [28.5950, 77.2450],  # South Extension
            [28.5800, 77.2300],  # Lajpat Nagar
            [28.5700, 77.2200],  # Jangpura
            [28.5672, 77.2100],  # AIIMS
        ],
        "segments": [
            {"id": "seg_a01", "name": "Minto Road", "length_km": 0.6, "lanes": 4, "speed_limit": 50},
            {"id": "seg_a02", "name": "ITO Junction", "length_km": 1.0, "lanes": 6, "speed_limit": 60},
            {"id": "seg_a03", "name": "Ring Road (North)", "length_km": 1.8, "lanes": 6, "speed_limit": 70},
            {"id": "seg_a04", "name": "Ring Road (East)", "length_km": 2.0, "lanes": 6, "speed_limit": 70},
            {"id": "seg_a05", "name": "Ring Road (South)", "length_km": 1.5, "lanes": 6, "speed_limit": 70},
            {"id": "seg_a06", "name": "Lajpat Nagar Connector", "length_km": 1.2, "lanes": 4, "speed_limit": 50},
            {"id": "seg_a07", "name": "AIIMS Ring Road Exit", "length_km": 0.9, "lanes": 4, "speed_limit": 40},
        ],
        "distance_km": 9.0,
        "base_eta_minutes": 12,
    },
}


def generate_route_data(
    origin: dict,
    destination: dict,
    route_key: Optional[str] = None,
) -> dict:
    """Generate route data between two points.

    Args:
        origin: {"lat": float, "lng": float, "name": str}
        destination: {"lat": float, "lng": float, "name": str}
        route_key: Optional template key. If None, uses default or generates one.

    Returns:
        Route data with waypoints, segments, distance, and ETA.
    """
    if route_key and route_key in ROUTE_TEMPLATES:
        template = ROUTE_TEMPLATES[route_key]
    else:
        # Default to primary route
        template = ROUTE_TEMPLATES["connaught_to_aiims"]

    return {
        "route_name": template["name"],
        "waypoints": template["waypoints"],
        "segments": template["segments"],
        "distance_km": template["distance_km"],
        "base_eta_minutes": template["base_eta_minutes"],
        "origin": origin,
        "destination": destination,
    }


def generate_alternative_route_data(
    origin: dict,
    destination: dict,
    avoid_segments: list[str],
) -> dict:
    """Generate an alternative route avoiding specified segments.

    Args:
        origin: Origin point
        destination: Destination point
        avoid_segments: Segment IDs to avoid

    Returns:
        Alternative route data.
    """
    template = ROUTE_TEMPLATES["connaught_to_aiims_alt"]
    return {
        "route_name": template["name"],
        "waypoints": template["waypoints"],
        "segments": template["segments"],
        "distance_km": template["distance_km"],
        "base_eta_minutes": template["base_eta_minutes"],
        "avoided_segments": avoid_segments,
        "origin": origin,
        "destination": destination,
    }


def estimate_eta_data(
    route_segments: list[dict],
    traffic_conditions: Optional[dict] = None,
) -> dict:
    """Estimate ETA based on route segments and traffic conditions.

    Args:
        route_segments: List of segment data
        traffic_conditions: Optional traffic data affecting segments

    Returns:
        ETA estimation with confidence.
    """
    total_distance = sum(s.get("length_km", 1.0) for s in route_segments)
    base_speed = 40  # km/h base speed in Delhi

    if traffic_conditions:
        congestion = traffic_conditions.get("congestion_level", 0.0)
        # Congestion reduces speed
        effective_speed = base_speed * (1 - congestion * 0.6)
    else:
        effective_speed = base_speed

    effective_speed = max(effective_speed, 10)  # Minimum 10 km/h
    eta_minutes = (total_distance / effective_speed) * 60

    # Confidence based on traffic data quality
    confidence = 0.95 if traffic_conditions else 0.75

    return {
        "eta_minutes": round(eta_minutes, 1),
        "effective_speed_kmh": round(effective_speed, 1),
        "total_distance_km": round(total_distance, 2),
        "confidence": confidence,
        "calculation_method": "segment_weighted" if traffic_conditions else "base_estimate",
    }


def interpolate_waypoints(waypoints: list[list[float]], num_points: int = 50) -> list[list[float]]:
    """Interpolate additional points along a route for smooth visualization."""
    if len(waypoints) < 2:
        return waypoints

    result = []
    for i in range(len(waypoints) - 1):
        start = waypoints[i]
        end = waypoints[i + 1]
        segment_points = max(2, num_points // (len(waypoints) - 1))

        for j in range(segment_points):
            t = j / segment_points
            lat = start[0] + t * (end[0] - start[0])
            lng = start[1] + t * (end[1] - start[1])
            result.append([round(lat, 6), round(lng, 6)])

    result.append(waypoints[-1])
    return result
