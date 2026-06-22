"""Incident simulation routes: create, list, resolve incidents."""

import random
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_factory
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.incident import Incident, IncidentType, IncidentSeverity, IncidentStatus
from app.models.mission import Mission, MissionStatus
from app.schemas.incident import IncidentSimulateRequest, IncidentResponse, IncidentListResponse
from app.services.ws_manager import ws_manager
from data.traffic_sim import add_incident, clear_incidents, get_traffic_scenario

logger = logging.getLogger("jeevanmarg.incidents")

router = APIRouter(prefix="/api/v1/incidents", tags=["Incidents"])

# Incident generation profiles for each type
INCIDENT_PROFILES = {
    "major_accident": {
        "severity": IncidentSeverity.HIGH,
        "affected_lanes_range": (2, 4),
        "total_lanes": 4,
        "delay_range": (6, 12),
        "speed_after_range": (5, 12),
        "descriptions": [
            "Multi-vehicle collision causing severe backup and lane closures",
            "Head-on collision between truck and bus, emergency services on scene",
            "Chain reaction accident involving 4 vehicles, debris blocking lanes",
        ],
        "locations": [
            {"name": "Lodhi Road Junction", "lat_offset": -0.020, "lng_offset": -0.005, "segment_id": "seg_04", "segment_name": "Lodhi Road"},
            {"name": "Safdarjung Flyover", "lat_offset": -0.030, "lng_offset": -0.008, "segment_id": "seg_05", "segment_name": "Safdarjung Flyover"},
            {"name": "Main Corridor Segment 3", "lat_offset": -0.012, "lng_offset": -0.004, "segment_id": "seg_03", "segment_name": "Mid-Corridor Junction"},
        ],
    },
    "road_block": {
        "severity": IncidentSeverity.MEDIUM,
        "affected_lanes_range": (1, 3),
        "total_lanes": 4,
        "delay_range": (4, 8),
        "speed_after_range": (10, 20),
        "descriptions": [
            "Road construction barricade blocking westbound lanes",
            "Police checkpoint blocking main corridor, diversions in place",
            "Utility work blocking two lanes, flaggers directing traffic",
        ],
        "locations": [
            {"name": "Corridor Midpoint", "lat_offset": -0.015, "lng_offset": -0.003, "segment_id": "seg_03", "segment_name": "Mid-Corridor"},
            {"name": "Near Destination Approach", "lat_offset": -0.040, "lng_offset": -0.005, "segment_id": "seg_06", "segment_name": "Destination Approach"},
        ],
    },
    "heavy_rain": {
        "severity": IncidentSeverity.MEDIUM,
        "affected_lanes_range": (0, 0),
        "total_lanes": 4,
        "delay_range": (3, 7),
        "speed_after_range": (15, 25),
        "descriptions": [
            "Heavy rainfall causing waterlogging and reduced visibility across corridor",
            "Monsoon-level downpour flooding underpasses and reducing speeds",
            "Torrential rain with 50mm/hr intensity, hydroplaning risk on all lanes",
        ],
        "locations": [
            {"name": "Corridor-Wide", "lat_offset": -0.020, "lng_offset": -0.005, "segment_id": "seg_04", "segment_name": "Central Corridor"},
        ],
    },
    "festival_traffic": {
        "severity": IncidentSeverity.MEDIUM,
        "affected_lanes_range": (1, 2),
        "total_lanes": 4,
        "delay_range": (5, 10),
        "speed_after_range": (8, 18),
        "descriptions": [
            "Festival procession blocking main road, thousands of pedestrians in corridor",
            "Religious celebration causing mass gathering, road closures in effect",
            "Cultural parade occupying two lanes, heavy pedestrian overflow on remaining lanes",
        ],
        "locations": [
            {"name": "Central Corridor Area", "lat_offset": -0.018, "lng_offset": -0.004, "segment_id": "seg_03", "segment_name": "Central Area"},
            {"name": "Near Origin Zone", "lat_offset": -0.005, "lng_offset": -0.002, "segment_id": "seg_02", "segment_name": "Origin Approach"},
        ],
    },
    "signal_failure": {
        "severity": IncidentSeverity.LOW,
        "affected_lanes_range": (0, 0),
        "total_lanes": 4,
        "delay_range": (3, 6),
        "speed_after_range": (12, 22),
        "descriptions": [
            "Traffic signal malfunction at major intersection, manual direction by traffic police",
            "Complete signal system failure at junction, causing stop-and-go gridlock",
            "Power outage disabling traffic signals at 3 consecutive intersections",
        ],
        "locations": [
            {"name": "Key Junction", "lat_offset": -0.025, "lng_offset": -0.006, "segment_id": "seg_05", "segment_name": "Junction Flyover"},
            {"name": "Corridor Intersection", "lat_offset": -0.010, "lng_offset": -0.003, "segment_id": "seg_03", "segment_name": "Corridor Intersection"},
        ],
    },
    "multiple_emergency_vehicles": {
        "severity": IncidentSeverity.HIGH,
        "affected_lanes_range": (1, 2),
        "total_lanes": 4,
        "delay_range": (4, 8),
        "speed_after_range": (10, 18),
        "descriptions": [
            "Multiple ambulances and fire trucks responding to nearby emergency, corridor congested",
            "Emergency vehicle convoy blocking right lane, civilian vehicles struggling to yield",
            "Police and fire department response blocking two lanes, helicopter overhead",
        ],
        "locations": [
            {"name": "Emergency Response Zone", "lat_offset": -0.022, "lng_offset": -0.005, "segment_id": "seg_04", "segment_name": "Emergency Zone"},
        ],
    },
}


def _generate_incident_data(
    incident_type: str,
    mission: Mission | None = None,
) -> dict:
    """Generate realistic incident data based on type and optional mission context."""
    profile = INCIDENT_PROFILES.get(incident_type)
    if not profile:
        raise ValueError(f"Unknown incident type: {incident_type}")

    location = random.choice(profile["locations"])

    # If mission exists, offset from mission origin; otherwise use Delhi defaults
    if mission:
        base_lat = mission.origin_lat
        base_lng = mission.origin_lng
    else:
        base_lat = 28.6315  # Default Delhi
        base_lng = 77.2167

    lat = base_lat + location["lat_offset"] + random.uniform(-0.003, 0.003)
    lng = base_lng + location["lng_offset"] + random.uniform(-0.003, 0.003)

    affected_lanes_min, affected_lanes_max = profile["affected_lanes_range"]
    affected_lanes = random.randint(affected_lanes_min, affected_lanes_max) if affected_lanes_max > 0 else 0
    total_lanes = profile["total_lanes"]

    delay_min, delay_max = profile["delay_range"]
    delay = round(random.uniform(delay_min, delay_max), 1)

    speed_min, speed_max = profile["speed_after_range"]
    speed_after = round(random.uniform(speed_min, speed_max), 1)
    speed_before = round(random.uniform(38, 48), 1)

    congestion_before = round(random.uniform(0.05, 0.15), 3)
    congestion_after = round(random.uniform(0.55, 0.85), 3)

    return {
        "incident_type": IncidentType(incident_type),
        "severity": profile["severity"],
        "status": IncidentStatus.ACTIVE,
        "location_name": location["name"],
        "location_lat": round(lat, 6),
        "location_lng": round(lng, 6),
        "segment_id": location["segment_id"],
        "segment_name": location["segment_name"],
        "affected_lanes": affected_lanes,
        "total_lanes": total_lanes,
        "estimated_delay_minutes": delay,
        "speed_before_kmh": speed_before,
        "speed_after_kmh": speed_after,
        "congestion_before": congestion_before,
        "congestion_after": congestion_after,
        "description": random.choice(profile["descriptions"]),
    }


@router.post("/simulate", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def simulate_incident(
    request: IncidentSimulateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Simulate an emergency incident.

    Creates an incident record, updates traffic simulation, and broadcasts via WebSocket.
    If a mission_id is provided, the incident is linked to that mission and triggers
    trust score recalculation.
    """
    if request.incident_type not in INCIDENT_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid incident type. Must be one of: {list(INCIDENT_PROFILES.keys())}",
        )

    # Check if mission exists (if provided)
    mission = None
    if request.mission_id:
        result = await db.execute(select(Mission).where(Mission.id == request.mission_id))
        mission = result.scalar_one_or_none()
        if not mission:
            raise HTTPException(status_code=404, detail="Mission not found")

    # Generate incident data
    incident_data = _generate_incident_data(request.incident_type, mission)
    incident_data["mission_id"] = request.mission_id

    # Create incident record
    incident = Incident(**incident_data)
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    logger.info(f"Incident simulated: {incident.incident_type.value} at {incident.location_name}")

    # Update traffic simulation with incident
    add_incident({
        "id": incident.id,
        "type": incident.incident_type.value,
        "segment_id": incident.segment_id,
        "severity": incident.severity.value,
        "congestion": incident.congestion_after,
        "speed_kmh": incident.speed_after_kmh,
        "affected_lanes": incident.affected_lanes,
        "total_lanes": incident.total_lanes,
    })

    # If linked to a mission, degrade it
    if mission:
        mission.status = MissionStatus.DEGRADED
        await db.commit()

        # Trigger degraded agent workflow dynamically in the background!
        from app.routers.missions import _run_mission_background
        background_tasks.add_task(
            _run_mission_background,
            mission_id=mission.id,
            origin={"name": mission.origin_name, "lat": mission.origin_lat, "lng": mission.origin_lng},
            destination={"name": mission.destination_name, "lat": mission.destination_lat, "lng": mission.destination_lng},
            scenario_sequence=["degraded"],
        )

    # Broadcast incident event via WebSocket
    incident_event = {
        "type": "incident_created",
        "incident": {
            "id": incident.id,
            "incident_type": incident.incident_type.value,
            "severity": incident.severity.value,
            "location_name": incident.location_name,
            "location_lat": incident.location_lat,
            "location_lng": incident.location_lng,
            "segment_id": incident.segment_id,
            "segment_name": incident.segment_name,
            "affected_lanes": incident.affected_lanes,
            "total_lanes": incident.total_lanes,
            "estimated_delay_minutes": incident.estimated_delay_minutes,
            "speed_before_kmh": incident.speed_before_kmh,
            "speed_after_kmh": incident.speed_after_kmh,
            "congestion_before": incident.congestion_before,
            "congestion_after": incident.congestion_after,
            "description": incident.description,
        },
        "mission_id": request.mission_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if request.mission_id:
        await ws_manager.broadcast_to_mission(request.mission_id, incident_event)
    else:
        await ws_manager.broadcast_global(incident_event)

    return IncidentResponse.model_validate(incident)


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    status_filter: str | None = None,
    mission_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all incidents, optionally filtered by status or mission."""
    query = select(Incident).order_by(desc(Incident.created_at))
    if status_filter:
        query = query.where(Incident.status == IncidentStatus(status_filter))
    if mission_id:
        query = query.where(Incident.mission_id == mission_id)
    result = await db.execute(query)
    incidents = result.scalars().all()
    return IncidentListResponse(
        incidents=[IncidentResponse.model_validate(i) for i in incidents],
        total=len(incidents),
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific incident by ID."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse.model_validate(incident)


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve an incident and restore traffic conditions."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status == IncidentStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Incident already resolved")

    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(incident)

    # Clear incidents from traffic simulation
    clear_incidents()

    # Broadcast resolution event
    resolve_event = {
        "type": "incident_resolved",
        "incident_id": incident.id,
        "mission_id": incident.mission_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if incident.mission_id:
        await ws_manager.broadcast_to_mission(incident.mission_id, resolve_event)
    else:
        await ws_manager.broadcast_global(resolve_event)

    return IncidentResponse.model_validate(incident)
