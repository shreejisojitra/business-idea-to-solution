from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.models import User, Workspace
from app.db.session import get_db

router = APIRouter()


class WorkspaceCreateSchema(BaseModel):
    name: str


class WorkspaceResponseSchema(BaseModel):
    id: str
    name: str
    owner_id: str

    class Config:
        from_attributes = True


@router.post("/", response_model=WorkspaceResponseSchema)
def create_workspace(
    payload: WorkspaceCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ws = Workspace(name=payload.name, owner_id=current_user.id)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return WorkspaceResponseSchema.model_validate(ws)


@router.get("/", response_model=List[WorkspaceResponseSchema])
def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    workspaces = db.query(Workspace).filter(Workspace.owner_id == current_user.id).all()
    return [WorkspaceResponseSchema.model_validate(w) for w in workspaces]
