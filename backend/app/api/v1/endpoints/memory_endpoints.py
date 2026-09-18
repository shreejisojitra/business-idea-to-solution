from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.db.models import ProjectMemory, ProjectDecision, Project, Workspace, User

router = APIRouter()


class DecisionCreateSchema(BaseModel):
    decision: str
    category: str = "architecture"
    reason: Optional[str] = None
    alternatives: Optional[str] = None
    status: str = "accepted"


class DecisionUpdateSchema(BaseModel):
    decision: Optional[str] = None
    category: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None


def _verify_project_ownership(db: Session, project_id: str, user_id: str) -> Project:
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == user_id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or unauthorized.")
    return project


@router.get("/projects/{project_id}/memory")
def get_project_memory(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_project_ownership(db, project_id, current_user.id)
    memories = db.query(ProjectMemory).filter(ProjectMemory.project_id == project_id).all()
    return {
        "project_id": project_id,
        "memories": [
            {
                "id": m.id,
                "category": m.category,
                "key": m.key,
                "value": m.value,
                "updated_at": m.updated_at.isoformat()
            } for m in memories
        ]
    }


@router.get("/projects/{project_id}/decisions")
def get_project_decisions(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_project_ownership(db, project_id, current_user.id)
    decisions = db.query(ProjectDecision).filter(
        ProjectDecision.project_id == project_id
    ).order_by(ProjectDecision.created_at.desc()).all()
    return {
        "project_id": project_id,
        "decisions": [
            {
                "id": d.id,
                "category": d.category,
                "decision": d.decision,
                "reason": d.reason,
                "alternatives": d.alternatives,
                "status": d.status,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat()
            } for d in decisions
        ]
    }


@router.post("/projects/{project_id}/decisions")
def create_project_decision(
    project_id: str,
    payload: DecisionCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_project_ownership(db, project_id, current_user.id)

    if payload.status == "accepted":
        db.query(ProjectDecision).filter(
            ProjectDecision.project_id == project_id,
            ProjectDecision.category == payload.category,
            ProjectDecision.status == "accepted"
        ).update({"status": "superseded"})

    new_dec = ProjectDecision(
        project_id=project_id,
        category=payload.category,
        decision=payload.decision,
        reason=payload.reason,
        alternatives=payload.alternatives,
        status=payload.status
    )
    db.add(new_dec)
    db.commit()
    db.refresh(new_dec)

    return {
        "id": new_dec.id,
        "category": new_dec.category,
        "decision": new_dec.decision,
        "reason": new_dec.reason,
        "status": new_dec.status,
        "created_at": new_dec.created_at.isoformat()
    }


@router.patch("/projects/{project_id}/decisions/{decision_id}")
def update_project_decision(
    project_id: str,
    decision_id: str,
    payload: DecisionUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_project_ownership(db, project_id, current_user.id)
    dec = db.query(ProjectDecision).filter(
        ProjectDecision.id == decision_id,
        ProjectDecision.project_id == project_id
    ).first()
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")

    if payload.decision:
        dec.decision = payload.decision
    if payload.category:
        dec.category = payload.category
    if payload.reason:
        dec.reason = payload.reason
    if payload.status:
        dec.status = payload.status

    db.commit()
    db.refresh(dec)

    return {
        "id": dec.id,
        "category": dec.category,
        "decision": dec.decision,
        "status": dec.status,
        "updated_at": dec.updated_at.isoformat()
    }


@router.delete("/projects/{project_id}/decisions/{decision_id}")
def delete_project_decision(
    project_id: str,
    decision_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_project_ownership(db, project_id, current_user.id)
    dec = db.query(ProjectDecision).filter(
        ProjectDecision.id == decision_id,
        ProjectDecision.project_id == project_id
    ).first()
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")

    db.delete(dec)
    db.commit()
    return {"message": "Decision deleted successfully"}
