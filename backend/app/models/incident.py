"""Incident model for emergency event simulation."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text, ForeignKey

from app.database import Base


class IncidentType(str, enum.Enum):
    """Types of incidents that can be simulated."""
    MAJOR_ACCIDENT = "major_accident"
    ROAD_BLOCK = "road_block"
    HEAVY_RAIN = "heavy_rain"
    FESTIVAL_TRAFFIC = "festival_traffic"
    SIGNAL_FAILURE = "signal_failure"
    MULTIPLE_EMERGENCY_VEHICLES = "multiple_emergency_vehicles"


class IncidentSeverity(str, enum.Enum):
    """Incident severity levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, enum.Enum):
    """Incident lifecycle states."""
    ACTIVE = "active"
    RESOLVED = "resolved"


class Incident(Base):
    """Emergency incident for simulation."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mission_id = Column(Integer, ForeignKey("missions.id"), nullable=True, index=True)
    incident_type = Column(Enum(IncidentType), nullable=False)
    severity = Column(Enum(IncidentSeverity), nullable=False, default=IncidentSeverity.HIGH)
    status = Column(Enum(IncidentStatus), nullable=False, default=IncidentStatus.ACTIVE)

    # Location
    location_name = Column(String(200), nullable=False)
    location_lat = Column(Float, nullable=False)
    location_lng = Column(Float, nullable=False)
    segment_id = Column(String(50), nullable=True)
    segment_name = Column(String(200), nullable=True)

    # Impact details
    affected_lanes = Column(Integer, nullable=True)
    total_lanes = Column(Integer, nullable=True)
    estimated_delay_minutes = Column(Float, nullable=True)
    speed_before_kmh = Column(Float, nullable=True)
    speed_after_kmh = Column(Float, nullable=True)
    congestion_before = Column(Float, nullable=True)
    congestion_after = Column(Float, nullable=True)

    # Description
    description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
