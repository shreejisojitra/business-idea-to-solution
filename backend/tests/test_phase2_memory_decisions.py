import pytest
import uuid
from app.db.session import SessionLocal, init_db
from app.db.models import User, Workspace, Project, Conversation, ChatMessage, ProjectMemory, ProjectDecision, ConversationSummary
from app.services.ai.chat_service import AIChatService
from app.services.ai.memory_service import MemoryService, contains_secret
from app.services.ai.project_context import build_project_context, format_project_context_summary



@pytest.fixture(scope="module")
def setup_db():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def setup_phase2_project(setup_db):
    db = setup_db
    user = User(email=f"phase2_user_{uuid.uuid4().hex[:6]}@example.com", hashed_password="hashed_secret_pass")
    db.add(user)
    db.commit()

    ws = Workspace(name="Phase 2 Workspace", owner_id=user.id)
    db.add(ws)
    db.commit()

    proj = Project(workspace_id=ws.id, name="AI College Placement Assistant", business_idea="AI college placement assistant for general users.")
    db.add(proj)
    db.commit()
    return ws, proj



def test_secret_filtering():
    assert contains_secret("My API key is sk-1234567890abcdef") is True
    assert contains_secret("Here is my secret password123") is True
    assert contains_secret("Let's use PostgreSQL for our database.") is False


@pytest.mark.asyncio
async def test_memory_extraction_and_decision_superseding(setup_db, setup_phase2_project):
    db = setup_db
    ws, proj = setup_phase2_project
    chat_service = AIChatService()


    # 1. Fact Extraction: Team size & target users
    await chat_service.process_chat_message(db, "user-1", proj.id, "Target users are college students.")
    await chat_service.process_chat_message(db, "user-1", proj.id, "I have 2 developers.")

    memories = db.query(ProjectMemory).filter(ProjectMemory.project_id == proj.id).all()
    mem_map = {m.key: m.value for m in memories}
    assert mem_map.get("target_users") == "College Students"
    assert mem_map.get("team_size") == "2 developers"

    # 2. Initial Decision: PostgreSQL
    await chat_service.process_chat_message(db, "user-1", proj.id, "Let's use PostgreSQL.")

    active_dec = db.query(ProjectDecision).filter(
        ProjectDecision.project_id == proj.id,
        ProjectDecision.category == "database",
        ProjectDecision.status == "accepted"
    ).first()
    assert active_dec is not None
    assert active_dec.decision == "PostgreSQL"

    # 3. Decision Superseding: MongoDB replaces PostgreSQL
    await chat_service.process_chat_message(db, "user-1", proj.id, "Actually MongoDB may be better.")

    all_decs = db.query(ProjectDecision).filter(ProjectDecision.project_id == proj.id, ProjectDecision.category == "database").all()
    assert len(all_decs) == 2

    statuses = {d.decision: d.status for d in all_decs}
    assert statuses.get("PostgreSQL") == "superseded"
    assert statuses.get("MongoDB") == "accepted"


@pytest.mark.asyncio
async def test_user_correction_and_forget_commands(setup_db, setup_phase2_project):
    db = setup_db
    ws, proj = setup_phase2_project
    chat_service = AIChatService()

    await chat_service.process_chat_message(db, "user-1", proj.id, "Let's use PostgreSQL.")
    await chat_service.process_chat_message(db, "user-1", proj.id, "Forget database decision.")

    active_dec = db.query(ProjectDecision).filter(
        ProjectDecision.project_id == proj.id,
        ProjectDecision.category == "database",
        ProjectDecision.status == "accepted"
    ).first()
    assert active_dec is None


@pytest.mark.asyncio
async def test_multi_conversation_memory_persistence(setup_db, setup_phase2_project):
    db = setup_db
    ws, proj = setup_phase2_project
    chat_service = AIChatService()

    # Conversation 1: Make decisions
    res1 = await chat_service.process_chat_message(db, "user-1", proj.id, "I want to build an AI placement assistant.")
    conv1_id = res1["conversation_id"]
    await chat_service.process_chat_message(db, "user-1", proj.id, "Let's use MongoDB.", conversation_id=conv1_id)

    # Conversation 2: Create brand new conversation in SAME project
    res2 = await chat_service.process_chat_message(db, "user-1", proj.id, "What database did we choose?")
    conv2_id = res2["conversation_id"]
    assert conv2_id != conv1_id

    ctx = build_project_context(db, proj.id, conv2_id)
    summary_prompt = format_project_context_summary(ctx)

    assert "ACTIVE ACCEPTED PROJECT DECISIONS" in summary_prompt
    assert "MongoDB" in summary_prompt


@pytest.mark.asyncio
async def test_cross_project_memory_isolation(setup_db, setup_phase2_project):
    db = setup_db
    ws, proj_a = setup_phase2_project

    proj_b = Project(workspace_id=ws.id, name="Smart Bicycle Rental", business_idea="Smart bicycle rental platform")
    db.add(proj_b)
    db.commit()

    chat_service = AIChatService()

    # Project A -> PostgreSQL decision
    await chat_service.process_chat_message(db, "user-1", proj_a.id, "Let's use PostgreSQL.")

    # Project B -> MongoDB decision
    await chat_service.process_chat_message(db, "user-1", proj_b.id, "Let's use MongoDB.")

    ctx_a = build_project_context(db, proj_a.id)
    ctx_b = build_project_context(db, proj_b.id)

    decs_a = [d["decision"] for d in ctx_a.get("decisions", [])]
    decs_b = [d["decision"] for d in ctx_b.get("decisions", [])]

    assert "PostgreSQL" in decs_a
    assert "MongoDB" not in decs_a

    assert "MongoDB" in decs_b
    assert "PostgreSQL" not in decs_b


@pytest.mark.asyncio
async def test_long_conversation_summarization(setup_db, setup_phase2_project):
    db = setup_db
    ws, proj = setup_phase2_project
    chat_service = AIChatService()

    res = await chat_service.process_chat_message(db, "user-1", proj.id, "Initial message")
    conv_id = res["conversation_id"]

    # Send 10 messages to trigger summarization
    for i in range(10):
        await chat_service.process_chat_message(db, "user-1", proj.id, f"Turn {i+1} message content.", conversation_id=conv_id)

    summary_rec = db.query(ConversationSummary).filter(ConversationSummary.conversation_id == conv_id).first()
    assert summary_rec is not None
    assert "Conversation Summary" in summary_rec.summary

