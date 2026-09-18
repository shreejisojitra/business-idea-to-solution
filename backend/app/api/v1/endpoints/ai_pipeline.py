import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.models import Blueprint, Project, User, Workspace
from app.db.session import get_db
from app.services.ai.orchestrator import AIOrchestrator, OrchestratorError
from app.services.ai.schemas import FullTransformationBlueprint

logger = logging.getLogger(__name__)
router = APIRouter()
orchestrator = AIOrchestrator()


class StageUpdateSchema(BaseModel):
    data: Dict[str, Any]


class GenerateRequestSchema(BaseModel):
    business_idea: Optional[str] = None


@router.post("/projects/{project_id}/generate", response_model=FullTransformationBlueprint)
async def generate_blueprint(
    project_id: str,
    payload: Optional[GenerateRequestSchema] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    business_idea_text = (payload.business_idea if payload and payload.business_idea else None) or project.business_idea or project.document_text
    if not business_idea_text or len(business_idea_text.strip()) < 5:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid business idea text or upload a document before generating."
        )

    # Save business idea if changed
    project.business_idea = business_idea_text.strip()
    project.status = "GENERATING"
    db.commit()

    try:
        blueprint_result = await orchestrator.run_full_pipeline(business_idea_text)
        
        # Save or update blueprint record in DB
        db_bp = db.query(Blueprint).filter(Blueprint.project_id == project_id).first()
        if not db_bp:
            db_bp = Blueprint(project_id=project_id)
            db.add(db_bp)

        db_bp.business_analysis = blueprint_result.business_analysis.model_dump()
        db_bp.ai_opportunities = blueprint_result.ai_opportunities.model_dump()
        db_bp.solution_blueprint = blueprint_result.solution_blueprint.model_dump()
        db_bp.architecture = blueprint_result.architecture.model_dump()
        db_bp.data_api_design = blueprint_result.data_api_design.model_dump()
        db_bp.ux_design = blueprint_result.ux_design.model_dump()
        db_bp.roadmap = blueprint_result.roadmap.model_dump()

        project.status = "COMPLETED"
        db.commit()
        db.refresh(db_bp)

        return blueprint_result
    except OrchestratorError as err:
        project.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=502, detail="AI pipeline failed. Please check your provider configuration and try again.")
    except Exception:
        project.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=500, detail="An unexpected error occurred during blueprint generation.")


@router.get("/projects/{project_id}/blueprint")
def get_project_blueprint(
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

    bp = db.query(Blueprint).filter(Blueprint.project_id == project_id).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not generated yet.")

    return {
        "project_id": project_id,
        "project_name": project.name,
        "business_idea": project.business_idea,
        "blueprint": {
            "business_analysis": bp.business_analysis,
            "ai_opportunities": bp.ai_opportunities,
            "solution_blueprint": bp.solution_blueprint,
            "architecture": bp.architecture,
            "data_api_design": bp.data_api_design,
            "ux_design": bp.ux_design,
            "roadmap": bp.roadmap,
        },
        "stage_statuses": bp.stage_statuses or {},
        "updated_at": bp.updated_at
    }



@router.put("/projects/{project_id}/blueprint/stages/{stage_name}")
def update_blueprint_stage(
    project_id: str,
    stage_name: str,
    payload: StageUpdateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    bp = db.query(Blueprint).filter(Blueprint.project_id == project_id).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found.")

    valid_stages = [
        "business_analysis", "ai_opportunities", "solution_blueprint",
        "architecture", "data_api_design", "ux_design", "roadmap"
    ]
    if stage_name not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Invalid stage name: {stage_name}")

    setattr(bp, stage_name, payload.data)
    db.commit()
    db.refresh(bp)
    return {"message": f"Stage '{stage_name}' updated successfully."}


@router.post("/projects/{project_id}/regenerate/{stage_name}")
async def regenerate_stage(
    project_id: str,
    stage_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    bp = db.query(Blueprint).filter(Blueprint.project_id == project_id).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint must be generated first.")

    existing_blueprint = {
        "business_analysis": bp.business_analysis,
        "ai_opportunities": bp.ai_opportunities,
        "solution_blueprint": bp.solution_blueprint,
        "architecture": bp.architecture,
        "data_api_design": bp.data_api_design,
        "ux_design": bp.ux_design,
        "roadmap": bp.roadmap,
    }

    try:
        new_stage_data = await orchestrator.regenerate_stage(
            stage_name,
            project.business_idea or "",
            existing_blueprint
        )
        data_dict = new_stage_data.model_dump()
        setattr(bp, stage_name, data_dict)
        data_dict = new_stage_data.model_dump()
        setattr(bp, stage_name, data_dict)
        db.commit()
        db.refresh(bp)
        return {"stage_name": stage_name, "data": data_dict}
    except OrchestratorError:
        raise HTTPException(status_code=502, detail="Stage regeneration failed. Please check your provider configuration and try again.")


class ChatMessageInput(BaseModel):
    message: str


@router.post(
    "/projects/{project_id}/chat",
    summary="Interactive AI Chat Assistant",
    description="Ask follow-up questions about the project solution, database, architecture, or workflow."
)
async def chat_with_project_ai(
    project_id: str,
    payload: ChatMessageInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    bp = db.query(Blueprint).filter(Blueprint.project_id == project_id).first()
    context_text = f"Business Idea: {project.business_idea or ''}\n"
    if bp:
        context_text += f"Business Analysis: {json.dumps(bp.business_analysis or {})}\n"
        context_text += f"AI Opportunities: {json.dumps(bp.ai_opportunities or {})}\n"
        context_text += f"Solution Blueprint: {json.dumps(bp.solution_blueprint or {})}\n"

    system_prompt = (
        "You are an expert AI Solution Architect & Technical Lead assisting a user with their business transformation project.\n"
        "Answer their questions concisely, accurately, and clearly based on the provided project context.\n\n"
        f"Project Context:\n{context_text}"
    )

    try:
        response_text = await orchestrator.provider.generate_completion(
            system_prompt=system_prompt,
            user_prompt=payload.message,
            json_mode=False
        )
        return {"reply": response_text}
    except Exception as exc:
        logger.error(f"Chat completion error: {str(exc)}")
        return {"reply": "AI provider is currently unavailable. Please check your API key configuration and try again."}

