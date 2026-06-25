"""Mission routes: create, list, start, and query missions."""

import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_factory
from app.middleware.auth import get_current_user, require_dispatcher
from app.models.user import User
from app.models.mission import (
    Mission, MissionStatus, AgentActivity, AgentState,
    MCPCall, Approval, ApprovalStatus, RouteData,
)
from app.schemas.mission import (
    MissionCreate, MissionResponse, MissionListResponse,
    AgentActivityResponse, MCPCallResponse, RouteDataResponse,
)
from app.services.ws_manager import ws_manager
from app.routers.system import update_agent_state, update_mcp_state, update_mcp_last_call

logger = logging.getLogger("jeevanmarg.missions")

router = APIRouter(prefix="/api/v1/missions", tags=["Missions"])


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(
    request: MissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_dispatcher),
):
    """Create a new emergency corridor mission."""
    mission_code = f"JM-{uuid.uuid4().hex[:8].upper()}"

    mission = Mission(
        mission_code=mission_code,
        status=MissionStatus.CREATED,
        origin_name=request.origin_name,
        origin_lat=request.origin_lat,
        origin_lng=request.origin_lng,
        destination_name=request.destination_name,
        destination_lat=request.destination_lat,
        destination_lng=request.destination_lng,
        created_by=current_user.id,
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)

    # Generate and persist primary route at mission creation
    from data.route_sim import generate_route_data
    from app.models.mission import RouteData

    origin = {"lat": mission.origin_lat, "lng": mission.origin_lng, "name": mission.origin_name}
    destination = {"lat": mission.destination_lat, "lng": mission.destination_lng, "name": mission.destination_name}
    
    is_cp_aiims = (abs(mission.origin_lat - 28.6315) < 0.01 and abs(mission.destination_lat - 28.5672) < 0.01)
    route_key = "connaught_to_aiims" if is_cp_aiims else None
    
    route_res = generate_route_data(origin, destination, route_key=route_key)
    
    route_db = RouteData(
        mission_id=mission.id,
        route_type="primary",
        route_name=route_res.get("route_name", "Primary Route"),
        waypoints=route_res.get("waypoints", []),
        segments=route_res.get("segments"),
        distance_km=route_res.get("distance_km"),
        eta_minutes=route_res.get("base_eta_minutes"),
        is_active=1,
        route_source=route_res.get("route_source", "Synthetic"),
    )
    db.add(route_db)
    await db.commit()
    logger.info(f"[Route Persistence] Successfully persisted primary route for mission {mission.id}. Source: {route_db.route_source}")

    # Broadcast mission_created event
    await ws_manager.broadcast_global({
        "type": "mission_created",
        "mission_id": mission.id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Broadcast route_generated event
    await ws_manager.broadcast_global({
        "type": "route_generated",
        "mission_id": mission.id,
        "route_type": "primary",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"[WebSocket] Successfully broadcast route_generated event for mission {mission.id}")

    return MissionResponse.model_validate(mission)


@router.get("", response_model=MissionListResponse)
async def list_missions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all missions, most recent first."""
    result = await db.execute(
        select(Mission).order_by(desc(Mission.created_at))
    )
    missions = result.scalars().all()
    return MissionListResponse(
        missions=[MissionResponse.model_validate(m) for m in missions],
        total=len(missions),
    )


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific mission by ID."""
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return MissionResponse.model_validate(mission)


@router.post("/{mission_id}/start")
async def start_mission(
    mission_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_dispatcher),
):
    """Start agent execution for a mission. Runs in background, streams via WebSocket."""
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    if mission.status not in (MissionStatus.CREATED, MissionStatus.COMPLETED):
        raise HTTPException(status_code=400, detail=f"Mission is already {mission.status.value}")

    mission.status = MissionStatus.RUNNING
    await db.commit()

    # Start agent orchestration in background
    background_tasks.add_task(
        _run_mission_background,
        mission_id=mission.id,
        origin={"name": mission.origin_name, "lat": mission.origin_lat, "lng": mission.origin_lng},
        destination={"name": mission.destination_name, "lat": mission.destination_lat, "lng": mission.destination_lng},
        scenario_sequence=["healthy"],
    )

    return {"status": "started", "mission_id": mission.id, "message": "Agent orchestration started"}


@router.get("/{mission_id}/activities", response_model=list[AgentActivityResponse])
async def get_mission_activities(
    mission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all agent activity logs for a mission."""
    result = await db.execute(
        select(AgentActivity)
        .where(AgentActivity.mission_id == mission_id)
        .order_by(AgentActivity.timestamp)
    )
    activities = result.scalars().all()
    return [AgentActivityResponse.model_validate(a) for a in activities]


@router.get("/{mission_id}/mcp-calls", response_model=list[MCPCallResponse])
async def get_mission_mcp_calls(
    mission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all MCP call logs for a mission."""
    result = await db.execute(
        select(MCPCall)
        .where(MCPCall.mission_id == mission_id)
        .order_by(MCPCall.timestamp)
    )
    calls = result.scalars().all()
    return [MCPCallResponse.model_validate(c) for c in calls]


@router.get("/{mission_id}/routes", response_model=list[RouteDataResponse])
async def get_mission_routes(
    mission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get route data for a mission."""
    result = await db.execute(
        select(RouteData)
        .where(RouteData.mission_id == mission_id)
        .order_by(RouteData.created_at)
    )
    routes = result.scalars().all()
    return [RouteDataResponse.model_validate(r) for r in routes]


async def _run_mission_background(
    mission_id: int,
    origin: dict,
    destination: dict,
    scenario_sequence: list[str] = None,
) -> None:
    """Background task that runs the agent orchestration."""
    from app.config import settings
    from agents.orchestrator import MissionOrchestrator

    logger.info(f"Starting background mission orchestration for mission {mission_id}")

    async with async_session_factory() as db:
        try:
            # Get mission
            result = await db.execute(select(Mission).where(Mission.id == mission_id))
            mission = result.scalar_one_or_none()
            if not mission:
                logger.error(f"Mission {mission_id} not found")
                return

            # Initialize orchestrator
            api_key = settings.GOOGLE_API_KEY or "demo-key"
            orchestrator = MissionOrchestrator(
                google_api_key=api_key,
                model=settings.GEMINI_MODEL,
            )

            # Event callback to persist and broadcast events
            async def handle_event(event: dict) -> None:
                event_type = event.get("type", "")

                # If this is an approval request, save to db first to get the database ID
                if event_type == "approval_requested":
                    async with async_session_factory() as event_db:
                        approval = Approval(
                            mission_id=mission_id,
                            approval_type=event.get("approval_type", "route_change"),
                            title=event.get("title", "Recovery Recommendation"),
                            description=event.get("description"),
                            trust_score_before=event.get("trust_score_before"),
                            trust_score_after=event.get("trust_score_after"),
                            eta_before=event.get("eta_before"),
                            eta_after=event.get("eta_after"),
                        )
                        event_db.add(approval)
                        await event_db.commit()
                        await event_db.refresh(approval)
                        event["approval_id"] = approval.id

                        # Update mission status to awaiting approval
                        result = await event_db.execute(
                            select(Mission).where(Mission.id == mission_id)
                        )
                        m = result.scalar_one_or_none()
                        if m:
                            m.status = MissionStatus.AWAITING_APPROVAL
                            await event_db.commit()

                # Broadcast via WebSocket
                await ws_manager.broadcast_to_mission(mission_id, event)

                # Persist agent activities
                if event_type in ("agent_started", "agent_completed", "agent_reasoning"):
                    async with async_session_factory() as event_db:
                        activity = AgentActivity(
                            mission_id=mission_id,
                            agent_name=event.get("agent_name", "unknown"),
                            agent_state=AgentState.RUNNING if event_type == "agent_started"
                                       else AgentState.COMPLETED if event_type == "agent_completed"
                                       else AgentState.RUNNING,
                            action=event.get("action", event_type),
                            result=event.get("result"),
                            reasoning=event.get("reasoning"),
                        )
                        event_db.add(activity)
                        await event_db.commit()

                    # Update system state
                    agent_name = event.get("agent_name", "")
                    if event_type == "agent_started":
                        update_agent_state(agent_name, "running", event.get("action"))
                    elif event_type == "agent_completed":
                        update_agent_state(agent_name, "completed", event.get("action"))

                # Persist MCP calls
                elif event_type == "mcp_call_completed":
                    async with async_session_factory() as event_db:
                        mcp_call = MCPCall(
                            mission_id=mission_id,
                            server_name=event.get("server_name", "unknown"),
                            tool_name=event.get("tool_name", "unknown"),
                            request_payload=event.get("request_payload"),
                            response_payload=event.get("response_payload"),
                            latency_ms=event.get("latency_ms"),
                        )
                        event_db.add(mcp_call)
                        await event_db.commit()

                    update_mcp_state(event.get("server_name", ""), "connected")
                    update_mcp_last_call(event.get("server_name", ""))

                # Update trust score on mission
                elif event_type == "trust_score_updated":
                    async with async_session_factory() as event_db:
                        result = await event_db.execute(
                            select(Mission).where(Mission.id == mission_id)
                        )
                        m = result.scalar_one_or_none()
                        if m:
                            m.trust_score = event.get("trust_score")
                            m.trust_level = event.get("trust_level")
                            m.corridor_health = event.get("corridor_health")
                            m.eta_confidence = event.get("eta_confidence")
                            factors = event.get("factors", {})
                            m.congestion_factor = factors.get("congestion")
                            m.route_stability_factor = factors.get("route_stability")
                            m.traffic_volatility_factor = factors.get("traffic_volatility")
                            m.corridor_continuity_factor = factors.get("corridor_continuity")
                            m.eta_confidence_factor = factors.get("eta_confidence")

                            if m.trust_score and m.trust_score < 70:
                                m.status = MissionStatus.DEGRADED
                            await event_db.commit()

                # Create approval request (handled at the start of handle_event)
                elif event_type == "approval_requested":
                    pass

                # Store route data
                elif event_type == "recovery_recommended":
                    rec = event.get("recommendation", {})
                    alt_route = rec.get("alternative_route", {})
                    if alt_route.get("waypoints"):
                        async with async_session_factory() as event_db:
                            from sqlalchemy import delete
                            await event_db.execute(
                                delete(RouteData).where(RouteData.mission_id == mission_id, RouteData.route_type == "alternative")
                            )
                            route = RouteData(
                                mission_id=mission_id,
                                route_type="alternative",
                                route_name=alt_route.get("route_name", "Alternative Route"),
                                waypoints=alt_route.get("waypoints", []),
                                segments=alt_route.get("segments"),
                                distance_km=alt_route.get("distance_km"),
                                eta_minutes=alt_route.get("base_eta_minutes"),
                                is_active=0,
                                route_source=alt_route.get("route_source", "OSRM" if "OSRM" in alt_route.get("route_source", "") or not alt_route.get("route_source") else "Synthetic Fallback"),
                            )
                            event_db.add(route)
                            await event_db.commit()
                            logger.info(f"[Route Persistence] Successfully persisted alternative route for mission {mission_id}. Source: {route.route_source}")

                # Broadcast via WebSocket after persisting to DB to avoid races
                await ws_manager.broadcast_to_mission(mission_id, event)

            orchestrator.set_event_callback(handle_event)

            # Store primary route first
            if scenario_sequence is None:
                scenario_sequence = ["healthy", "degraded"]

            # Run mission orchestration
            results = await orchestrator.run_mission(
                mission_id=mission_id,
                origin=origin,
                destination=destination,
                scenario_sequence=scenario_sequence,
            )

            # Store primary route
            if "healthy" in scenario_sequence:
                healthy_result = results.get("healthy", {})
                route_data = healthy_result.get("route", {})
                if route_data.get("waypoints"):
                    async with async_session_factory() as route_db:
                        from sqlalchemy import delete
                        await route_db.execute(
                            delete(RouteData).where(RouteData.mission_id == mission_id, RouteData.route_type == "primary")
                        )
                        route = RouteData(
                            mission_id=mission_id,
                            route_type="primary",
                            route_name=route_data.get("route_name", "Primary Route"),
                            waypoints=route_data.get("waypoints", []),
                            segments=route_data.get("segments"),
                            distance_km=route_data.get("distance_km"),
                            eta_minutes=route_data.get("eta", {}).get("eta_minutes"),
                            is_active=1,
                            route_source=route_data.get("route_source", "OSRM" if "OSRM" in route_data.get("route_source", "") or not route_data.get("route_source") else "Synthetic Fallback"),
                        )
                        route_db.add(route)
                        await route_db.commit()
                        logger.info(f"[Route Persistence] Successfully persisted primary route during background run for mission {mission_id}. Source: {route.route_source}")

                    # Broadcast route_generated event after successful persist to DB
                    await ws_manager.broadcast_to_mission(mission_id, {
                        "type": "route_generated",
                        "mission_id": mission_id,
                        "route_type": "primary",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    logger.info(f"[WebSocket] Successfully broadcast route_generated event during background run for mission {mission_id}")

            # Update final mission status
            async with async_session_factory() as final_db:
                result = await final_db.execute(
                    select(Mission).where(Mission.id == mission_id)
                )
                m = result.scalar_one_or_none()
                if m and m.status == MissionStatus.RUNNING and "degraded" in scenario_sequence:
                    m.status = MissionStatus.COMPLETED
                    await final_db.commit()

            # Send mission completed event only if status is COMPLETED
            async with async_session_factory() as final_db:
                result = await final_db.execute(
                    select(Mission).where(Mission.id == mission_id)
                )
                m = result.scalar_one_or_none()
                if m and m.status == MissionStatus.COMPLETED:
                    await ws_manager.broadcast_to_mission(mission_id, {
                        "type": "mission_completed",
                        "mission_id": mission_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            logger.info(f"Mission {mission_id} orchestration completed")

        except Exception as e:
            logger.error(f"Mission {mission_id} failed: {e}", exc_info=True)
            async with async_session_factory() as err_db:
                result = await err_db.execute(
                    select(Mission).where(Mission.id == mission_id)
                )
                m = result.scalar_one_or_none()
                if m:
                    m.status = MissionStatus.FAILED
                    await err_db.commit()

            await ws_manager.broadcast_to_mission(mission_id, {
                "type": "mission_failed",
                "mission_id": mission_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Reset agent states
            for agent in ["emergency_coordinator", "route_intelligence",
                         "traffic_intelligence", "trust_score", "recovery"]:
                update_agent_state(agent, "failed")
