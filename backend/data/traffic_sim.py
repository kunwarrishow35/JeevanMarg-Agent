"""Simulated traffic data generator — incident-aware."""

import random
import math
from datetime import datetime, timezone
from typing import Optional


# Segment-level traffic profiles
_SEGMENT_PROFILES: dict[str, dict] = {}

# Scenario overrides
_active_scenario: Optional[str] = None

# Active incidents affecting traffic
_active_incidents: list[dict] = []


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


def add_incident(incident: dict) -> None:
    """Add an active incident that affects traffic.

    Args:
        incident: dict with keys: id, type, segment_id, severity,
                  congestion, speed_kmh, affected_lanes, total_lanes
    """
    _active_incidents.append(incident)
    # Also set scenario to degraded when incidents are added
    global _active_scenario
    _active_scenario = "degraded"


def clear_incidents() -> None:
    """Clear all active incidents and restore healthy scenario."""
    global _active_scenario
    _active_incidents.clear()
    _active_scenario = "healthy"


def get_active_incidents() -> list[dict]:
    """Get all active incidents."""
    return list(_active_incidents)


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

    # Find incident-affected segments
    incident_segments = []
    for inc in _active_incidents:
        for seg_status in segment_statuses:
            if seg_status["segment_id"] == inc.get("segment_id"):
                incident_segments.append({
                    "segment_id": seg_status["segment_id"],
                    "segment_name": seg_status["segment_name"],
                    "incident_type": inc.get("type"),
                    "incident_severity": inc.get("severity"),
                })

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
        "active_incidents": incident_segments,
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
    # Check for active incidents first
    if _active_incidents:
        risk_level = random.uniform(0.6, 0.85)
        risk_category = "high"
        incidents = []
        for inc in _active_incidents:
            incidents.append({
                "type": inc.get("type", "unknown"),
                "severity": inc.get("severity", "high"),
                "description": f"{inc.get('type', 'Incident').replace('_', ' ').title()} affecting {inc.get('segment_id', 'corridor')}",
                "lat": lat + random.uniform(-0.005, 0.005),
                "lng": lng + random.uniform(-0.005, 0.005),
                "impact_radius_km": 1.5,
                "estimated_clearance_minutes": 45,
                "affected_lanes": inc.get("affected_lanes", 2),
                "total_lanes": inc.get("total_lanes", 4),
            })
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "center": {"lat": lat, "lng": lng},
            "radius_km": radius_km,
            "risk_level": round(risk_level, 3),
            "risk_category": risk_category,
            "incidents": incidents,
            "historical_pattern": "congestion prone",
        }

    # Fall back to scenario-based assessment
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
    # Check if any incident targets this segment
    incident_match = None
    for inc in _active_incidents:
        if inc.get("segment_id") == segment_id:
            incident_match = inc
            break

    # Base speed by segment type
    base_speed = 45.0  # km/h default

    if incident_match:
        # Incident directly affecting this segment
        current_speed = incident_match.get("speed_kmh", random.uniform(8, 15))
        flow_status = "stop_and_go"
        congestion = incident_match.get("congestion", random.uniform(0.7, 0.9))
    elif _active_scenario == "degraded" and segment_id in ("seg_04", "seg_05"):
        # Legacy degraded scenario segments
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
        "incident_affected": incident_match is not None,
    }


def _generate_segment_traffic(segment_id: str, segment: dict) -> dict:
    """Generate traffic data for a single segment based on scenario and incidents."""
    speed_limit = segment.get("speed_limit", 50)

    # Check if an incident targets this segment
    incident_match = None
    for inc in _active_incidents:
        if inc.get("segment_id") == segment_id:
            incident_match = inc
            break

    if incident_match:
        # Direct incident on this segment — severe impact
        congestion = incident_match.get("congestion", random.uniform(0.7, 0.9))
        speed = min(incident_match.get("speed_kmh", 10), speed_limit * (1 - congestion * 0.8))
        status_str = "incident"
        incident_type = incident_match.get("type", "unknown")
    elif _active_incidents and _active_scenario == "degraded":
        # Nearby segments affected by spill-over congestion
        congestion = random.uniform(0.25, 0.45)
        speed = speed_limit * (1 - congestion * 0.6)
        status_str = "slow"
        incident_type = None
    elif _active_scenario == "degraded" and segment_id in ("seg_04", "seg_05"):
        # Legacy degraded scenario for specific segments
        congestion = random.uniform(0.7, 0.9)
        speed = speed_limit * (1 - congestion * 0.8)
        status_str = "congested"
        incident_type = None
    elif _active_scenario == "degraded":
        congestion = random.uniform(0.3, 0.5)
        speed = speed_limit * (1 - congestion * 0.6)
        status_str = "slow"
        incident_type = None
    elif _active_scenario == "recovered":
        congestion = random.uniform(0.05, 0.15)
        speed = speed_limit * (1 - congestion * 0.3)
        status_str = "clear"
        incident_type = None
    else:
        # Healthy default
        congestion = random.uniform(0.05, 0.15)
        speed = speed_limit * (1 - congestion * 0.3)
        status_str = "clear"
        incident_type = None

    result = {
        "segment_id": segment_id,
        "segment_name": segment.get("name", segment_id),
        "congestion_level": round(congestion, 3),
        "current_speed_kmh": round(max(speed, 5), 1),
        "speed_limit_kmh": speed_limit,
        "status": status_str,
        "delay_seconds": round(congestion * 120, 0),
        "incident_affected": incident_match is not None,
    }
    if incident_type:
        result["incident_type"] = incident_type

    return result
