from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.models import Blueprint, Project, User, Workspace
from app.db.session import get_db
from app.services.export_service import ExportService, ExportError

router = APIRouter()


@router.get("/projects/{project_id}/export")
def export_project_blueprint(
    project_id: str,
    format: str = Query("markdown", enum=["markdown", "json", "html", "pdf"]),
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

    blueprint_data = {
        "business_analysis": bp.business_analysis or {},
        "ai_opportunities": bp.ai_opportunities or {},
        "solution_blueprint": bp.solution_blueprint or {},
        "architecture": bp.architecture or {},
        "data_api_design": bp.data_api_design or {},
        "ux_design": bp.ux_design or {},
        "roadmap": bp.roadmap or {},
    }

    filename = f"{project.name.lower().replace(' ', '_')}_blueprint"

    if format == "json":
        content = ExportService.export_as_json(blueprint_data)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'}
        )
    elif format == "html":
        content = ExportService.export_as_html(project.name, blueprint_data)
        return Response(
            content=content,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename}.html"'}
        )
    elif format == "pdf":
        try:
            content = ExportService.export_as_pdf(project.name, blueprint_data)
            return Response(
                content=content,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'}
            )
        except ExportError as err:
            raise HTTPException(status_code=501, detail=str(err))
    else:  # markdown
        content = ExportService.export_as_markdown(project.name, blueprint_data)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'}
        )
