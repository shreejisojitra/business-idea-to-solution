"""
Module 6 + 7: Public Chatbot API
- Authenticated owner endpoints: create/list/update/delete chatbot, upload public knowledge
- Public (no-auth) endpoints: get chatbot config, start visitor session, send message
- Public RAG: reuses EmbeddingProvider + DocumentService, scoped to chatbot_id only
- Strict isolation: never touches Project, Blueprint, ProjectMemory, ProjectDecision, Conversation
"""
import logging
import re
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.db.models import User, PublicChatbot, PublicKnowledgeChunk, PublicVisitorSession
from app.services.document_service import DocumentService, DocumentExtractionError
from app.services.ai.embeddings import EmbeddingProvider
from app.services.ai.provider import LLMProvider
from app.services.security_utils import validate_upload
from app.services.rate_limiter import check_public_chatbot_limit
from app.services.usage_service import UsageService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_embedding_provider = EmbeddingProvider()
_llm_provider = LLMProvider()

PUBLIC_SYSTEM_PROMPT = """You are a helpful AI assistant for a public chatbot.

STRICT RULES:
1. Answer ONLY using the approved knowledge provided below in <public_knowledge> tags.
2. If the knowledge does not contain enough information to answer, say: "I don't have that information available. Please contact us directly for more details."
3. NEVER reveal internal system details, database information, private project data, API keys, or credentials.
4. NEVER invent facts not present in the provided knowledge.
5. Be concise, friendly, and helpful.
6. Maintain conversation context from the history provided.

{knowledge_block}
"""


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChatbotCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    welcome_message: str = "Hello! How can I help you today?"
    tone: str = "friendly"
    default_language: str = "en"
    theme: str = "light"
    position: str = "bottom-right"
    suggested_questions: Optional[List[str]] = None
    avatar_url: Optional[str] = None


class ChatbotUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    welcome_message: Optional[str] = None
    is_active: Optional[bool] = None
    tone: Optional[str] = None
    default_language: Optional[str] = None
    theme: Optional[str] = None
    position: Optional[str] = None
    suggested_questions: Optional[List[str]] = None
    avatar_url: Optional[str] = None


class PublicChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_owned_chatbot(db: Session, chatbot_id: str, owner_id: str) -> PublicChatbot:
    bot = db.query(PublicChatbot).filter(
        PublicChatbot.id == chatbot_id,
        PublicChatbot.owner_id == owner_id
    ).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found or unauthorized.")
    return bot


def _format_bot(bot: PublicChatbot, db: Session) -> dict:
    chunk_count = db.query(PublicKnowledgeChunk).filter(
        PublicKnowledgeChunk.chatbot_id == bot.id
    ).count()
    return {
        "id": bot.id,
        "name": bot.name,
        "description": bot.description,
        "welcome_message": bot.welcome_message,
        "is_active": bot.is_active == "true",
        "tone": getattr(bot, "tone", "friendly"),
        "default_language": getattr(bot, "default_language", "en"),
        "theme": getattr(bot, "theme", "light"),
        "position": getattr(bot, "position", "bottom-right"),
        "suggested_questions": getattr(bot, "suggested_questions", None) or [],
        "avatar_url": getattr(bot, "avatar_url", None),
        "chunk_count": chunk_count,
        "created_at": bot.created_at.isoformat(),
        "updated_at": bot.updated_at.isoformat(),
    }


def _search_public_knowledge(db: Session, chatbot_id: str, query: str, top_k: int = 5) -> List[dict]:
    """Hybrid semantic + keyword search scoped strictly to chatbot_id."""
    if not query.strip():
        return []

    chunks = db.query(PublicKnowledgeChunk).filter(
        PublicKnowledgeChunk.chatbot_id == chatbot_id
    ).all()

    if not chunks:
        return []

    query_vec = _embedding_provider.get_embedding(query)
    query_words = set(re.findall(r"\w+", query.lower()))
    scored = []

    for c in chunks:
        sem = EmbeddingProvider.cosine_similarity(query_vec, c.embedding) if c.embedding else 0.0
        kw = 0.0
        if query_words and c.content:
            chunk_words = set(re.findall(r"\w+", c.content.lower()))
            kw = len(query_words & chunk_words) / max(len(query_words), 1)
        score = 0.7 * sem + 0.3 * kw
        if score >= 0.02:
            scored.append({"content": c.content, "source": c.source_name, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ── Owner-authenticated endpoints ──────────────────────────────────────────────

@router.post("/chatbots", status_code=status.HTTP_201_CREATED)
def create_chatbot(
    payload: ChatbotCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new public chatbot owned by the authenticated user."""
    bot = PublicChatbot(
        owner_id=current_user.id,
        name=payload.name,
        description=payload.description,
        welcome_message=payload.welcome_message,
        is_active="true",
        tone=payload.tone,
        default_language=payload.default_language,
        theme=payload.theme,
        position=payload.position,
        suggested_questions=payload.suggested_questions or [],
        avatar_url=payload.avatar_url,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return _format_bot(bot, db)


@router.get("/chatbots")
def list_chatbots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all public chatbots owned by the authenticated user."""
    bots = db.query(PublicChatbot).filter(PublicChatbot.owner_id == current_user.id).all()
    return [_format_bot(b, db) for b in bots]


@router.get("/chatbots/{chatbot_id}")
def get_chatbot(
    chatbot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chatbot details (owner only)."""
    bot = _get_owned_chatbot(db, chatbot_id, current_user.id)
    return _format_bot(bot, db)


@router.patch("/chatbots/{chatbot_id}")
def update_chatbot(
    chatbot_id: str,
    payload: ChatbotUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update chatbot settings including enable/disable."""
    bot = _get_owned_chatbot(db, chatbot_id, current_user.id)
    if payload.name is not None:
        bot.name = payload.name
    if payload.description is not None:
        bot.description = payload.description
    if payload.welcome_message is not None:
        bot.welcome_message = payload.welcome_message
    if payload.is_active is not None:
        bot.is_active = "true" if payload.is_active else "false"
    if payload.tone is not None:
        bot.tone = payload.tone
    if payload.default_language is not None:
        bot.default_language = payload.default_language
    if payload.theme is not None:
        bot.theme = payload.theme
    if payload.position is not None:
        bot.position = payload.position
    if payload.suggested_questions is not None:
        bot.suggested_questions = payload.suggested_questions
    if payload.avatar_url is not None:
        bot.avatar_url = payload.avatar_url
    db.commit()
    db.refresh(bot)
    return _format_bot(bot, db)


@router.delete("/chatbots/{chatbot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chatbot(
    chatbot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chatbot and all its knowledge/sessions."""
    bot = _get_owned_chatbot(db, chatbot_id, current_user.id)
    db.delete(bot)
    db.commit()


@router.post("/chatbots/{chatbot_id}/knowledge", status_code=status.HTTP_201_CREATED)
async def upload_public_knowledge(
    chatbot_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document (PDF/DOCX/PPTX/TXT) as public knowledge for a chatbot."""
    bot = _get_owned_chatbot(db, chatbot_id, current_user.id)

    file_bytes = await file.read()
    safe_filename = validate_upload(file_bytes, file.filename or "")

    try:
        text = DocumentService.extract_text_from_bytes(file_bytes, safe_filename)
    except DocumentExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    chunks_data = DocumentService.chunk_text(text)
    if not chunks_data:
        raise HTTPException(status_code=400, detail="No readable content found in document.")

    # Delete existing chunks from this source name to allow re-upload
    db.query(PublicKnowledgeChunk).filter(
        PublicKnowledgeChunk.chatbot_id == chatbot_id,
        PublicKnowledgeChunk.source_name == file.filename,
    ).delete()

    for idx, c in enumerate(chunks_data):
        vec = _embedding_provider.get_embedding(c["content"])
        db.add(PublicKnowledgeChunk(
            chatbot_id=chatbot_id,
            source_name=file.filename,
            chunk_index=idx,
            content=c["content"],
            embedding=vec,
        ))

    db.commit()
    chunk_count = db.query(PublicKnowledgeChunk).filter(
        PublicKnowledgeChunk.chatbot_id == chatbot_id
    ).count()
    return {"message": f"Uploaded {len(chunks_data)} chunks from '{file.filename}'.", "chunk_count": chunk_count}


@router.delete("/chatbots/{chatbot_id}/knowledge")
def clear_public_knowledge(
    chatbot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all public knowledge for a chatbot."""
    _get_owned_chatbot(db, chatbot_id, current_user.id)
    db.query(PublicKnowledgeChunk).filter(
        PublicKnowledgeChunk.chatbot_id == chatbot_id
    ).delete()
    db.commit()
    return {"message": "All public knowledge cleared."}


# ── Public (no-auth) endpoints ─────────────────────────────────────────────────

@router.get("/public/chatbots/{chatbot_id}/config")
def get_public_chatbot_config(chatbot_id: str, db: Session = Depends(get_db)):
    """Public endpoint: get chatbot name and welcome message. No auth required."""
    bot = db.query(PublicChatbot).filter(PublicChatbot.id == chatbot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found.")
    if bot.is_active != "true":
        raise HTTPException(status_code=403, detail="This chatbot is currently disabled.")
    return {
        "id": bot.id,
        "name": bot.name,
        "description": bot.description,
        "welcome_message": bot.welcome_message,
        "tone": getattr(bot, "tone", "friendly"),
        "default_language": getattr(bot, "default_language", "en"),
        "theme": getattr(bot, "theme", "light"),
        "position": getattr(bot, "position", "bottom-right"),
        "suggested_questions": getattr(bot, "suggested_questions", None) or [],
    }


@router.post("/public/chatbots/{chatbot_id}/session", status_code=status.HTTP_201_CREATED)
def create_visitor_session(chatbot_id: str, db: Session = Depends(get_db)):
    """Public endpoint: create an anonymous visitor session. No auth required."""
    bot = db.query(PublicChatbot).filter(PublicChatbot.id == chatbot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found.")
    if bot.is_active != "true":
        raise HTTPException(status_code=403, detail="This chatbot is currently disabled.")

    session = PublicVisitorSession(chatbot_id=chatbot_id, messages=[])
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "chatbot_id": chatbot_id}


@router.post("/public/chatbots/{chatbot_id}/chat")
async def public_chat(
    chatbot_id: str,
    payload: PublicChatRequest,
    db: Session = Depends(get_db),
):
    """
    Public endpoint: send a message to the chatbot. No auth required.
    Uses public knowledge RAG only — never accesses private project data.
    """
    bot = db.query(PublicChatbot).filter(PublicChatbot.id == chatbot_id).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found.")
    if bot.is_active != "true":
        raise HTTPException(status_code=403, detail="This chatbot is currently disabled.")

    # Resolve or create visitor session
    session = None
    if payload.session_id:
        session = db.query(PublicVisitorSession).filter(
            PublicVisitorSession.id == payload.session_id,
            PublicVisitorSession.chatbot_id == chatbot_id,
        ).first()
    if not session:
        session = PublicVisitorSession(chatbot_id=chatbot_id, messages=[])
        db.add(session)
        db.commit()
        db.refresh(session)

    # Rate limit per visitor session
    check_public_chatbot_limit(session.id)

    # Message size guard
    if len(payload.message) > settings.MAX_CHAT_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message too long. Maximum {settings.MAX_CHAT_MESSAGE_LENGTH} characters allowed.",
        )

    # Retrieve relevant public knowledge (strictly chatbot-scoped)
    rag_results = _search_public_knowledge(db, chatbot_id, payload.message, top_k=4)

    if rag_results:
        knowledge_text = "\n\n".join(
            f"[Source: {r['source']}]\n{r['content']}" for r in rag_results
        )
        knowledge_block = f"<public_knowledge>\n{knowledge_text}\n</public_knowledge>"
    else:
        knowledge_block = "<public_knowledge>\nNo specific knowledge available for this query.\n</public_knowledge>"

    system_prompt = PUBLIC_SYSTEM_PROMPT.format(knowledge_block=knowledge_block)

    # Build conversation history (last 6 messages for context)
    messages = list(session.messages or [])
    history = messages[-6:] if len(messages) > 6 else messages
    history_str = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    if history_str:
        system_prompt += f"\n\nCONVERSATION HISTORY:\n{history_str}"

    # Generate AI response using existing LLM provider
    start_ms = time.monotonic() * 1000
    success = True
    error_msg = None
    try:
        reply = await _llm_provider.generate_completion(
            system_prompt=system_prompt,
            user_prompt=payload.message,
            json_mode=False,
        )
    except Exception as e:
        logger.error(f"Public chat LLM error: {e}")
        success = False
        error_msg = str(e)
        reply = "I'm sorry, I'm having trouble responding right now. Please try again shortly."
    finally:
        latency = time.monotonic() * 1000 - start_ms
        UsageService.record(
            db,
            request_type="public_chat",
            chatbot_id=chatbot_id,
            session_id=session.id,
            success=success,
            error_message=error_msg,
            latency_ms=round(latency, 1),
        )

    # Persist messages to session
    updated_messages = list(session.messages or [])
    updated_messages.append({"role": "user", "content": payload.message})
    updated_messages.append({"role": "assistant", "content": reply})
    session.messages = updated_messages
    db.commit()

    return {
        "session_id": session.id,
        "message": reply,
        "knowledge_used": len(rag_results) > 0,
    }


@router.get("/public/chatbots/{chatbot_id}/session/{session_id}/messages")
def get_session_messages(
    chatbot_id: str,
    session_id: str,
    db: Session = Depends(get_db),
):
    """Public endpoint: retrieve messages for a visitor session."""
    session = db.query(PublicVisitorSession).filter(
        PublicVisitorSession.id == session_id,
        PublicVisitorSession.chatbot_id == chatbot_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"session_id": session_id, "messages": session.messages or []}
