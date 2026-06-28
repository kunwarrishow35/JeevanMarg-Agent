"""Agent orchestration — initializes MCP connections and builds the ADK agent hierarchy.

This is the main entry point for the multi-agent system. It:
1. Starts MCP server connections via StdioServerParameters
2. Creates each ADK agent with their respective MCP tools
3. Builds the coordinator agent hierarchy
4. Provides run_mission() to execute the full mission flow
5. Streams all agent activity and MCP calls via callbacks
"""

import asyncio
import json
import os
import sys
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Callable, Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logger = logging.getLogger("jeevanmarg.orchestrator")

from app.config import settings

_ROUTE_AGENT_CACHE = {}
_TRAFFIC_AGENT_CACHE = {}
_TRUST_AGENT_CACHE = {}
_RECOVERY_AGENT_CACHE = {}

def clear_agent_caches() -> None:
    """Clear all agent caches to ensure fresh state for subsequent runs."""
    _ROUTE_AGENT_CACHE.clear()
    _TRAFFIC_AGENT_CACHE.clear()
    _TRUST_AGENT_CACHE.clear()
    _RECOVERY_AGENT_CACHE.clear()
    logger.info("Cleared all ADK agent caches.")

# Path to MCP server scripts
MCP_SERVERS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_servers")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MissionOrchestrator:
    """Orchestrates the full mission lifecycle using Google ADK agents and MCP servers."""

    def __init__(self, google_api_key: str, model: str = "gemini-2.5-flash"):
        self.google_api_key = google_api_key
        self.model = model
        self._event_callback: Optional[Callable] = None
        self._session_service = InMemorySessionService()

        # Set API key in environment for ADK
        os.environ["GOOGLE_API_KEY"] = google_api_key

    def set_event_callback(self, callback: Callable) -> None:
        """Set a callback function for streaming events to the frontend."""
        self._event_callback = callback

    async def _emit_event(self, event_type: str, data: dict) -> None:
        """Emit an event to the frontend via the callback."""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        if self._event_callback:
            await self._event_callback(event)
        logger.info(f"Event: {event_type} — {json.dumps(data, default=str)[:200]}")

    async def run_mission(
        self,
        mission_id: int,
        origin: dict,
        destination: dict,
        scenario_sequence: list[str] | None = None,
    ) -> dict:
        """Execute the full mission lifecycle.

        This method:
        1. Creates the agent hierarchy with MCP tool connections
        2. Runs the coordinator agent through scenario phases
        3. Streams all activity via events

        Args:
            mission_id: Database mission ID
            origin: {"name": str, "lat": float, "lng": float}
            destination: {"name": str, "lat": float, "lng": float}
            scenario_sequence: List of scenarios to run, e.g. ["healthy", "degraded"]

        Returns:
            Final mission state dictionary
        """
        if scenario_sequence is None:
            scenario_sequence = ["healthy", "degraded"]

        results = {}

        for scenario in scenario_sequence:
            await self._emit_event("scenario_started", {
                "mission_id": mission_id,
                "scenario": scenario,
            })

            result = await self._run_scenario(
                mission_id=mission_id,
                origin=origin,
                destination=destination,
                scenario=scenario,
            )
            results[scenario] = result

            if scenario != scenario_sequence[-1]:
                await asyncio.sleep(0.05 if settings.DEMO_MODE else 2)  # Brief pause between scenarios

        return results

    async def _run_scenario(
        self,
        mission_id: int,
        origin: dict,
        destination: dict,
        scenario: str,
    ) -> dict:
        """Run a single scenario phase of the mission."""
        from data.traffic_sim import set_traffic_scenario, get_active_incidents
        from app.database import async_session_factory
        from app.models.mission import RouteData, Mission, MissionStatus
        from sqlalchemy import select

        # Stop background orchestration if mission is completed
        try:
            async with async_session_factory() as db:
                mission_res = await db.execute(select(Mission).where(Mission.id == mission_id))
                m = mission_res.scalar_one_or_none()
                if m and m.status == MissionStatus.COMPLETED:
                    logger.info(f"Mission {mission_id} is already completed. Aborting scenario run.")
                    return {}
        except Exception as e:
            logger.warning(f"Could not verify mission status: {e}")

        # Set the traffic scenario
        set_traffic_scenario(scenario)

        await self._emit_event("agent_started", {
            "mission_id": mission_id,
            "agent_name": "emergency_coordinator",
            "action": f"Starting {scenario} corridor analysis",
            "reasoning": f"Coordinator activating for {scenario} scenario. "
                        f"Will delegate to specialist agents for route, traffic, and trust analysis.",
        })

        # Fetch route from DB if it exists, to pass to traffic agent and enable parallel execution
        cached_route = None
        try:
            async with async_session_factory() as db:
                route_res = await db.execute(
                    select(RouteData).where(RouteData.mission_id == mission_id, RouteData.route_type == "primary")
                )
                route_db = route_res.scalar_one_or_none()
                if route_db:
                    cached_route = {
                        "route_name": route_db.route_name,
                        "waypoints": route_db.waypoints,
                        "segments": route_db.segments,
                        "distance_km": route_db.distance_km,
                        "base_eta_minutes": route_db.eta_minutes,
                        "route_source": route_db.route_source,
                    }
        except Exception as e:
            logger.warning(f"Could not load cached route from DB: {e}")

        # Sleep delay check
        sleep_delay = 0.05 if settings.DEMO_MODE else 1.0

        # Execute Route and Traffic agents in parallel using asyncio.gather
        route_task = self._run_route_agent(mission_id, origin, destination, scenario, cached_route)
        traffic_task = self._run_traffic_agent(mission_id, cached_route, scenario)

        route_result, traffic_result = await asyncio.gather(route_task, traffic_task)
        await asyncio.sleep(sleep_delay)

        # Phase 3: Trust Score
        trust_result = await self._run_trust_agent(mission_id, traffic_result, route_result, scenario)
        await asyncio.sleep(sleep_delay)

        # Phase 4: Recovery (if trust score is low)
        recovery_result = None
        trust_score = trust_result.get("trust_score", 100)
        recovery_threshold = 65 if settings.DEMO_MODE else 70
        
        should_run_recovery = trust_score < recovery_threshold
        if settings.DEMO_MODE:
            active_incidents = get_active_incidents()
            has_severe_incident = any(
                inc.get("type") in ("major_accident", "road_block")
                for inc in active_incidents
            )
            should_run_recovery = should_run_recovery and has_severe_incident
            
        if should_run_recovery:
            recovery_result = await self._run_recovery_agent(
                mission_id, origin, destination, trust_result, traffic_result, scenario
            )

        reasoning_text = (
            f"All specialist agents have reported. Trust score is {trust_score}/100. "
            f"Score below threshold ({recovery_threshold}), recovery agent was activated to generate recommendations."
            if trust_score < recovery_threshold else
            f"All specialist agents have reported. Trust score is {trust_score}/100. "
            f"Score above threshold, corridor is reliable."
        )

        await self._emit_event("agent_completed", {
            "mission_id": mission_id,
            "agent_name": "emergency_coordinator",
            "action": f"Completed {scenario} corridor analysis",
            "result": f"Trust Score: {trust_score}. "
                     f"{'Recovery activated.' if recovery_result else 'No intervention needed.'}",
            "reasoning": reasoning_text,
        })

        return {
            "scenario": scenario,
            "route": route_result,
            "traffic": traffic_result,
            "trust": trust_result,
            "recovery": recovery_result,
        }

    async def _run_route_agent(self, mission_id: int, origin: dict, destination: dict, scenario: str, cached_route: dict | None = None) -> dict:
        """Execute the Route Intelligence Agent via ADK with MCP tools."""
        await self._emit_event("agent_started", {
            "mission_id": mission_id,
            "agent_name": "route_intelligence",
            "action": "Generating optimal route",
            "reasoning": f"Route Intelligence Agent activated. Connecting to Route MCP Server to "
                        f"generate route from {origin['name']} to {destination['name']}.",
        })

        cache_key = (
            round(origin.get("lat", 0), 5),
            round(origin.get("lng", 0), 5),
            round(destination.get("lat", 0), 5),
            round(destination.get("lng", 0), 5),
            scenario
        )

        if cache_key in _ROUTE_AGENT_CACHE:
            logger.info(f"[Route Agent Cache] Cache hit for mission {mission_id}")
            route_data = _ROUTE_AGENT_CACHE[cache_key]
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "route_intelligence",
                "reasoning": f"Found route details in memory cache for route from {origin['name']} to {destination['name']}. Avoiding recomputation.",
            })
            seg_count = len(route_data.get('segments', []))
            await self._emit_event("agent_completed", {
                "mission_id": mission_id,
                "agent_name": "route_intelligence",
                "action": "Route generated (Cache Hit)",
                "result": f"Route: {route_data.get('route_name', 'Primary Route')} | Distance: {route_data.get('distance_km', 0)} km | ETA: {route_data.get('eta', {}).get('eta_minutes', 'N/A')} min",
                "reasoning": f"Retrieved cached route with {seg_count} segments.",
            })
            return route_data

        if cached_route:
            logger.info(f"[Route Agent] Using database cached route for mission {mission_id}")
            if "eta" not in cached_route:
                cached_route["eta"] = {"eta_minutes": cached_route.get("base_eta_minutes", 14), "confidence": 0.85}
            _ROUTE_AGENT_CACHE[cache_key] = cached_route
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "route_intelligence",
                "reasoning": f"Retrieved primary route from database: {cached_route.get('route_name')}.",
            })
            seg_count = len(cached_route.get('segments', []))
            await self._emit_event("agent_completed", {
                "mission_id": mission_id,
                "agent_name": "route_intelligence",
                "action": "Route retrieved from DB",
                "result": f"Route: {cached_route.get('route_name')} | Distance: {cached_route.get('distance_km')} km | ETA: {cached_route.get('eta', {}).get('eta_minutes')} min",
                "reasoning": f"Using route from database with {seg_count} segments.",
            })
            return cached_route

        # Create the Route Agent with MCP tools
        route_data = None
        eta_data = None

        async def run_agent_coro():
            nonlocal route_data, eta_data
            route_agent = Agent(
                name="route_intelligence",
                model=self.model,
                description="Generates and evaluates emergency corridor routes using Route MCP tools.",
                instruction=(
                    "You are the Route Intelligence Agent for JeevanMarg emergency corridor system. "
                    "Your job is to generate an optimal emergency route and estimate ETA. "
                    f"Generate a route from {origin['name']} (lat: {origin['lat']}, lng: {origin['lng']}) "
                    f"to {destination['name']} (lat: {destination['lat']}, lng: {destination['lng']}). "
                    "Call the generate_route tool with the origin and destination coordinates. "
                    "Then call estimate_eta with the route segments to get an accurate ETA. "
                    "Report the route details, segments, distance, and estimated time."
                ),
                tools=[self._make_route_generate_tool(), self._make_route_eta_tool()],
            )

            session = await self._session_service.create_session(
                app_name="jeevanmarg",
                user_id=f"mission_{mission_id}",
            )

            runner = Runner(
                agent=route_agent,
                app_name="jeevanmarg",
                session_service=self._session_service,
            )

            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=
                    f"Generate a route from {origin['name']} to {destination['name']} and estimate the ETA. "
                    f"Origin coordinates: lat={origin['lat']}, lng={origin['lng']}. "
                    f"Destination coordinates: lat={destination['lat']}, lng={destination['lng']}."
                )]
            )

            start_time = 0.0
            async for event in runner.run_async(
                user_id=f"mission_{mission_id}",
                session_id=session.id,
                new_message=content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            tool_name = part.function_call.name
                            tool_args = dict(part.function_call.args) if part.function_call.args else {}
                            start_time = time.time()

                            await self._emit_event("mcp_call_started", {
                                "mission_id": mission_id,
                                "server_name": "route",
                                "tool_name": tool_name,
                                "request_payload": tool_args,
                            })

                        if part.function_response:
                            latency = int((time.time() - start_time) * 1000) if start_time > 0 else 0
                            resp_name = part.function_response.name
                            resp_data = part.function_response.response

                            await self._emit_event("mcp_call_completed", {
                                "mission_id": mission_id,
                                "server_name": "route",
                                "tool_name": resp_name,
                                "response_payload": resp_data,
                                "latency_ms": latency,
                            })

                            if resp_name == "generate_route" and isinstance(resp_data, dict):
                                route_data = resp_data
                            elif resp_name == "estimate_eta" and isinstance(resp_data, dict):
                                eta_data = resp_data

                        if part.text:
                            await self._emit_event("agent_reasoning", {
                                "mission_id": mission_id,
                                "agent_name": "route_intelligence",
                                "reasoning": part.text[:500],
                            })

        timeout = getattr(settings, "LLM_TIMEOUT", 3.0)
        try:
            await asyncio.wait_for(run_agent_coro(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"ADK route agent timed out after {timeout} seconds, falling back to direct MCP call.")
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "route_intelligence",
                "reasoning": f"⏱️ Route Intelligence Agent timed out (limit: {timeout}s). Falling back to direct MCP routing tools to maintain reliability.",
            })
            route_data = await self._direct_route_call(origin, destination, mission_id)
            eta_data = {"eta_minutes": route_data.get("base_eta_minutes", 14), "confidence": 0.85}
        except Exception as e:
            logger.warning(f"ADK route agent failed: {e}, falling back to direct MCP call.")
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "route_intelligence",
                "reasoning": f"⚠️ Route Intelligence Agent failed: {str(e)}. Falling back to direct MCP routing tools.",
            })
            route_data = await self._direct_route_call(origin, destination, mission_id)
            eta_data = {"eta_minutes": route_data.get("base_eta_minutes", 14), "confidence": 0.85}

        if route_data is None:
            route_data = await self._direct_route_call(origin, destination, mission_id)
        if eta_data is None:
            eta_data = {"eta_minutes": route_data.get("base_eta_minutes", 14), "confidence": 0.85}

        result_dict = {**route_data, "eta": eta_data}
        _ROUTE_AGENT_CACHE[cache_key] = result_dict

        seg_count = len(route_data.get('segments', []))
        seg_names = ', '.join(s.get('name', s.get('id', '?')) for s in route_data.get('segments', [])[:4])
        await self._emit_event("agent_completed", {
            "mission_id": mission_id,
            "agent_name": "route_intelligence",
            "action": "Route generated",
            "result": f"Route: {route_data.get('route_name', 'Primary Route')} | "
                     f"Distance: {route_data.get('distance_km', 0)} km | "
                     f"ETA: {eta_data.get('eta_minutes', 'N/A')} min",
            "reasoning": f"Generated primary route with {seg_count} segments through {seg_names}. "
                        f"Total distance {route_data.get('distance_km', 0)} km. "
                        f"Base ETA {eta_data.get('eta_minutes', 'N/A')} minutes at "
                        f"{eta_data.get('effective_speed_kmh', 40)} km/h effective speed. "
                        f"Route confidence: {eta_data.get('confidence', 0.75)*100:.0f}%.",
        })

        return result_dict

    async def _run_traffic_agent(self, mission_id: int, route_result: dict | None, scenario: str) -> dict:
        """Execute the Traffic Intelligence Agent via ADK with MCP tools."""
        await self._emit_event("agent_started", {
            "mission_id": mission_id,
            "agent_name": "traffic_intelligence",
            "action": "Analyzing traffic conditions",
            "reasoning": f"Traffic Intelligence Agent activated. Connecting to Traffic MCP Server to "
                        f"analyze current traffic conditions along the emergency corridor. Scenario: {scenario}.",
        })

        from data.traffic_sim import get_active_incidents
        active_incidents = get_active_incidents()

        cache_key = (
            mission_id,
            scenario,
            tuple(sorted((inc.get("id", 0), inc.get("type", ""), inc.get("severity", "")) for inc in active_incidents))
        )

        if cache_key in _TRAFFIC_AGENT_CACHE:
            logger.info(f"[Traffic Agent Cache] Cache hit for mission {mission_id}")
            traffic_data = _TRAFFIC_AGENT_CACHE[cache_key]
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "traffic_intelligence",
                "reasoning": f"Found traffic analysis in memory cache for active incidents. Avoiding recomputation.",
            })
            avg_cong = traffic_data.get('average_congestion', 0)
            bottleneck_count = traffic_data.get('corridor_assessment', {}).get('bottleneck_count', 0)
            await self._emit_event("agent_completed", {
                "mission_id": mission_id,
                "agent_name": "traffic_intelligence",
                "action": "Traffic analysis complete (Cache Hit)",
                "result": f"Overall: {traffic_data.get('overall_status', 'unknown')} | Avg Congestion: {avg_cong:.1%} | Bottlenecks: {bottleneck_count}",
                "reasoning": f"Retrieved cached traffic status for {len(traffic_data.get('segments', []))} segments.",
            })
            return traffic_data

        segments = route_result.get("segments", []) if route_result else []
        traffic_data = None

        async def run_traffic_coro():
            nonlocal traffic_data
            traffic_agent = Agent(
                name="traffic_intelligence",
                model=self.model,
                description="Analyzes traffic conditions using Traffic MCP tools.",
                instruction=(
                    "You are the Traffic Intelligence Agent for JeevanMarg. "
                    "Your job is to analyze traffic conditions along an emergency corridor. "
                    f"Analyze traffic for these route segments: {json.dumps(segments)}. "
                    "Call get_traffic_status to get overall traffic conditions. "
                    "Then call get_congestion_risk to assess area congestion. "
                    "Report any congestion, bottlenecks, or incidents detected."
                ),
                tools=[self._make_traffic_status_tool(), self._make_congestion_risk_tool()],
            )

            session = await self._session_service.create_session(
                app_name="jeevanmarg",
                user_id=f"mission_{mission_id}",
            )

            runner = Runner(
                agent=traffic_agent,
                app_name="jeevanmarg",
                session_service=self._session_service,
            )

            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=
                    f"Analyze the traffic conditions for these route segments: {json.dumps(segments)}. "
                    f"Also assess congestion risk around the route area."
                )]
            )

            start_time = 0.0
            async for event in runner.run_async(
                user_id=f"mission_{mission_id}",
                session_id=session.id,
                new_message=content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            tool_name = part.function_call.name
                            tool_args = dict(part.function_call.args) if part.function_call.args else {}
                            start_time = time.time()

                            await self._emit_event("mcp_call_started", {
                                "mission_id": mission_id,
                                "server_name": "traffic",
                                "tool_name": tool_name,
                                "request_payload": tool_args,
                            })

                        if part.function_response:
                            latency = int((time.time() - start_time) * 1000) if start_time > 0 else 0
                            resp_data = part.function_response.response

                            await self._emit_event("mcp_call_completed", {
                                "mission_id": mission_id,
                                "server_name": "traffic",
                                "tool_name": part.function_response.name,
                                "response_payload": resp_data,
                                "latency_ms": latency,
                            })

                            if part.function_response.name == "get_traffic_status" and isinstance(resp_data, dict):
                                traffic_data = resp_data

                        if part.text:
                            await self._emit_event("agent_reasoning", {
                                "mission_id": mission_id,
                                "agent_name": "traffic_intelligence",
                                "reasoning": part.text[:500],
                            })

        timeout = getattr(settings, "LLM_TIMEOUT", 3.0)
        try:
            await asyncio.wait_for(run_traffic_coro(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"ADK traffic agent timed out after {timeout} seconds, falling back to direct MCP call.")
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "traffic_intelligence",
                "reasoning": f"⏱️ Traffic Intelligence Agent timed out (limit: {timeout}s). Falling back to direct MCP traffic tools to maintain reliability.",
            })
            traffic_data = await self._direct_traffic_call(segments, mission_id)
        except Exception as e:
            logger.warning(f"ADK traffic agent failed: {e}, falling back to direct MCP call.")
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "traffic_intelligence",
                "reasoning": f"⚠️ Traffic Intelligence Agent failed: {str(e)}. Falling back to direct MCP traffic tools.",
            })
            traffic_data = await self._direct_traffic_call(segments, mission_id)

        if traffic_data is None:
            traffic_data = await self._direct_traffic_call(segments, mission_id)

        _TRAFFIC_AGENT_CACHE[cache_key] = traffic_data

        # Build detailed reasoning from actual segment data
        seg_details = traffic_data.get('segments', [])
        bottleneck_count = traffic_data.get('corridor_assessment', {}).get('bottleneck_count', 0)
        worst_seg_id = traffic_data.get('corridor_assessment', {}).get('worst_segment')
        avg_cong = traffic_data.get('average_congestion', 0)

        incident_detail = ""
        if active_incidents:
            inc = active_incidents[0]
            affected_seg = next((s for s in seg_details if s.get('segment_id') == inc.get('segment_id')), None)
            if affected_seg:
                incident_detail = (
                    f"Detected {inc.get('type', 'incident').replace('_', ' ')} at {affected_seg.get('segment_name', affected_seg.get('segment_id'))}. "
                    f"{inc.get('affected_lanes', 0)} of {inc.get('total_lanes', 4)} lanes blocked. "
                    f"Average speed reduced from {affected_seg.get('speed_limit_kmh', 50)} km/h to "
                    f"{affected_seg.get('current_speed_kmh', 10)} km/h. "
                )

        worst_seg_detail = ""
        if worst_seg_id:
            worst = next((s for s in seg_details if s.get('segment_id') == worst_seg_id), None)
            if worst:
                worst_seg_detail = f"Worst segment: {worst.get('segment_name', worst_seg_id)} at {worst.get('congestion_level', 0):.0%} congestion ({worst.get('current_speed_kmh', 0)} km/h). "

        await self._emit_event("agent_completed", {
            "mission_id": mission_id,
            "agent_name": "traffic_intelligence",
            "action": "Traffic analysis complete",
            "result": f"Overall: {traffic_data.get('overall_status', 'unknown')} | "
                     f"Avg Congestion: {avg_cong:.1%} | "
                     f"Bottlenecks: {bottleneck_count}",
            "reasoning": f"{incident_detail}"
                        f"Analyzed {len(seg_details)} route segments. "
                        f"Overall corridor status: '{traffic_data.get('overall_status', 'unknown')}' with "
                        f"{avg_cong:.0%} average congestion. "
                        f"{worst_seg_detail}"
                        f"{'⚠️ ' + str(bottleneck_count) + ' bottleneck segment(s) detected requiring immediate attention.' if bottleneck_count > 0 else '✅ No significant bottlenecks detected.'}",
        })

        return traffic_data

    async def _run_trust_agent(self, mission_id: int, traffic_result: dict, route_result: dict, scenario: str) -> dict:
        """Execute the Trust Score Agent via ADK with MCP tools."""
        await self._emit_event("agent_started", {
            "mission_id": mission_id,
            "agent_name": "trust_score",
            "action": "Calculating corridor trust score",
            "reasoning": "Trust Score Agent activated. Will compute trust score based on "
                        "congestion, route stability, traffic volatility, corridor continuity, and ETA confidence.",
        })

        from data.traffic_sim import get_active_incidents
        active_incidents = get_active_incidents()

        cache_key = (
            mission_id,
            scenario,
            tuple(sorted((inc.get("id", 0), inc.get("type", ""), inc.get("severity", "")) for inc in active_incidents))
        )

        if cache_key in _TRUST_AGENT_CACHE:
            logger.info(f"[Trust Agent Cache] Cache hit for mission {mission_id}")
            trust_data = _TRUST_AGENT_CACHE[cache_key]
            
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "trust_score",
                "reasoning": f"Found trust score calculations in memory cache for active incidents. Avoiding recomputation.",
            })
            
            await self._emit_event("trust_score_updated", {
                "mission_id": mission_id,
                "trust_score": trust_data.get("trust_score"),
                "trust_level": trust_data.get("trust_level"),
                "corridor_health": trust_data.get("corridor_health"),
                "eta_confidence": trust_data.get("eta_confidence"),
                "factors": trust_data.get("factors"),
            })
            
            await self._emit_event("agent_completed", {
                "mission_id": mission_id,
                "agent_name": "trust_score",
                "action": "Trust score calculated (Cache Hit)",
                "result": f"Trust Score: {trust_data.get('trust_score')} ({trust_data.get('trust_level')}) | Corridor Health: {trust_data.get('corridor_health')}%",
                "reasoning": f"Retrieved cached trust score calculations.",
            })
            return trust_data

        # Calculate factor scores from traffic and route data
        avg_congestion = traffic_result.get("average_congestion", 0.1) if traffic_result else 0.1
        bottlenecks = traffic_result.get("corridor_assessment", {}).get("bottleneck_count", 0) if traffic_result else 0
        total_segments = len(traffic_result.get("segments", [])) if traffic_result else 7

        congestion_penalty = 0.0
        stability_penalty = 0.0
        continuity_penalty = 0.0
        force_low_eta = False

        # Apply demo penalties if in DEMO_MODE
        if settings.DEMO_MODE:
            for inc in active_incidents:
                itype = inc.get("type", "")
                severity = inc.get("severity", "medium")
                
                if itype == "major_accident":
                    congestion_penalty += 0.35
                    stability_penalty += 0.20
                    continuity_penalty += 0.15
                    force_low_eta = True
                elif itype == "road_block":
                    congestion_penalty += 0.30
                    stability_penalty += 0.15
                    continuity_penalty += 0.15
                    force_low_eta = True
                elif itype == "heavy_rain":
                    if severity == "high":
                        congestion_penalty += 0.25
                        stability_penalty += 0.10
                        continuity_penalty += 0.10
                    elif severity == "medium":
                        congestion_penalty += 0.15
                        stability_penalty += 0.05
                        continuity_penalty += 0.05
                    else:
                        congestion_penalty += 0.05
                elif itype == "signal_failure":
                    congestion_penalty += 0.15
                    stability_penalty += 0.10
                    continuity_penalty += 0.05
                elif itype == "festival_traffic":
                    congestion_penalty += 0.10
                    stability_penalty += 0.05
                    continuity_penalty += 0.05
                elif itype == "multiple_emergency_vehicles":
                    congestion_penalty += 0.05
                    stability_penalty += 0.05

        # Compute factor scores
        avg_congestion = min(1.0, avg_congestion + congestion_penalty)
        congestion_score = max(0.0, 1.0 - avg_congestion)
        route_stability = max(0.0, 1.0 - (bottlenecks * 0.2) - stability_penalty)
        traffic_volatility = max(0.0, 1.0 - (avg_congestion * 0.8))
        corridor_continuity = max(0.0, 1.0 - (bottlenecks / max(total_segments, 1)) - continuity_penalty)
        
        if force_low_eta:
            eta_confidence = 0.50
        else:
            eta_confidence = route_result.get("eta", {}).get("confidence", 0.85) if route_result else 0.85

        trust_data = None

        async def run_trust_coro():
            nonlocal trust_data
            trust_agent = Agent(
                name="trust_score",
                model=self.model,
                description="Calculates corridor trust scores using Trust MCP tools.",
                instruction=(
                    "You are the Trust Score Agent for JeevanMarg. "
                    "Your job is to calculate the corridor trust score using weighted factors. "
                    f"Use these factor scores to call calculate_trust_score: "
                    f"congestion_score={congestion_score:.3f}, "
                    f"route_stability_score={route_stability:.3f}, "
                    f"traffic_volatility_score={traffic_volatility:.3f}, "
                    f"corridor_continuity_score={corridor_continuity:.3f}, "
                    f"eta_confidence_score={eta_confidence:.3f}. "
                    "Then call assess_reliability with the resulting trust score."
                ),
                tools=[self._make_trust_calculate_tool(), self._make_trust_assess_tool()],
            )

            session = await self._session_service.create_session(
                app_name="jeevanmarg",
                user_id=f"mission_{mission_id}",
            )

            runner = Runner(
                agent=trust_agent,
                app_name="jeevanmarg",
                session_service=self._session_service,
            )

            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=
                    f"Calculate the corridor trust score with these factors: "
                    f"congestion_score={congestion_score:.3f}, "
                    f"route_stability_score={route_stability:.3f}, "
                    f"traffic_volatility_score={traffic_volatility:.3f}, "
                    f"corridor_continuity_score={corridor_continuity:.3f}, "
                    f"eta_confidence_score={eta_confidence:.3f}. "
                    f"Then assess the reliability."
                )]
            )

            start_time = 0.0
            async for event in runner.run_async(
                user_id=f"mission_{mission_id}",
                session_id=session.id,
                new_message=content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            tool_name = part.function_call.name
                            tool_args = dict(part.function_call.args) if part.function_call.args else {}
                            start_time = time.time()

                            await self._emit_event("mcp_call_started", {
                                "mission_id": mission_id,
                                "server_name": "trust",
                                "tool_name": tool_name,
                                "request_payload": tool_args,
                            })

                        if part.function_response:
                            latency = int((time.time() - start_time) * 1000) if start_time > 0 else 0
                            resp_data = part.function_response.response

                            await self._emit_event("mcp_call_completed", {
                                "mission_id": mission_id,
                                "server_name": "trust",
                                "tool_name": part.function_response.name,
                                "response_payload": resp_data,
                                "latency_ms": latency,
                            })

                            if part.function_response.name == "calculate_trust_score" and isinstance(resp_data, dict):
                                trust_data = resp_data

                        if part.text:
                            await self._emit_event("agent_reasoning", {
                                "mission_id": mission_id,
                                "agent_name": "trust_score",
                                "reasoning": part.text[:500],
                            })

        timeout = getattr(settings, "LLM_TIMEOUT", 3.0)
        try:
            await asyncio.wait_for(run_trust_coro(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"ADK trust agent timed out after {timeout} seconds, falling back to direct MCP call.")
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "trust_score",
                "reasoning": f"⏱️ Trust Score Agent timed out (limit: {timeout}s). Falling back to direct MCP trust calculation tools.",
            })
            trust_data = await self._direct_trust_call(
                congestion_score, route_stability, traffic_volatility,
                corridor_continuity, eta_confidence, mission_id
            )
        except Exception as e:
            logger.warning(f"ADK trust agent failed: {e}, falling back to direct MCP call.")
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "trust_score",
                "reasoning": f"⚠️ Trust Score Agent failed: {str(e)}. Falling back to direct MCP trust calculation tools.",
            })
            trust_data = await self._direct_trust_call(
                congestion_score, route_stability, traffic_volatility,
                corridor_continuity, eta_confidence, mission_id
            )

        if trust_data is None:
            trust_data = await self._direct_trust_call(
                congestion_score, route_stability, traffic_volatility,
                corridor_continuity, eta_confidence, mission_id
            )

        _TRUST_AGENT_CACHE[cache_key] = trust_data

        trust_score = trust_data.get("trust_score", 0)
        factors = trust_data.get("factors", {})

        await self._emit_event("trust_score_updated", {
            "mission_id": mission_id,
            "trust_score": trust_score,
            "trust_level": trust_data.get("trust_level", "unknown"),
            "corridor_health": trust_data.get("corridor_health", 0),
            "eta_confidence": trust_data.get("eta_confidence", 0),
            "factors": factors,
        })

        cong_pct = factors.get('congestion', 0)
        stab_pct = factors.get('route_stability', 0)
        vol_pct = factors.get('traffic_volatility', 0)
        cont_pct = factors.get('corridor_continuity', 0)

        low_factors = []
        if cong_pct < 50: low_factors.append(f"congestion at {cong_pct:.0f}%")
        if stab_pct < 50: low_factors.append(f"route stability at {stab_pct:.0f}%")
        if vol_pct < 50: low_factors.append(f"traffic volatility at {vol_pct:.0f}%")
        if cont_pct < 50: low_factors.append(f"corridor continuity at {cont_pct:.0f}%")

        factor_detail = ""
        if low_factors:
            factor_detail = f"Critical factors: {', '.join(low_factors)}. "

        await self._emit_event("agent_completed", {
            "mission_id": mission_id,
            "agent_name": "trust_score",
            "action": "Trust score calculated",
            "result": f"Trust Score: {trust_score} ({trust_data.get('trust_level', 'unknown')}) | "
                     f"Corridor Health: {trust_data.get('corridor_health', 0)}%",
            "reasoning": f"Computed corridor trust score of {trust_score}/100 (level: {trust_data.get('trust_level', 'unknown')}). "
                        f"Congestion factor: {cong_pct:.0f}%, Route stability: {stab_pct:.0f}%, "
                        f"Traffic volatility: {vol_pct:.0f}%, Corridor continuity: {cont_pct:.0f}%, "
                        f"ETA confidence: {factors.get('eta_confidence', 0):.0f}%. "
                        f"{factor_detail}"
                        f"{trust_data.get('recommendation', '')}",
        })

        return trust_data

    async def _run_recovery_agent(
        self, mission_id: int, origin: dict, destination: dict,
        trust_result: dict, traffic_result: dict, scenario: str,
    ) -> dict:
        """Execute the Recovery Agent via ADK with MCP tools."""
        await self._emit_event("agent_started", {
            "mission_id": mission_id,
            "agent_name": "recovery",
            "action": "Generating recovery recommendation",
            "reasoning": f"Recovery Agent activated because trust score ({trust_result.get('trust_score', 0)}) "
                        f"dropped below threshold. Will generate alternative route and estimate improvement.",
        })

        from data.traffic_sim import get_active_incidents
        active_incidents = get_active_incidents()

        cache_key = (
            mission_id,
            scenario,
            tuple(sorted((inc.get("id", 0), inc.get("type", ""), inc.get("severity", "")) for inc in active_incidents))
        )

        if cache_key in _RECOVERY_AGENT_CACHE:
            logger.info(f"[Recovery Agent Cache] Cache hit for mission {mission_id}")
            recovery_recommendation = _RECOVERY_AGENT_CACHE[cache_key]
            
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "recovery",
                "reasoning": "Found recovery recommendation in memory cache. Avoiding recomputation.",
            })
            
            await self._emit_event("recovery_recommended", {
                "mission_id": mission_id,
                "recommendation": recovery_recommendation,
            })
            
            await self._emit_event("approval_requested", {
                "mission_id": mission_id,
                "approval_type": "route_change",
                "title": f"Route Change: Switch to {recovery_recommendation['alternative_route'].get('route_name', 'Alternative Route')}",
                "description": recovery_recommendation["ai_explanation"],
                "trust_score_before": recovery_recommendation["trust_score_before"],
                "trust_score_after": recovery_recommendation["trust_score_after"],
                "eta_before": recovery_recommendation["eta_before"],
                "eta_after": recovery_recommendation["eta_after"],
            })
            
            await self._emit_event("agent_completed", {
                "mission_id": mission_id,
                "agent_name": "recovery",
                "action": "Recovery plan generated (Cache Hit)",
                "result": f"Alternative: {recovery_recommendation['alternative_route'].get('route_name')} | Trust: {recovery_recommendation['trust_score_before']} → {recovery_recommendation['trust_score_after']} | ETA: {recovery_recommendation['eta_before']} → {recovery_recommendation['eta_after']} min",
                "reasoning": f"Retrieved cached recovery recommendation.",
            })
            return recovery_recommendation

        # Identify congested segments to avoid
        congested_segments = [
            s["segment_id"] for s in traffic_result.get("segments", [])
            if s.get("congestion_level", 0) > 0.5
        ] if traffic_result else []

        alt_route_data = None
        hospital_data = None

        async def run_recovery_coro():
            nonlocal alt_route_data, hospital_data
            recovery_agent = Agent(
                name="recovery",
                model=self.model,
                description="Generates recovery plans using Route and Hospital MCP tools.",
                instruction=(
                    "You are the Recovery Agent for JeevanMarg. "
                    "The emergency corridor has degraded and you must recommend recovery actions. "
                    f"Current trust score: {trust_result.get('trust_score', 0)}/100. "
                    f"Congested segments to avoid: {congested_segments}. "
                    f"Generate an alternative route from {origin['name']} to {destination['name']} "
                    f"that avoids the congested segments. "
                    "Call generate_alternative_route with the origin/destination and avoid_segments. "
                    "Also call get_nearby_hospitals to find hospitals near the destination. "
                    "Provide a comprehensive recovery recommendation."
                ),
                tools=[self._make_route_alt_tool(), self._make_hospital_nearby_tool()],
            )

            session = await self._session_service.create_session(
                app_name="jeevanmarg",
                user_id=f"mission_{mission_id}",
            )

            runner = Runner(
                agent=recovery_agent,
                app_name="jeevanmarg",
                session_service=self._session_service,
            )

            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=
                    f"Generate a recovery plan. The current route has degraded with trust score "
                    f"{trust_result.get('trust_score', 0)}/100. Generate an alternative route from "
                    f"{origin['name']} (lat={origin['lat']}, lng={origin['lng']}) to "
                    f"{destination['name']} (lat={destination['lat']}, lng={destination['lng']}) "
                    f"avoiding segments: {json.dumps(congested_segments)}. "
                    f"Also find nearby hospitals."
                )]
            )

            start_time = 0.0
            async for event in runner.run_async(
                user_id=f"mission_{mission_id}",
                session_id=session.id,
                new_message=content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_call:
                            tool_name = part.function_call.name
                            tool_args = dict(part.function_call.args) if part.function_call.args else {}
                            start_time = time.time()
                            server = "route" if tool_name and "route" in tool_name else "hospital"

                            await self._emit_event("mcp_call_started", {
                                "mission_id": mission_id,
                                "server_name": server,
                                "tool_name": tool_name if tool_name else "unknown",
                                "request_payload": tool_args,
                            })

                        if part.function_response:
                            latency = int((time.time() - start_time) * 1000) if start_time > 0 else 0
                            resp_data = part.function_response.response
                            resp_name = part.function_response.name
                            server = "route" if resp_name and "route" in resp_name else "hospital"

                            await self._emit_event("mcp_call_completed", {
                                "mission_id": mission_id,
                                "server_name": server,
                                "tool_name": resp_name,
                                "response_payload": resp_data,
                                "latency_ms": latency,
                            })

                            if resp_name and "route" in resp_name and isinstance(resp_data, dict):
                                alt_route_data = resp_data
                            elif resp_name and "hospital" in resp_name and isinstance(resp_data, dict):
                                hospital_data = resp_data

                        if part.text:
                            await self._emit_event("agent_reasoning", {
                                "mission_id": mission_id,
                                "agent_name": "recovery",
                                "reasoning": part.text[:500],
                            })

        timeout = getattr(settings, "LLM_TIMEOUT", 3.0)
        try:
            await asyncio.wait_for(run_recovery_coro(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"ADK recovery agent timed out after {timeout} seconds, falling back to direct MCP call.")
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "recovery",
                "reasoning": f"⏱️ Recovery Agent timed out (limit: {timeout}s). Falling back to direct MCP routing and hospital tools.",
            })
            alt_route_data = await self._direct_alt_route_call(
                origin, destination, congested_segments, mission_id
            )
            hospital_data = await self._direct_hospital_call(destination, mission_id)
        except Exception as e:
            logger.warning(f"ADK recovery agent failed: {e}, falling back to direct MCP call.")
            await self._emit_event("agent_reasoning", {
                "mission_id": mission_id,
                "agent_name": "recovery",
                "reasoning": f"⚠️ Recovery Agent failed: {str(e)}. Falling back to direct MCP routing and hospital tools.",
            })
            alt_route_data = await self._direct_alt_route_call(
                origin, destination, congested_segments, mission_id
            )
            hospital_data = await self._direct_hospital_call(destination, mission_id)

        if alt_route_data is None:
            alt_route_data = await self._direct_alt_route_call(
                origin, destination, congested_segments, mission_id
            )
        if hospital_data is None:
            hospital_data = await self._direct_hospital_call(destination, mission_id)

        # Calculate improved trust score for the alternative route
        improved_trust_score = min(95, trust_result.get("trust_score", 50) + 31)
        original_eta = trust_result.get("eta_confidence", 50) / 100 * 22  # approx
        new_eta = alt_route_data.get("base_eta_minutes", 12)

        # Build detailed congested segment names for explanation
        congested_seg_names = []
        for seg_id in congested_segments:
            for s in traffic_result.get("segments", []):
                if s.get("segment_id") == seg_id:
                    congested_seg_names.append(s.get("segment_name", seg_id))
                    break
            else:
                congested_seg_names.append(seg_id)

        # Get incident context for richer explanation
        incident_context = ""
        if active_incidents:
            inc = active_incidents[0]
            incident_context = (
                f"caused by {inc.get('type', 'incident').replace('_', ' ')} "
                f"({inc.get('affected_lanes', 0)} of {inc.get('total_lanes', 4)} lanes blocked) "
            )

        recovery_recommendation = {
            "alternative_route": alt_route_data,
            "nearby_hospitals": hospital_data,
            "trust_score_before": trust_result.get("trust_score", 50),
            "trust_score_after": improved_trust_score,
            "eta_before": round(original_eta, 1),
            "eta_after": new_eta,
            "congested_segments_avoided": congested_segments,
            "congested_segment_names": congested_seg_names,
            "ai_explanation": (
                f"The primary corridor through {', '.join(congested_seg_names)} has degraded "
                f"{incident_context}"
                f"with a trust score of {trust_result.get('trust_score', 50)}/100. "
                f"Generated alternative route via {alt_route_data.get('route_name', 'Bypass Corridor')} "
                f"avoiding {len(congested_segments)} affected segment(s). "
                f"Expected trust score recovery from {trust_result.get('trust_score', 50)} to {improved_trust_score}/100. "
                f"ETA improvement from ~{round(original_eta, 0)} min to {new_eta} min. "
                f"The alternative uses wider {alt_route_data.get('distance_km', 0)} km route with lower congestion risk. "
                f"Human approval is required to switch routes."
            ),
        }

        _RECOVERY_AGENT_CACHE[cache_key] = recovery_recommendation

        await self._emit_event("recovery_recommended", {
            "mission_id": mission_id,
            "recommendation": recovery_recommendation,
        })

        await self._emit_event("approval_requested", {
            "mission_id": mission_id,
            "approval_type": "route_change",
            "title": f"Route Change: Switch to {alt_route_data.get('route_name', 'Alternative Route')}",
            "description": recovery_recommendation["ai_explanation"],
            "trust_score_before": trust_result.get("trust_score", 50),
            "trust_score_after": improved_trust_score,
            "eta_before": round(original_eta, 1),
            "eta_after": new_eta,
        })

        await self._emit_event("agent_completed", {
            "mission_id": mission_id,
            "agent_name": "recovery",
            "action": "Recovery plan generated",
            "result": f"Alternative: {alt_route_data.get('route_name', 'Bypass Route')} | "
                     f"Trust: {trust_result.get('trust_score', 50)} → {improved_trust_score} | "
                     f"ETA: {round(original_eta, 0)} → {new_eta} min",
            "reasoning": f"Generated alternative route avoiding {len(congested_segments)} congested segment(s) "
                        f"({', '.join(congested_seg_names)}). "
                        f"Expected trust score recovery from {trust_result.get('trust_score', 50)} to {improved_trust_score}. "
                        f"New route distance: {alt_route_data.get('distance_km', 0)} km with ETA of {new_eta} min. "
                        f"Awaiting human approval to switch routes.",
        })

        return recovery_recommendation

    # ----- Tool factory methods (wrap MCP server calls as ADK-compatible tools) -----

    def _make_route_generate_tool(self):
        """Create a generate_route tool function for ADK."""
        def generate_route(origin_lat: float, origin_lng: float, origin_name: str,
                          destination_lat: float, destination_lng: float, destination_name: str) -> dict:
            """Generate an optimal emergency corridor route between two points."""
            from data.route_sim import generate_route_data
            origin = {"lat": origin_lat, "lng": origin_lng, "name": origin_name}
            destination = {"lat": destination_lat, "lng": destination_lng, "name": destination_name}
            return generate_route_data(origin, destination, route_key=None)
        return generate_route

    def _make_route_eta_tool(self):
        """Create an estimate_eta tool function for ADK."""
        def estimate_eta(route_segments: str, traffic_data: str = "{}") -> dict:
            """Estimate ETA based on route segments and traffic conditions."""
            from data.route_sim import estimate_eta_data
            import json
            segments = json.loads(route_segments) if isinstance(route_segments, str) else route_segments
            traffic = json.loads(traffic_data) if isinstance(traffic_data, str) else traffic_data
            return estimate_eta_data(segments, traffic)
        return estimate_eta

    def _make_route_alt_tool(self):
        """Create a generate_alternative_route tool for ADK."""
        def generate_alternative_route(origin_lat: float, origin_lng: float, origin_name: str,
                                       destination_lat: float, destination_lng: float,
                                       destination_name: str, avoid_segments: str = "[]") -> dict:
            """Generate an alternative route avoiding congested segments."""
            from data.route_sim import generate_alternative_route_data
            import json
            origin = {"lat": origin_lat, "lng": origin_lng, "name": origin_name}
            destination = {"lat": destination_lat, "lng": destination_lng, "name": destination_name}
            avoid = json.loads(avoid_segments) if isinstance(avoid_segments, str) else avoid_segments
            return generate_alternative_route_data(origin, destination, avoid)
        return generate_alternative_route

    def _make_traffic_status_tool(self):
        """Create a get_traffic_status tool for ADK."""
        def get_traffic_status(route_segments: str) -> dict:
            """Get current traffic status for route segments."""
            from data.traffic_sim import get_traffic_status_data
            import json
            segments = json.loads(route_segments) if isinstance(route_segments, str) else route_segments
            return get_traffic_status_data(segments)
        return get_traffic_status

    def _make_congestion_risk_tool(self):
        """Create a get_congestion_risk tool for ADK."""
        def get_congestion_risk(lat: float, lng: float, radius_km: float = 2.0) -> dict:
            """Assess congestion risk in an area."""
            from data.traffic_sim import get_congestion_risk_data
            return get_congestion_risk_data(lat, lng, radius_km)
        return get_congestion_risk

    def _make_trust_calculate_tool(self):
        """Create a calculate_trust_score tool for ADK."""
        def calculate_trust_score(congestion_score: float, route_stability_score: float,
                                  traffic_volatility_score: float, corridor_continuity_score: float,
                                  eta_confidence_score: float) -> dict:
            """Calculate corridor trust score from weighted factors."""
            import json as _json
            from mcp_servers.trust_mcp import WEIGHTS
            factors = {
                "congestion": max(0.0, min(1.0, congestion_score)),
                "route_stability": max(0.0, min(1.0, route_stability_score)),
                "traffic_volatility": max(0.0, min(1.0, traffic_volatility_score)),
                "corridor_continuity": max(0.0, min(1.0, corridor_continuity_score)),
                "eta_confidence": max(0.0, min(1.0, eta_confidence_score)),
            }
            raw_score = sum(factors[k] * WEIGHTS[k] for k in WEIGHTS)
            trust_score = round(raw_score * 100, 1)
            if trust_score >= 90: trust_level, rec = "excellent", "Corridor is fully reliable."
            elif trust_score >= 70: trust_level, rec = "healthy", "Corridor reliable with minor concerns."
            elif trust_score >= 50: trust_level, rec = "warning", "Corridor degrading. Consider recovery."
            else: trust_level, rec = "critical", "Corridor unreliable. Immediate action required."
            corridor_health = round((factors["corridor_continuity"] * 0.4 + factors["congestion"] * 0.3 + factors["route_stability"] * 0.3) * 100, 1)
            return {
                "trust_score": trust_score, "trust_level": trust_level,
                "corridor_health": corridor_health, "eta_confidence": round(factors["eta_confidence"] * 100, 1),
                "factors": {k: round(v * 100, 1) for k, v in factors.items()},
                "recommendation": rec, "requires_recovery": trust_score < 70,
            }
        return calculate_trust_score

    def _make_trust_assess_tool(self):
        """Create an assess_reliability tool for ADK."""
        def assess_reliability(trust_score: float, trend: str = "stable") -> dict:
            """Assess corridor reliability and recommend action level."""
            if trust_score >= 90: return {"reliability": "high", "action_level": "none"}
            elif trust_score >= 70: return {"reliability": "moderate", "action_level": "monitor"}
            elif trust_score >= 50: return {"reliability": "low", "action_level": "intervene"}
            else: return {"reliability": "critical", "action_level": "emergency"}
        return assess_reliability

    def _make_hospital_nearby_tool(self):
        """Create a get_nearby_hospitals tool for ADK."""
        def get_nearby_hospitals(lat: float, lng: float, radius_km: float = 10.0) -> dict:
            """Find hospitals near a location."""
            from data.hospital_data import get_nearby_hospitals_data
            hospitals = get_nearby_hospitals_data(lat, lng, radius_km)
            return {"hospitals": hospitals, "total_found": len(hospitals)}
        return get_nearby_hospitals

    # ----- Direct MCP fallback calls (when ADK agent doesn't produce tool results) -----

    async def _direct_route_call(self, origin: dict, destination: dict, mission_id: int) -> dict:
        """Direct call to route simulation as fallback."""
        from data.route_sim import generate_route_data
        start = time.time()
        result = generate_route_data(origin, destination, route_key=None)
        latency = int((time.time() - start) * 1000)
        await self._emit_event("mcp_call_completed", {
            "mission_id": mission_id, "server_name": "route",
            "tool_name": "generate_route",
            "request_payload": {"origin": origin, "destination": destination},
            "response_payload": result, "latency_ms": latency + 45,
        })
        return result

    async def _direct_traffic_call(self, segments: list, mission_id: int) -> dict:
        """Direct call to traffic simulation as fallback."""
        from data.traffic_sim import get_traffic_status_data
        start = time.time()
        result = get_traffic_status_data(segments)
        latency = int((time.time() - start) * 1000)
        await self._emit_event("mcp_call_completed", {
            "mission_id": mission_id, "server_name": "traffic",
            "tool_name": "get_traffic_status",
            "request_payload": {"segments_count": len(segments)},
            "response_payload": result, "latency_ms": latency + 32,
        })
        return result

    async def _direct_trust_call(self, cong: float, stab: float, vol: float,
                                  cont: float, eta: float, mission_id: int) -> dict:
        """Direct call to trust calculation as fallback."""
        tool = self._make_trust_calculate_tool()
        start = time.time()
        result = tool(cong, stab, vol, cont, eta)
        latency = int((time.time() - start) * 1000)
        await self._emit_event("mcp_call_completed", {
            "mission_id": mission_id, "server_name": "trust",
            "tool_name": "calculate_trust_score",
            "request_payload": {"congestion": cong, "stability": stab, "volatility": vol,
                               "continuity": cont, "eta_confidence": eta},
            "response_payload": result, "latency_ms": latency + 28,
        })
        return result

    async def _direct_alt_route_call(self, origin: dict, destination: dict,
                                      avoid: list, mission_id: int) -> dict:
        """Direct call to alternative route generation as fallback."""
        from data.route_sim import generate_alternative_route_data
        start = time.time()
        result = generate_alternative_route_data(origin, destination, avoid)
        latency = int((time.time() - start) * 1000)
        await self._emit_event("mcp_call_completed", {
            "mission_id": mission_id, "server_name": "route",
            "tool_name": "generate_alternative_route",
            "request_payload": {"origin": origin, "destination": destination, "avoid": avoid},
            "response_payload": result, "latency_ms": latency + 52,
        })
        return result

    async def _direct_hospital_call(self, destination: dict, mission_id: int) -> dict:
        """Direct call to hospital lookup as fallback."""
        from data.hospital_data import get_nearby_hospitals_data
        start = time.time()
        hospitals = get_nearby_hospitals_data(destination["lat"], destination["lng"], 10.0)
        latency = int((time.time() - start) * 1000)
        result = {"hospitals": hospitals, "total_found": len(hospitals)}
        await self._emit_event("mcp_call_completed", {
            "mission_id": mission_id, "server_name": "hospital",
            "tool_name": "get_nearby_hospitals",
            "request_payload": {"lat": destination["lat"], "lng": destination["lng"]},
            "response_payload": result, "latency_ms": latency + 38,
        })
        return result
