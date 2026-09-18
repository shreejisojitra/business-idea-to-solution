"""
Module 13: Analytics API endpoints.
- GET /projects/{project_id}/analytics  — project-level analytics (owner only)
- GET /chatbots/{chatbot_id}/analytics  — chatbot-level analytics (owner only)
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.models import (
    AIUsageRecord, ChatMessage, Conversation, KnowledgeSource,
    Project, PublicChatbot, PublicVisitorSession, User, Workspace,
)
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_PERIODS = {
    "today": 1,
    "7d": 7,
    "30d": 30,
}


def _since(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


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


# ── Project Analytics ──────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/analytics")
def get_project_analytics(
    project_id: str,
    period: Optional[str] = Query("30d", description="today | 7d | 30d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns usage analytics for a project. Owner access only."""
    _verify_project_owner(db, project_id, current_user.id)

    days = _PERIODS.get(period, 30)
    since = _since(days)

    # Chat message counts
    total_messages = (
        db.query(func.count(ChatMessage.id))
        .join(Conversation, ChatMessage.conversation_id == Conversation.id)
        .filter(Conversation.project_id == project_id)
        .scalar() or 0
    )
    messages_in_period = (
        db.query(func.count(ChatMessage.id))
        .join(Conversation, ChatMessage.conversation_id == Conversation.id)
        .filter(
            Conversation.project_id == project_id,
            ChatMessage.created_at >= since,
        )
        .scalar() or 0
    )

    # Conversation counts
    total_conversations = (
        db.query(func.count(Conversation.id))
        .filter(Conversation.project_id == project_id)
        .scalar() or 0
    )

    # AI usage records
    usage_q = db.query(AIUsageRecord).filter(
        AIUsageRecord.project_id == project_id,
        AIUsageRecord.created_at >= since,
    )
    usage_records = usage_q.all()

    ai_requests = len(usage_records)
    ai_success = sum(1 for r in usage_records if r.success)
    ai_failed = ai_requests - ai_success

    latencies = [r.latency_ms for r in usage_records if r.latency_ms is not None]
    avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else None

    # Knowledge sources
    knowledge_count = (
        db.query(func.count(KnowledgeSource.id))
        .filter(KnowledgeSource.project_id == project_id)
        .scalar() or 0
    )

    # Daily breakdown (last `days` days)
    daily = _daily_ai_breakdown(db, project_id=project_id, days=days)

    return {
        "project_id": project_id,
        "period": period,
        "period_days": days,
        "total_conversations": total_conversations,
        "total_messages": total_messages,
        "messages_in_period": messages_in_period,
        "ai_requests": ai_requests,
        "ai_success": ai_success,
        "ai_failed": ai_failed,
        "avg_latency_ms": avg_latency_ms,
        "knowledge_sources": knowledge_count,
        "daily_breakdown": daily,
    }


# ── Chatbot Analytics ──────────────────────────────────────────────────────────

@router.get("/chatbots/{chatbot_id}/analytics")
def get_chatbot_analytics(
    chatbot_id: str,
    period: Optional[str] = Query("30d", description="today | 7d | 30d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns usage analytics for a public chatbot. Owner access only."""
    bot = db.query(PublicChatbot).filter(
        PublicChatbot.id == chatbot_id,
        PublicChatbot.owner_id == current_user.id,
    ).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found or unauthorized.")

    days = _PERIODS.get(period, 30)
    since = _since(days)

    total_sessions = (
        db.query(func.count(PublicVisitorSession.id))
        .filter(PublicVisitorSession.chatbot_id == chatbot_id)
        .scalar() or 0
    )
    sessions_in_period = (
        db.query(func.count(PublicVisitorSession.id))
        .filter(
            PublicVisitorSession.chatbot_id == chatbot_id,
            PublicVisitorSession.created_at >= since,
        )
        .scalar() or 0
    )

    # Count messages from session JSON arrays
    sessions = db.query(PublicVisitorSession).filter(
        PublicVisitorSession.chatbot_id == chatbot_id
    ).all()
    total_messages = sum(len(s.messages or []) for s in sessions)

    # AI usage records for this chatbot
    usage_records = db.query(AIUsageRecord).filter(
        AIUsageRecord.chatbot_id == chatbot_id,
        AIUsageRecord.created_at >= since,
    ).all()

    ai_requests = len(usage_records)
    ai_success = sum(1 for r in usage_records if r.success)
    ai_failed = ai_requests - ai_success

    latencies = [r.latency_ms for r in usage_records if r.latency_ms is not None]
    avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else None

    daily = _daily_ai_breakdown(db, chatbot_id=chatbot_id, days=days)

    return {
        "chatbot_id": chatbot_id,
        "chatbot_name": bot.name,
        "period": period,
        "period_days": days,
        "total_sessions": total_sessions,
        "sessions_in_period": sessions_in_period,
        "total_messages": total_messages,
        "ai_requests": ai_requests,
        "ai_success": ai_success,
        "ai_failed": ai_failed,
        "avg_latency_ms": avg_latency_ms,
        "daily_breakdown": daily,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _daily_ai_breakdown(
    db: Session,
    *,
    project_id: Optional[str] = None,
    chatbot_id: Optional[str] = None,
    days: int = 30,
) -> list:
    """Returns a list of {date, requests, success, failed} dicts for the last `days` days."""
    since = _since(days)
    q = db.query(AIUsageRecord).filter(AIUsageRecord.created_at >= since)
    if project_id:
        q = q.filter(AIUsageRecord.project_id == project_id)
    if chatbot_id:
        q = q.filter(AIUsageRecord.chatbot_id == chatbot_id)

    records = q.all()

    # Bucket by date string
    buckets: dict = {}
    for r in records:
        day = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown"
        if day not in buckets:
            buckets[day] = {"date": day, "requests": 0, "success": 0, "failed": 0}
        buckets[day]["requests"] += 1
        if r.success:
            buckets[day]["success"] += 1
        else:
            buckets[day]["failed"] += 1

    return sorted(buckets.values(), key=lambda x: x["date"])
