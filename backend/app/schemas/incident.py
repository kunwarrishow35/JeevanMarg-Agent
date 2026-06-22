"""Incident Pydantic schemas for API serialization."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class IncidentSimulateRequest(BaseModel):
    """Request to simulate a new incident."""
    incident_type: str = Field(
        ...,
        description="Type of incident: major_accident, road_block, heavy_rain, festival_traffic, signal_failure, multiple_emergency_vehicles"
    )
    mission_id: Optional[int] = Field(None, description="Associated mission ID (optional)")


class IncidentResponse(BaseModel):
    """Full incident details."""
    id: int
    mission_id: Optional[int] = None
    incident_type: str
    severity: str
    status: str
    location_name: str
    location_lat: float
    location_lng: float
    segment_id: Optional[str] = None
    segment_name: Optional[str] = None
    affected_lanes: Optional[int] = None
    total_lanes: Optional[int] = None
    estimated_delay_minutes: Optional[float] = None
    speed_before_kmh: Optional[float] = None
    speed_after_kmh: Optional[float] = None
    congestion_before: Optional[float] = None
    congestion_after: Optional[float] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IncidentListResponse(BaseModel):
    """List of incidents."""
    incidents: list[IncidentResponse]
    total: int
