"""Simulated traffic data generator for Delhi NCR."""

import random
import math
from datetime import datetime, timezone
from typing import Optional


# Segment-level traffic profiles
_SEGMENT_PROFILES: dict[str, dict] = {}

# Scenario overrides
_active_scenario: Optional[str] = None


def set_traffic_scenario(scenario: str) -> None:
    """Set the active traffic scenario.

    Args:
        scenario: "healthy", "degraded", or "recovered"
    """
    global _active_scenario
    _active_scenario = scenario


def get_traffic_scenario() -> Optional[str]:
    """Get the current traffic scenario."""
    return _active_scenario


def get_traffic_status_data(route_segments: list[dict]) -> dict:
    """Get traffic status for a list of route segments.

    Args:
        route_segments: List of segment dicts with "id", "name", etc.

    Returns:
        Traffic status per segment and overall corridor assessment.
    """
    segment_statuses = []
    total_congestion = 0.0

    for segment in route_segments:
        seg_id = segment.get("id", "unknown")
        status = _generate_segment_traffic(seg_id, segment)
        segment_statuses.append(status)
        total_congestion += status["congestion_level"]

    avg_congestion = total_congestion / max(len(segment_statuses), 1)

    # Determine overall status
    if avg_congestion < 0.2:
        overall_status = "clear"
    elif avg_congestion < 0.4:
        overall_status = "moderate"
    elif avg_congestion < 0.6:
        overall_status = "heavy"
    else:
        overall_status = "severe"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "average_congestion": round(avg_congestion, 3),
        "segments": segment_statuses,
        "corridor_assessment": {
            "is_clear": avg_congestion < 0.3,
            "bottleneck_count": sum(1 for s in segment_statuses if s["congestion_level"] > 0.6),
            "worst_segment": max(segment_statuses, key=lambda s: s["congestion_level"])["segment_id"]
            if segment_statuses else None,
        },
    }


def get_congestion_risk_data(lat: float, lng: float, radius_km: float = 2.0) -> dict:
    """Assess congestion risk in an area.

    Args:
        lat: Center latitude
        lng: Center longitude
        radius_km: Radius to assess

    Returns:
        Congestion risk assessment.
    """
    # Use scenario to determine risk
    if _active_scenario == "degraded":
        risk_level = random.uniform(0.6, 0.85)
        risk_category = "high"
        incidents = [
            {
                "type": "accident",
                "severity": "major",
                "description": "Multi-vehicle collision on Lodhi Road causing severe backup",
                "lat": lat + random.uniform(-0.005, 0.005),
                "lng": lng + random.uniform(-0.005, 0.005),
                "impact_radius_km": 1.5,
                "estimated_clearance_minutes": 45,
            }
        ]
    elif _active_scenario == "recovered":
        risk_level = random.uniform(0.1, 0.25)
        risk_category = "low"
        incidents = []
    else:
        # Healthy scenario
        risk_level = random.uniform(0.05, 0.2)
        risk_category = "low"
        incidents = []

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "risk_level": round(risk_level, 3),
        "risk_category": risk_category,
        "incidents": incidents,
        "historical_pattern": "typically clear" if risk_level < 0.3 else "congestion prone",
    }


def get_segment_speed_data(segment_id: str) -> dict:
    """Get real-time speed data for a route segment.

    Args:
        segment_id: Segment identifier

    Returns:
        Speed and flow data for the segment.
    """
    # Base speed by segment type
    base_speed = 45.0  # km/h default

    if _active_scenario == "degraded" and segment_id in ("seg_04", "seg_05"):
        # These are the congested segments in degraded scenario
        current_speed = random.uniform(8, 15)
        flow_status = "stop_and_go"
        congestion = random.uniform(0.7, 0.9)
    elif _active_scenario == "degraded":
        current_speed = random.uniform(25, 35)
        flow_status = "slow"
        congestion = random.uniform(0.3, 0.5)
    elif _active_scenario == "recovered":
        current_speed = random.uniform(40, 55)
        flow_status = "free_flow"
        congestion = random.uniform(0.05, 0.15)
    else:
        # Healthy
        current_speed = random.uniform(38, 50)
        flow_status = "free_flow"
        congestion = random.uniform(0.05, 0.2)

    return {
        "segment_id": segment_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "current_speed_kmh": round(current_speed, 1),
        "free_flow_speed_kmh": round(base_speed, 1),
        "speed_ratio": round(current_speed / base_speed, 3),
        "congestion_level": round(congestion, 3),
        "flow_status": flow_status,
        "vehicle_density": "high" if congestion > 0.5 else "moderate" if congestion > 0.2 else "low",
    }


def _generate_segment_traffic(segment_id: str, segment: dict) -> dict:
    """Generate traffic data for a single segment based on scenario."""
    speed_limit = segment.get("speed_limit", 50)

    if _active_scenario == "degraded" and segment_id in ("seg_04", "seg_05"):
        # Heavy congestion on specific segments
        congestion = random.uniform(0.7, 0.9)
        speed = speed_limit * (1 - congestion * 0.8)
        status = "congested"
    elif _active_scenario == "degraded":
        # Moderate impact on surrounding segments
        congestion = random.uniform(0.3, 0.5)
        speed = speed_limit * (1 - congestion * 0.6)
        status = "slow"
    elif _active_scenario == "recovered":
        congestion = random.uniform(0.05, 0.15)
        speed = speed_limit * (1 - congestion * 0.3)
        status = "clear"
    else:
        # Healthy default
        congestion = random.uniform(0.05, 0.15)
        speed = speed_limit * (1 - congestion * 0.3)
        status = "clear"

    return {
        "segment_id": segment_id,
        "segment_name": segment.get("name", segment_id),
        "congestion_level": round(congestion, 3),
        "current_speed_kmh": round(max(speed, 5), 1),
        "speed_limit_kmh": speed_limit,
        "status": status,
        "delay_seconds": round(congestion * 120, 0),
    }
