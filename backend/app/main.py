"""JeevanMarg — FastAPI Application Entry Point.

Self-Healing Emergency Corridor Agent platform.
Demonstrates Google ADK, MCP Servers, and Human-in-the-loop workflows.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import init_db, async_session_factory
from app.middleware.auth import hash_password
from app.models.user import User, UserRole
from app.routers import auth, missions, approvals, system
from app.services.ws_manager import ws_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("jeevanmarg")


async def seed_demo_users() -> None:
    """Seed default demo users on first startup."""
    demo_users = [
        {"username": "dispatcher", "password": "dispatch123", "full_name": "Demo Dispatcher", "role": UserRole.DISPATCHER},
        {"username": "operator", "password": "operate123", "full_name": "Demo Operator", "role": UserRole.OPERATOR},
        {"username": "admin", "password": "admin123", "full_name": "Demo Administrator", "role": UserRole.ADMINISTRATOR},
    ]

    async with async_session_factory() as db:
        for user_data in demo_users:
            result = await db.execute(
                select(User).where(User.username == user_data["username"])
            )
            if not result.scalar_one_or_none():
                user = User(
                    username=user_data["username"],
                    password_hash=hash_password(user_data["password"]),
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                )
                db.add(user)
                logger.info(f"Seeded demo user: {user_data['username']}")
        await db.commit()


async def init_mcp_status() -> None:
    """Mark MCP servers as connected on startup."""
    from app.routers.system import update_mcp_state
    for server in ["traffic", "route", "hospital", "trust"]:
        update_mcp_state(server, "connected")
    logger.info("MCP servers marked as connected")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Seed demo users
    await seed_demo_users()

    # Initialize MCP server status
    await init_mcp_status()

    logger.info(f"{settings.APP_NAME} is ready")
    yield
    logger.info(f"{settings.APP_NAME} shutting down")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Self-Healing Emergency Corridor Agent — AI Multi-Agent System",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(missions.router)
app.include_router(approvals.router)
app.include_router(system.router)


# WebSocket endpoint for real-time mission streaming
@app.websocket("/ws/missions/{mission_id}")
async def websocket_mission(websocket: WebSocket, mission_id: int):
    """WebSocket endpoint for streaming mission events in real-time."""
    await ws_manager.connect(websocket, mission_id)
    try:
        while True:
            # Keep connection alive, receive any client messages
            data = await websocket.receive_text()
            # Client can send ping/keepalive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, mission_id)


@app.websocket("/ws/global")
async def websocket_global(websocket: WebSocket):
    """WebSocket endpoint for streaming all mission events."""
    await ws_manager.connect(websocket, 0)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, 0)


# Root endpoint
@app.get("/")
async def root():
    """Health check and API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Self-Healing Emergency Corridor Agent",
        "docs": "/docs",
        "status": "online",
    }


@app.get("/api/v1/demo/config")
async def get_demo_config():
    """Get demo scenario configuration for the frontend."""
    return {
        "default_origin": {
            "name": "Connaught Place, Delhi",
            "lat": 28.6315,
            "lng": 77.2167,
        },
        "default_destination": {
            "name": "AIIMS Hospital, Delhi",
            "lat": 28.5672,
            "lng": 77.2100,
        },
        "scenarios": [
            {"id": "healthy", "name": "Healthy Corridor", "description": "Normal traffic, high trust score"},
            {"id": "degraded", "name": "Traffic Event", "description": "Accident causes corridor degradation"},
            {"id": "recovered", "name": "Recovery", "description": "Alternative route improves trust score"},
        ],
        "demo_credentials": {
            "dispatcher": {"username": "dispatcher", "password": "dispatch123"},
            "operator": {"username": "operator", "password": "operate123"},
            "admin": {"username": "admin", "password": "admin123"},
        },
    }
