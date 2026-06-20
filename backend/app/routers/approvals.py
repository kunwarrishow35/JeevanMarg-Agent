"""Approval routes: list, approve, and reject recovery recommendations."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session_factory
from app.middleware.auth import get_current_user, require_operator
from app.models.user import User
from app.models.mission import Approval, ApprovalStatus, Mission, MissionStatus
from app.schemas.mission import ApprovalResponse, ApprovalAction
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


@router.get("", response_model=list[ApprovalResponse])
async def list_approvals(
    status_filter: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all approval requests, optionally filtered by status."""
    query = select(Approval).order_by(desc(Approval.created_at))
    if status_filter:
        query = query.where(Approval.status == ApprovalStatus(status_filter))
    result = await db.execute(query)
    approvals = result.scalars().all()
    return [ApprovalResponse.model_validate(a) for a in approvals]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific approval request."""
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return ApprovalResponse.model_validate(approval)


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_recommendation(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Approve a recovery recommendation (operator or admin only)."""
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Approval is already {approval.status.value}")

    # Approve
    approval.status = ApprovalStatus.APPROVED
    approval.reviewed_by = current_user.id
    approval.reviewed_at = datetime.now(timezone.utc)

    # Update mission trust score and status
    mission_result = await db.execute(
        select(Mission).where(Mission.id == approval.mission_id)
    )
    mission = mission_result.scalar_one_or_none()
    if mission:
        if approval.trust_score_after:
            mission.trust_score = approval.trust_score_after
            mission.trust_level = (
                "excellent" if approval.trust_score_after >= 90
                else "healthy" if approval.trust_score_after >= 70
                else "warning" if approval.trust_score_after >= 50
                else "critical"
            )
        if approval.eta_after:
            mission.eta_minutes = approval.eta_after
        mission.status = MissionStatus.COMPLETED
        mission.scenario = "recovered"

    await db.commit()
    await db.refresh(approval)

    # Broadcast approval event
    await ws_manager.broadcast_to_mission(approval.mission_id, {
        "type": "approval_resolved",
        "approval_id": approval.id,
        "mission_id": approval.mission_id,
        "action": "approved",
        "reviewed_by": current_user.username,
        "trust_score_after": approval.trust_score_after,
        "eta_after": approval.eta_after,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return ApprovalResponse.model_validate(approval)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_recommendation(
    approval_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Reject a recovery recommendation (operator or admin only)."""
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Approval is already {approval.status.value}")

    approval.status = ApprovalStatus.REJECTED
    approval.reviewed_by = current_user.id
    approval.reviewed_at = datetime.now(timezone.utc)

    # Update mission status
    mission_result = await db.execute(
        select(Mission).where(Mission.id == approval.mission_id)
    )
    mission = mission_result.scalar_one_or_none()
    if mission:
        mission.status = MissionStatus.DEGRADED

    await db.commit()
    await db.refresh(approval)

    await ws_manager.broadcast_to_mission(approval.mission_id, {
        "type": "approval_resolved",
        "approval_id": approval.id,
        "mission_id": approval.mission_id,
        "action": "rejected",
        "reviewed_by": current_user.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return ApprovalResponse.model_validate(approval)
