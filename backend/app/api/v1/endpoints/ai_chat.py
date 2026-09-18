import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User, Project, Workspace, Conversation, ChatMessage
from app.api.v1.endpoints.auth import get_current_user
from app.services.ai.chat_service import AIChatService
from app.services.rate_limiter import check_authenticated_limit, check_ai_limit
from app.services.usage_service import UsageService
from app.core.config import settings

router = APIRouter()
chat_service = AIChatService()


class ChatRequest(BaseModel):
    project_id: str
    message: str
    conversation_id: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.post("/chat", summary="Send message to AI Consultant")
async def chat_with_consultant(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Rate limiting
    check_authenticated_limit(current_user.id)
    check_ai_limit(current_user.id)

    # Message size guard
    if len(payload.message) > settings.MAX_CHAT_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message too long. Maximum {settings.MAX_CHAT_MESSAGE_LENGTH} characters allowed.",
        )

    # Verify project ownership
    project = db.query(Project).join(Workspace).filter(
        Project.id == payload.project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized.")

    start_ms = time.monotonic() * 1000
    success = True
    error_msg = None
    try:
        res = await chat_service.process_chat_message(
            db=db,
            user_id=current_user.id,
            project_id=payload.project_id,
            user_message=payload.message,
            conversation_id=payload.conversation_id
        )
    except Exception as exc:
        success = False
        error_msg = str(exc)
        raise
    finally:
        latency = time.monotonic() * 1000 - start_ms
        UsageService.record(
            db,
            request_type="chat",
            user_id=current_user.id,
            project_id=payload.project_id,
            success=success,
            error_message=error_msg,
            latency_ms=round(latency, 1),
        )

    # Refetch project to return synced state
    refreshed_proj = db.query(Project).filter(Project.id == payload.project_id).first()
    if refreshed_proj:
        res["project"] = {
            "id": refreshed_proj.id,
            "workspace_id": refreshed_proj.workspace_id,
            "name": refreshed_proj.name,
            "business_idea": refreshed_proj.business_idea,
            "document_text": refreshed_proj.document_text,
            "status": refreshed_proj.status,
            "created_at": refreshed_proj.created_at.isoformat()
        }
    return res


@router.get("/conversations", summary="List project conversations")
def list_conversations(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(Workspace).filter(
        Project.id == project_id,
        Workspace.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or unauthorized.")

    convs = db.query(Conversation).filter(
        Conversation.project_id == project_id,
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).all()

    return [
        {
            "id": c.id,
            "project_id": c.project_id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat()
        } for c in convs
    ]


@router.get("/conversations/{conversation_id}/messages", summary="Get messages in conversation")
def get_conversation_messages(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")

    msgs = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat()
        } for m in msgs
    ]


@router.delete("/conversations/{conversation_id}", summary="Delete a conversation")
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found or unauthorized.")

    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted successfully."}
