"""
Module 12: AI Usage Tracking Service.
Records AI request outcomes for analytics.
All writes are fire-and-forget: failures are logged but never propagate.
"""
import logging
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import AIUsageRecord

logger = logging.getLogger(__name__)


class UsageService:
    """Records AI usage events. All methods are safe — they never raise."""

    @staticmethod
    def record(
        db: Session,
        *,
        request_type: str = "chat",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        chatbot_id: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        latency_ms: Optional[float] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
    ) -> None:
        """
        Persist one AI usage record.
        Silently swallows all exceptions so a DB write failure never breaks AI responses.
        """
        try:
            record = AIUsageRecord(
                user_id=user_id,
                project_id=project_id,
                chatbot_id=chatbot_id,
                session_id=session_id,
                request_type=request_type,
                provider=settings.LLM_PROVIDER,
                model=settings.LLM_MODEL,
                success=success,
                error_message=error_message[:500] if error_message else None,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )
            db.add(record)
            db.commit()
        except Exception as exc:
            logger.warning(f"UsageService.record failed (non-critical): {exc}")
            try:
                db.rollback()
            except Exception:
                pass
