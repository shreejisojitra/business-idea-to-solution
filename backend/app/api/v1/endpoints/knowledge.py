import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.db.models import User, Project, KnowledgeSource, KnowledgeChunk, WebsitePage
from app.services.ai.rag_service import RAGService, RAGError
from app.services.security_utils import validate_upload, validate_url_for_crawl

logger = logging.getLogger(__name__)

router = APIRouter()


class WebsiteIngestRequest(BaseModel):
    url: str
    name: Optional[str] = None


class KnowledgeSourceOut(BaseModel):
    id: str
    project_id: str
    type: str
    name: str
    source_url: Optional[str] = None
    filename: Optional[str] = None
    status: str
    extracted_text_snippet: Optional[str] = None
    chunk_count: int = 0
    created_at: str
    updated_at: str


def _verify_project_ownership(db: Session, project_id: str, user_id: str) -> Project:
    from app.db.models import Workspace
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == user_id
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found or unauthorized.")
    return project


def _format_source(source: KnowledgeSource, db: Session) -> dict:
    chunk_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source.id).count()
    snippet = source.extracted_text[:200] + "..." if source.extracted_text and len(source.extracted_text) > 200 else source.extracted_text

    return {
        "id": source.id,
        "project_id": source.project_id,
        "type": source.type,
        "name": source.name,
        "source_url": source.source_url,
        "filename": source.filename,
        "status": source.status,
        "extracted_text_snippet": snippet,
        "chunk_count": chunk_count,
        "created_at": source.created_at.isoformat() if source.created_at else "",
        "updated_at": source.updated_at.isoformat() if source.updated_at else ""
    }


@router.post("/projects/{project_id}/knowledge/upload", status_code=status.HTTP_201_CREATED)
async def upload_document_knowledge(
    project_id: str,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Uploads a document file (PDF, DOCX, PPTX, TXT, CSV, MD) to ingest into project knowledge RAG."""
    _verify_project_ownership(db, project_id, current_user.id)

    file_bytes = await file.read()
    safe_filename = validate_upload(file_bytes, file.filename or "")

    rag_service = RAGService()
    try:
        source = rag_service.ingest_document(
            db,
            project_id=project_id,
            filename=safe_filename,
            file_bytes=file_bytes,
            source_name=name
        )
        return _format_source(source, db)
    except RAGError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/projects/{project_id}/knowledge/website", status_code=status.HTTP_201_CREATED)
async def ingest_website_knowledge(
    project_id: str,
    payload: WebsiteIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crawls and ingests a public website URL into project knowledge RAG."""
    _verify_project_ownership(db, project_id, current_user.id)
    validated_url = validate_url_for_crawl(payload.url)

    rag_service = RAGService()
    try:
        source = await rag_service.ingest_website(
            db,
            project_id=project_id,
            start_url=validated_url,
            source_name=payload.name
        )
        return _format_source(source, db)
    except RAGError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/projects/{project_id}/knowledge")
async def list_project_knowledge_sources(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all knowledge sources for a project."""
    _verify_project_ownership(db, project_id, current_user.id)

    sources = db.query(KnowledgeSource).filter(
        KnowledgeSource.project_id == project_id
    ).order_by(KnowledgeSource.created_at.desc()).all()

    return [_format_source(s, db) for s in sources]


@router.get("/projects/{project_id}/knowledge/{source_id}")
async def get_knowledge_source_details(
    project_id: str,
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetches details, chunks, and website pages for a specific knowledge source."""
    _verify_project_ownership(db, project_id, current_user.id)

    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id,
        KnowledgeSource.project_id == project_id
    ).first()

    if not source:
        raise HTTPException(status_code=404, detail="Knowledge source not found.")

    res = _format_source(source, db)

    # Attach chunks summary
    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_source_id == source.id).all()
    res["chunks"] = [
        {
            "id": c.id,
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "section_heading": c.section_heading,
            "source_url": c.source_url,
            "snippet": c.content[:150] + "..." if len(c.content) > 150 else c.content
        } for c in chunks
    ]

    # Attach website pages if applicable
    if source.type == "WEBSITE":
        pages = db.query(WebsitePage).filter(WebsitePage.knowledge_source_id == source.id).all()
        res["pages"] = [
            {
                "id": p.id,
                "url": p.url,
                "title": p.title,
                "status": p.status,
                "content_hash": p.content_hash,
                "last_fetched_at": p.last_fetched_at.isoformat() if p.last_fetched_at else ""
            } for p in pages
        ]

    return res


@router.post("/projects/{project_id}/knowledge/{source_id}/refresh")
async def refresh_website_knowledge_source(
    project_id: str,
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-crawls and refreshes a website knowledge source."""
    _verify_project_ownership(db, project_id, current_user.id)

    rag_service = RAGService()
    try:
        source = await rag_service.refresh_website(db, knowledge_source_id=source_id, project_id=project_id)
        return _format_source(source, db)
    except RAGError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.delete("/projects/{project_id}/knowledge/{source_id}")
async def delete_knowledge_source(
    project_id: str,
    source_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a knowledge source and all its associated chunks."""
    _verify_project_ownership(db, project_id, current_user.id)

    rag_service = RAGService()
    try:
        rag_service.delete_knowledge_source(db, knowledge_source_id=source_id, project_id=project_id)
        return {"message": "Knowledge source deleted successfully."}
    except RAGError as err:
        raise HTTPException(status_code=400, detail=str(err))
