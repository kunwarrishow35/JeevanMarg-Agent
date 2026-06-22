"""Route data generator — supports both predefined and dynamic routes."""

import math
import random
from typing import Optional


# Pre-defined routes (kept for backward compatibility)
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


# Segment name patterns for dynamic routes
_SEGMENT_NAMES = [
    "Departure Corridor", "Main Avenue", "Central Flyover", "Primary Road",
    "Mid-Corridor Junction", "Through Road", "Connector Bridge",
    "Final Approach", "Destination Lane",
]

_ALT_SEGMENT_NAMES = [
    "Bypass Entry", "Outer Ring Road", "Peripheral Highway", "Arterial Road",
    "Cross-Connector", "Service Road", "Parallel Avenue",
    "Destination Bypass", "Final Merge",
]


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points using the Haversine formula."""
    R = 6371.0  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _generate_dynamic_waypoints(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
    num_waypoints: int = 8,
    offset_scale: float = 0.003,
) -> list[list[float]]:
    """Generate realistic waypoints between two coordinates.

    Creates intermediate points with slight random offsets to simulate
    realistic road curvature rather than a straight line.
    """
    waypoints = [[origin_lat, origin_lng]]

    for i in range(1, num_waypoints - 1):
        t = i / (num_waypoints - 1)
        # Linear interpolation with random offsets for road curvature
        lat = origin_lat + t * (dest_lat - origin_lat)
        lng = origin_lng + t * (dest_lng - origin_lng)

        # Add slight random offset (simulates roads not being straight)
        lat += random.uniform(-offset_scale, offset_scale)
        lng += random.uniform(-offset_scale, offset_scale)

        waypoints.append([round(lat, 6), round(lng, 6)])

    waypoints.append([dest_lat, dest_lng])
    return waypoints


def _generate_dynamic_segments(
    waypoints: list[list[float]],
    segment_names: list[str] | None = None,
) -> list[dict]:
    """Generate segment metadata from waypoints."""
    if segment_names is None:
        segment_names = _SEGMENT_NAMES

    segments = []
    for i in range(len(waypoints) - 1):
        seg_distance = _haversine_km(
            waypoints[i][0], waypoints[i][1],
            waypoints[i + 1][0], waypoints[i + 1][1],
        )
        name_idx = min(i, len(segment_names) - 1)
        segments.append({
            "id": f"seg_{i + 1:02d}",
            "name": segment_names[name_idx],
            "length_km": round(seg_distance, 2),
            "lanes": random.choice([3, 4, 4, 4, 6]),
            "speed_limit": random.choice([40, 50, 50, 60, 60]),
        })
    return segments


def generate_route_data(
    origin: dict,
    destination: dict,
    route_key: Optional[str] = None,
) -> dict:
    """Generate route data between two points.

    Args:
        origin: {"lat": float, "lng": float, "name": str}
        destination: {"lat": float, "lng": float, "name": str}
        route_key: Optional template key. If None, generates a dynamic route.

    Returns:
        Route data with waypoints, segments, distance, and ETA.
    """
    if route_key and route_key in ROUTE_TEMPLATES:
        template = ROUTE_TEMPLATES[route_key]
        return {
            "route_name": template["name"],
            "waypoints": template["waypoints"],
            "segments": template["segments"],
            "distance_km": template["distance_km"],
            "base_eta_minutes": template["base_eta_minutes"],
            "origin": origin,
            "destination": destination,
        }

    # Dynamic route generation
    waypoints = _generate_dynamic_waypoints(
        origin["lat"], origin["lng"],
        destination["lat"], destination["lng"],
    )
    segments = _generate_dynamic_segments(waypoints)
    distance_km = round(sum(s["length_km"] for s in segments), 1)
    avg_speed = 35  # km/h average urban speed
    eta_minutes = round((distance_km / avg_speed) * 60, 1)

    route_name = f"{origin.get('name', 'Origin')} → {destination.get('name', 'Destination')} via Main Corridor"

    return {
        "route_name": route_name,
        "waypoints": waypoints,
        "segments": segments,
        "distance_km": distance_km,
        "base_eta_minutes": eta_minutes,
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
    # Check if we're using the predefined Delhi route
    if (abs(origin.get("lat", 0) - 28.6315) < 0.01 and
        abs(destination.get("lat", 0) - 28.5672) < 0.01):
        # Use predefined alternative template
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

    # Dynamic alternative route — create a wider arc path
    waypoints = _generate_dynamic_waypoints(
        origin["lat"], origin["lng"],
        destination["lat"], destination["lng"],
        num_waypoints=9,
        offset_scale=0.008,  # Wider offsets for a different path
    )

    # Bias the arc outward (add perpendicular offset to middle waypoints)
    mid = len(waypoints) // 2
    d_lat = destination["lat"] - origin["lat"]
    d_lng = destination["lng"] - origin["lng"]
    # Perpendicular direction for the arc
    perp_lat = -d_lng * 0.15
    perp_lng = d_lat * 0.15
    for i in range(1, len(waypoints) - 1):
        # Parabolic weighting — strongest at midpoint
        t = 1.0 - abs(i - mid) / mid
        waypoints[i][0] = round(waypoints[i][0] + perp_lat * t, 6)
        waypoints[i][1] = round(waypoints[i][1] + perp_lng * t, 6)

    segments = _generate_dynamic_segments(waypoints, _ALT_SEGMENT_NAMES)
    distance_km = round(sum(s["length_km"] for s in segments), 1)
    avg_speed = 40  # Wider roads on alternative route
    eta_minutes = round((distance_km / avg_speed) * 60, 1)

    route_name = f"{origin.get('name', 'Origin')} → {destination.get('name', 'Destination')} via Bypass Corridor"

    return {
        "route_name": route_name,
        "waypoints": waypoints,
        "segments": segments,
        "distance_km": distance_km,
        "base_eta_minutes": eta_minutes,
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
