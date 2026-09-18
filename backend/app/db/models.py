from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON, Integer, Float, Boolean
from sqlalchemy.orm import relationship

from app.db.session import Base


def generate_uuid() -> str:
    """Utility to generate string UUID for primary keys."""
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="workspaces")
    projects = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False)
    business_idea = Column(Text, nullable=True)
    document_text = Column(Text, nullable=True)
    status = Column(String(50), default="DRAFT")  # DRAFT, GENERATING, COMPLETED, FAILED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    workspace = relationship("Workspace", back_populates="projects")
    blueprint = relationship("Blueprint", back_populates="project", uselist=False, cascade="all, delete-orphan")


class Blueprint(Base):
    __tablename__ = "blueprints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), unique=True, nullable=False)

    business_analysis = Column(JSON, nullable=True)
    ai_opportunities = Column(JSON, nullable=True)
    solution_blueprint = Column(JSON, nullable=True)
    architecture = Column(JSON, nullable=True)
    data_api_design = Column(JSON, nullable=True)
    ux_design = Column(JSON, nullable=True)
    roadmap = Column(JSON, nullable=True)
    stage_statuses = Column(JSON, nullable=True)  # Stage status map: {"business_analysis": "CURRENT", "architecture": "STALE", ...}

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="blueprint")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="AI Transformation Consultation")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", backref="conversations")
    user = relationship("User", backref="conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")


class ProjectMemory(Base):
    __tablename__ = "project_memories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False, default="business")  # business, requirements, technical, project
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", backref="memories")


class ProjectDecision(Base):
    __tablename__ = "project_decisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=True, index=True)
    decision = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="architecture")  # business, scope, database, backend, frontend, AI, architecture, deployment, security
    reason = Column(Text, nullable=True)
    alternatives = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="accepted")  # proposed, accepted, rejected, superseded
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", backref="decisions")


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), unique=True, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    last_summarized_message_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", backref="summary_record")


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    type = Column(String(50), nullable=False, default="DOCUMENT")  # DOCUMENT, WEBSITE, TEXT, OTHER
    name = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=True)
    filename = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="PROCESSING")  # PROCESSING, READY, FAILED
    extracted_text = Column(Text, nullable=True)
    meta_data = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", backref="knowledge_sources")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    knowledge_source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_heading = Column(String(255), nullable=True)
    source_url = Column(Text, nullable=True)
    embedding = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    knowledge_source = relationship("KnowledgeSource", backref="chunks")


class WebsitePage(Base):
    __tablename__ = "website_pages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    knowledge_source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    url = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="READY")
    last_fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    content_hash = Column(String(64), nullable=True)

    knowledge_source = relationship("KnowledgeSource", backref="pages")


# ── Module 6/7: Public Chatbot ─────────────────────────────────────────────────

class PublicChatbot(Base):
    """A public-facing chatbot owned by a registered user. Completely isolated from private projects."""
    __tablename__ = "public_chatbots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    welcome_message = Column(Text, nullable=False, default="Hello! How can I help you today?")
    is_active = Column(String(10), nullable=False, default="true")  # "true" / "false" (SQLite-safe)
    # Customization fields
    tone = Column(String(50), nullable=False, default="friendly")  # friendly, professional, casual, formal
    default_language = Column(String(10), nullable=False, default="en")
    theme = Column(String(20), nullable=False, default="light")  # light, dark, auto
    position = Column(String(20), nullable=False, default="bottom-right")  # bottom-right, bottom-left
    suggested_questions = Column(JSON, nullable=True)  # list of strings
    avatar_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    owner = relationship("User", backref="public_chatbots")
    knowledge_chunks = relationship("PublicKnowledgeChunk", back_populates="chatbot", cascade="all, delete-orphan")
    visitor_sessions = relationship("PublicVisitorSession", back_populates="chatbot", cascade="all, delete-orphan")


class PublicKnowledgeChunk(Base):
    """Knowledge chunks scoped to a public chatbot. Reuses DocumentService + EmbeddingProvider."""
    __tablename__ = "public_knowledge_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    chatbot_id = Column(String(36), ForeignKey("public_chatbots.id", ondelete="CASCADE"), nullable=False, index=True)
    source_name = Column(String(255), nullable=False, default="Document")
    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    chatbot = relationship("PublicChatbot", back_populates="knowledge_chunks")


class PublicVisitorSession(Base):
    """Anonymous visitor session for a public chatbot. Messages stored as JSON list."""
    __tablename__ = "public_visitor_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    chatbot_id = Column(String(36), ForeignKey("public_chatbots.id", ondelete="CASCADE"), nullable=False, index=True)
    messages = Column(JSON, nullable=False, default=list)  # [{"role": "user"|"assistant", "content": str}]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    chatbot = relationship("PublicChatbot", back_populates="visitor_sessions")


# ── Module 12/13: AI Usage Tracking ───────────────────────────────────────────

class AIUsageRecord(Base):
    """Tracks every AI request for usage analytics and rate-limit accounting."""
    __tablename__ = "ai_usage_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    # Scope — at least one of these will be set
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    chatbot_id = Column(String(36), ForeignKey("public_chatbots.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String(36), nullable=True, index=True)  # public visitor session

    # Request metadata
    request_type = Column(String(50), nullable=False, default="chat")  # chat, pipeline, public_chat
    provider = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)

    # Outcome
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)

    # Usage metrics (nullable — not all providers expose these)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ── Module 14: Feedback ────────────────────────────────────────────────────────

class MessageFeedback(Base):
    """User feedback on an AI response message."""
    __tablename__ = "message_feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(String(36), ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    rating = Column(String(10), nullable=False)  # "positive" | "negative"
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


# ── Module 15: Human Handoff ───────────────────────────────────────────────────

class HandoffRequest(Base):
    """User request for human assistance on a project."""
    __tablename__ = "handoff_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="OPEN")  # OPEN | IN_PROGRESS | RESOLVED | CLOSED
    priority = Column(String(10), nullable=False, default="normal")  # low | normal | high
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

