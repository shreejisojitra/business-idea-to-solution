"""
Module 14: Feedback API.
POST   /projects/{project_id}/feedback          — submit feedback
GET    /projects/{project_id}/feedback          — list project feedback (owner)
GET    /projects/{project_id}/feedback/summary  — aggregated counts (owner)
DELETE /projects/{project_id}/feedback/{id}     — delete own feedback
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.models import MessageFeedback, Project, User, Workspace
from app.db.session import get_db

router = APIRouter()

VALID_RATINGS = {"positive", "negative"}


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


class FeedbackCreate(BaseModel):
    rating: str                        # "positive" | "negative"
    comment: Optional[str] = None
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None


@router.post("/projects/{project_id}/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    project_id: str,
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit feedback on an AI response. Project ownership is verified."""
    _verify_project_owner(db, project_id, current_user.id)

    if payload.rating not in VALID_RATINGS:
        raise HTTPException(status_code=400, detail=f"rating must be one of: {VALID_RATINGS}")

    fb = MessageFeedback(
        user_id=current_user.id,
        project_id=project_id,
        message_id=payload.message_id,
        conversation_id=payload.conversation_id,
        rating=payload.rating,
        comment=payload.comment[:500] if payload.comment else None,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    return {
        "id": fb.id,
        "project_id": fb.project_id,
        "rating": fb.rating,
        "comment": fb.comment,
        "message_id": fb.message_id,
        "created_at": fb.created_at.isoformat(),
    }


@router.get("/projects/{project_id}/feedback")
def list_feedback(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all feedback for a project. Owner access only."""
    _verify_project_owner(db, project_id, current_user.id)

    records = (
        db.query(MessageFeedback)
        .filter(MessageFeedback.project_id == project_id)
        .order_by(MessageFeedback.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "message_id": r.message_id,
            "conversation_id": r.conversation_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@router.get("/projects/{project_id}/feedback/summary")
def feedback_summary(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregated feedback counts for analytics. Owner access only."""
    _verify_project_owner(db, project_id, current_user.id)

    total = db.query(func.count(MessageFeedback.id)).filter(
        MessageFeedback.project_id == project_id
    ).scalar() or 0

    positive = db.query(func.count(MessageFeedback.id)).filter(
        MessageFeedback.project_id == project_id,
        MessageFeedback.rating == "positive",
    ).scalar() or 0

    negative = total - positive

    return {
        "project_id": project_id,
        "total": total,
        "positive": positive,
        "negative": negative,
        "feedback_rate": round(positive / total, 2) if total else None,
    }


@router.delete("/projects/{project_id}/feedback/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback(
    project_id: str,
    feedback_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete own feedback record."""
    fb = db.query(MessageFeedback).filter(
        MessageFeedback.id == feedback_id,
        MessageFeedback.project_id == project_id,
        MessageFeedback.user_id == current_user.id,
    ).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    db.delete(fb)
    db.commit()
