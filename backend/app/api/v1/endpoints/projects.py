from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.config import settings
from app.db.models import Project, User, Workspace
from app.db.session import get_db
from app.services.document_service import DocumentExtractionError, DocumentService

router = APIRouter()


class ProjectCreateSchema(BaseModel):
    name: str
    workspace_id: str
    business_idea: Optional[str] = None


class ProjectResponseSchema(BaseModel):
    id: str
    name: str
    workspace_id: str
    business_idea: Optional[str] = None
    document_text: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


@router.post("/", response_model=ProjectResponseSchema)
def create_project(
    payload: ProjectCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ws = db.query(Workspace).filter(Workspace.id == payload.workspace_id, Workspace.owner_id == current_user.id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found or unauthorized.")

    project = Project(
        name=payload.name,
        workspace_id=payload.workspace_id,
        business_idea=payload.business_idea,
        status="DRAFT"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponseSchema.model_validate(project)


@router.get("/", response_model=List[ProjectResponseSchema])
def list_projects(
    workspace_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Project).join(Workspace).filter(Workspace.owner_id == current_user.id)
    if workspace_id:
        query = query.filter(Project.workspace_id == workspace_id)
    projects = query.all()
    return [ProjectResponseSchema.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponseSchema)
def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return ProjectResponseSchema.model_validate(project)


class ProjectUpdateSchema(BaseModel):
    name: Optional[str] = None
    business_idea: Optional[str] = None


@router.put("/{project_id}", response_model=ProjectResponseSchema)
def update_project(
    project_id: str,
    payload: ProjectUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if payload.name is not None:
        project.name = payload.name
    if payload.business_idea is not None:
        project.business_idea = payload.business_idea
    db.commit()
    db.refresh(project)
    return ProjectResponseSchema.model_validate(project)



async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    contents = await file.read()
    if len(contents) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES / (1024*1024)}MB."
        )

    try:
        extracted_text = DocumentService.extract_text_from_bytes(contents, file.filename or "file.pdf")
        project.document_text = extracted_text
        if not project.business_idea or len(project.business_idea.strip()) < 5:
            project.business_idea = extracted_text[:1000]
        db.commit()
        db.refresh(project)
        return ProjectResponseSchema.model_validate(project)
    except DocumentExtractionError as err:
        raise HTTPException(status_code=400, detail=str(err))
