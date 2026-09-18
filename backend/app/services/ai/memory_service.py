import re
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.db.models import ProjectMemory, ProjectDecision, ConversationSummary, ChatMessage, Project
from app.services.ai.provider import LLMProvider

logger = logging.getLogger(__name__)

# Sensitive terms filter to ensure memory safety
SECRET_PATTERNS = [
    r"api[_-]?key",
    r"sk-[a-zA-Z0-9_-]+",
    r"secret",
    r"password",
    r"bearer\s+[a-zA-Z0-9\._\-]+",
    r"auth[_-]?token",
    r"private[_-]?key"
]


def contains_secret(text: str) -> bool:
    """Checks if text contains credentials, tokens, or API keys."""
    if not text:
        return False
    text_lower = text.lower()
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


class MemoryService:
    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or LLMProvider()

    def extract_and_process(
        self,
        db: Session,
        project_id: str,
        conversation_id: str,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Parses user input for:
        1. Explicit Project Facts (team size, timeline, target users, constraints).
        2. Technology / Scope Decisions (PostgreSQL, MongoDB, no mobile app).
        3. User Corrections / Memory Deletions ("Forget database decision", "I never said 5 developers").
        """
        if contains_secret(user_message):
            logger.info("Skipping memory extraction due to potential sensitive information / secret detected.")
            return {"facts_extracted": 0, "decisions_updated": 0}

        msg_lower = user_message.lower().strip()
        facts_count = 0
        decisions_count = 0

        # --- 1. User Corrections / Forget Commands ---
        if "forget" in msg_lower or "never said" in msg_lower or "cancel decision" in msg_lower:
            if "database" in msg_lower or "db" in msg_lower:
                db.query(ProjectDecision).filter(
                    ProjectDecision.project_id == project_id,
                    ProjectDecision.category == "database",
                    ProjectDecision.status == "accepted"
                ).update({"status": "superseded"})
                db.commit()
                decisions_count += 1
            if "developer" in msg_lower or "team" in msg_lower:
                db.query(ProjectMemory).filter(
                    ProjectMemory.project_id == project_id,
                    ProjectMemory.key == "team_size"
                ).delete()
                db.commit()
                facts_count += 1

        # --- 2. Fact Extractions ---
        # Target Users — extract the actual text after the trigger phrase
        target_triggers = ["target user", "users are", "target users are", "for general users", "for college students", "our users are", "users will be", "designed for"]
        if any(t in msg_lower for t in target_triggers):
            # Try to extract the actual user description from the message
            target = self._extract_target_users(user_message)
            self._upsert_memory(db, project_id, "business", "target_users", target)
            facts_count += 1

        # Team Size
        team_match = re.search(r"(\d+)\s*(developer|dev|engineer|people|member)", msg_lower)
        if team_match:
            size_val = team_match.group(1)
            self._upsert_memory(db, project_id, "project", "team_size", f"{size_val} developers")
            facts_count += 1
        elif "only have 2 developers" in msg_lower or "two developers" in msg_lower:
            self._upsert_memory(db, project_id, "project", "team_size", "2 developers")
            facts_count += 1

        # Timeline / Duration
        time_match = re.search(r"(\d+)\s*(week|month|day)", msg_lower)
        if time_match:
            val, unit = time_match.group(1), time_match.group(2)
            self._upsert_memory(db, project_id, "project", "timeline", f"{val} {unit}s")
            facts_count += 1

        # --- 3. Technology & Scope Decisions (with Superseding Logic) ---
        # Database Decision
        if "use postgresql" in msg_lower or "using postgresql" in msg_lower or "choose postgresql" in msg_lower or "select postgresql" in msg_lower or "we'll use postgresql" in msg_lower:
            self._register_decision(db, project_id, conversation_id, "database", "PostgreSQL", "User selected PostgreSQL for core relational database.")
            decisions_count += 1
        elif "use mongodb" in msg_lower or "using mongodb" in msg_lower or "choose mongodb" in msg_lower or "select mongodb" in msg_lower or "we'll use mongodb" in msg_lower or "mongodb may be better" in msg_lower or "mongodb instead" in msg_lower:
            self._register_decision(db, project_id, conversation_id, "database", "MongoDB", "User selected MongoDB for flexible document storage.")
            decisions_count += 1

        # Mobile App Scope Decision
        if "no mobile app" in msg_lower or "not build a mobile app" in msg_lower or "mobile app is not required" in msg_lower or "without mobile app" in msg_lower or "mobile app not in" in msg_lower:
            self._register_decision(db, project_id, conversation_id, "scope", "No Mobile App in MVP", "User explicitly excluded mobile app from initial MVP scope.")
            decisions_count += 1

        return {"facts_extracted": facts_count, "decisions_updated": decisions_count}

    def _extract_target_users(self, message: str) -> str:
        """Extracts the actual target user description from the user message."""
        msg_lower = message.lower()
        # Try to extract text after common trigger phrases
        for trigger in ["target users are", "users are", "designed for", "our users are", "users will be", "for "]:
            idx = msg_lower.find(trigger)
            if idx != -1:
                extracted = message[idx + len(trigger):].strip().rstrip(".!?,")
                if extracted and len(extracted) > 2:
                    # Title-case and limit to reasonable length
                    return extracted[:80].strip().title()
        # Fallback: return the whole message trimmed and title-cased
        return message.strip()[:80].title()

    def _upsert_memory(self, db: Session, project_id: str, category: str, key: str, value: str):
        existing = db.query(ProjectMemory).filter(
            ProjectMemory.project_id == project_id,
            ProjectMemory.key == key
        ).first()
        if existing:
            existing.value = value
            existing.category = category
        else:
            mem = ProjectMemory(project_id=project_id, category=category, key=key, value=value)
            db.add(mem)
        db.commit()

    def _register_decision(
        self,
        db: Session,
        project_id: str,
        conversation_id: str,
        category: str,
        decision_text: str,
        reason: str
    ):
        """Registers an accepted decision and marks previous decisions in the same category as superseded."""
        # Supersede existing accepted decisions in this category
        db.query(ProjectDecision).filter(
            ProjectDecision.project_id == project_id,
            ProjectDecision.category == category,
            ProjectDecision.status == "accepted"
        ).update({"status": "superseded"})

        # Add new accepted decision
        new_dec = ProjectDecision(
            project_id=project_id,
            conversation_id=conversation_id,
            category=category,
            decision=decision_text,
            reason=reason,
            status="accepted"
        )
        db.add(new_dec)
        db.commit()

    async def summarize_conversation_if_needed(self, db: Session, conversation_id: str):
        """Generates or updates conversation summary when message count reaches or exceeds 10."""
        msgs = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.created_at.asc()).all()
        if len(msgs) < 10:
            return

        # Build actual summary from conversation content
        dialog_lines = [f"{m.role.upper()}: {m.content[:200]}" for m in msgs]
        full_dialog = "\n".join(dialog_lines)

        summary_text = f"Conversation Summary ({len(msgs)} messages):\n{full_dialog[:1500]}"

        existing_summary = db.query(ConversationSummary).filter(ConversationSummary.conversation_id == conversation_id).first()
        if existing_summary:
            existing_summary.summary = summary_text
            existing_summary.last_summarized_message_id = msgs[-1].id
        else:
            rec = ConversationSummary(
                conversation_id=conversation_id,
                summary=summary_text,
                last_summarized_message_id=msgs[-1].id
            )
            db.add(rec)
        db.commit()
