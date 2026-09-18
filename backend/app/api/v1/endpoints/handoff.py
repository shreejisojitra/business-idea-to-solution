"""
Module 15: Human Handoff API.
POST  /projects/{project_id}/handoffs          — create handoff request
GET   /projects/{project_id}/handoffs          — list project handoffs (owner)
GET   /projects/{project_id}/handoffs/{id}     — get single handoff (owner)
PATCH /projects/{project_id}/handoffs/{id}     — update status (owner)
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.models import HandoffRequest, Project, User, Workspace
from app.db.session import get_db

router = APIRouter()

VALID_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}
VALID_PRIORITIES = {"low", "normal", "high"}


def _verify_project_owner(db: Session, project_id: str, user_id: str) -> Project:
    project = (
        db.query(Project)
        .join(Workspace)
        .filter(Project.id == project_id, Workspace.owner_id == user_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized.")
    return project


def _fmt(h: HandoffRequest) -> dict:
    return {
        "id": h.id,
        "project_id": h.project_id,
        "user_id": h.user_id,
        "conversation_id": h.conversation_id,
        "subject": h.subject,
        "description": h.description,
        "status": h.status,
        "priority": h.priority,
        "created_at": h.created_at.isoformat(),
        "updated_at": h.updated_at.isoformat(),
        "resolved_at": h.resolved_at.isoformat() if h.resolved_at else None,
    }


class HandoffCreate(BaseModel):
    subject: str
    description: str
    priority: Optional[str] = "normal"
    conversation_id: Optional[str] = None


class HandoffStatusUpdate(BaseModel):
    status: str


@router.post("/projects/{project_id}/handoffs", status_code=status.HTTP_201_CREATED)
def create_handoff(
    project_id: str,
    payload: HandoffCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a human-assistance request for a project."""
    _verify_project_owner(db, project_id, current_user.id)

    if not payload.subject.strip():
        raise HTTPException(status_code=400, detail="subject cannot be empty.")
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="description cannot be empty.")

    priority = payload.priority if payload.priority in VALID_PRIORITIES else "normal"

    h = HandoffRequest(
        user_id=current_user.id,
        project_id=project_id,
        conversation_id=payload.conversation_id,
        subject=payload.subject.strip()[:255],
        description=payload.description.strip()[:2000],
        status="OPEN",
        priority=priority,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return _fmt(h)


@router.get("/projects/{project_id}/handoffs")
def list_handoffs(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all handoff requests for a project. Owner access only."""
    _verify_project_owner(db, project_id, current_user.id)

    records = (
        db.query(HandoffRequest)
        .filter(HandoffRequest.project_id == project_id)
        .order_by(HandoffRequest.created_at.desc())
        .all()
    )
    return [_fmt(h) for h in records]


@router.get("/projects/{project_id}/handoffs/{handoff_id}")
def get_handoff(
    project_id: str,
    handoff_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single handoff request. Owner access only."""
    _verify_project_owner(db, project_id, current_user.id)

    h = db.query(HandoffRequest).filter(
        HandoffRequest.id == handoff_id,
        HandoffRequest.project_id == project_id,
    ).first()
    if not h:
        raise HTTPException(status_code=404, detail="Handoff not found.")
    return _fmt(h)


@router.patch("/projects/{project_id}/handoffs/{handoff_id}")
def update_handoff_status(
    project_id: str,
    handoff_id: str,
    payload: HandoffStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update handoff status. Owner access only."""
    _verify_project_owner(db, project_id, current_user.id)

    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of: {VALID_STATUSES}")

    h = db.query(HandoffRequest).filter(
        HandoffRequest.id == handoff_id,
        HandoffRequest.project_id == project_id,
    ).first()
    if not h:
        raise HTTPException(status_code=404, detail="Handoff not found.")

    h.status = payload.status
    if payload.status in ("RESOLVED", "CLOSED") and not h.resolved_at:
        h.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(h)
    return _fmt(h)
