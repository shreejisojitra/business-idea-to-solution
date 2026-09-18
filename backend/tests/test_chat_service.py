import pytest
import uuid
from app.db.session import SessionLocal, init_db
from app.db.models import User, Workspace, Project, Blueprint, Conversation, ChatMessage
from app.services.ai.chat_service import AIChatService
from app.services.ai.project_context import build_project_context


@pytest.fixture(scope="module")
def setup_db():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


@pytest.mark.asyncio
async def test_chat_service_and_multi_domain_isolation(setup_db):
    db = setup_db
    email = f"chat_user_{uuid.uuid4().hex[:6]}@example.com"
    user = User(email=email, hashed_password="hashed_secret_pass")
    db.add(user)
    db.commit()

    workspace = Workspace(name="Consultant Workspace", owner_id=user.id)
    db.add(workspace)
    db.commit()

    # Project A: Vendor Invoice Automation
    proj_a = Project(
        name="Invoice Automator",
        workspace_id=workspace.id,
        business_idea="Small businesses waste 15+ hours weekly manually typing paper vendor receipts and invoices into accounting software, leading to data entry errors and late supplier payments."
    )
    db.add(proj_a)

    # Project B: College Faculty Appointment Booking
    proj_b = Project(
        name="College Faculty Booking",
        workspace_id=workspace.id,
        business_idea="A college wants to build a system where students can book appointments with faculty members."
    )
    db.add(proj_b)
    db.commit()

    # Create Blueprint for Project A
    bp_a = Blueprint(
        project_id=proj_a.id,
        business_analysis={"problem": "Manual paper invoice data entry causes processing delays.", "pain_points": ["Data entry errors", "Late supplier payments"], "goals": ["Automate invoice OCR"], "requirements": ["QuickBooks integration"]},
        solution_blueprint={"recommended_solution": "OCR + Document Intelligence + Accounting Sync Engine", "system_modules": [{"module_name": "Invoice Intake", "description": "Drag-and-drop PDF/receipt processing"}]}
    )
    db.add(bp_a)

    # Create Blueprint for Project B
    bp_b = Blueprint(
        project_id=proj_b.id,
        business_analysis={"problem": "Students struggle to find faculty availability for academic advising.", "pain_points": ["Scheduling conflicts", "Long wait times"], "goals": ["Streamline slot booking"], "requirements": ["Calendar sync", "Role RBAC"]},
        solution_blueprint={"recommended_solution": "Faculty Appointment Booking Portal", "system_modules": [{"module_name": "Slot Manager", "description": "Faculty time slot management"}]}
    )
    db.add(bp_b)
    db.commit()

    chat_service = AIChatService()

    # Test Chat on Project A (Invoice Automation)
    res_a1 = await chat_service.process_chat_message(
        db=db,
        user_id=user.id,
        project_id=proj_a.id,
        user_message="What AI can we use?"
    )
    assert res_a1["conversation_id"] is not None
    assert "OCR" in res_a1["message"] or "invoice" in res_a1["message"].lower() or "receipt" in res_a1["message"].lower() or "document" in res_a1["message"].lower()

    # Follow-up question on Project A
    res_a2 = await chat_service.process_chat_message(
        db=db,
        user_id=user.id,
        project_id=proj_a.id,
        user_message="What database should we use?",
        conversation_id=res_a1["conversation_id"]
    )
    assert res_a2["conversation_id"] == res_a1["conversation_id"]
    assert "PostgreSQL" in res_a2["message"] or "database" in res_a2["message"].lower()

    # Test Chat on Project B (College Faculty Booking)
    res_b1 = await chat_service.process_chat_message(
        db=db,
        user_id=user.id,
        project_id=proj_b.id,
        user_message="What database should we use?"
    )
    assert res_b1["conversation_id"] is not None
    assert res_b1["conversation_id"] != res_a1["conversation_id"]
    assert "Faculty" in res_b1["message"] or "Student" in res_b1["message"] or "Booking" in res_b1["message"] or "PostgreSQL" in res_b1["message"]

    # Verify Conversation Messages Persistence in DB
    msgs_a = db.query(ChatMessage).filter(ChatMessage.conversation_id == res_a1["conversation_id"]).all()
    assert len(msgs_a) == 4  # 2 user msgs + 2 assistant msgs


@pytest.mark.asyncio
async def test_ai_nutrition_and_bicycle_isolation(setup_db):
    db = setup_db
    email = f"nutrition_user_{uuid.uuid4().hex[:6]}@example.com"
    user = User(email=email, hashed_password="hashed_secret_pass")
    db.add(user)
    db.commit()

    ws = Workspace(name="Multi Domain Workspace", owner_id=user.id)
    db.add(ws)
    db.commit()

    # Create AI Nutrition project
    proj_nutrition = Project(
        name="AI Nutrition Assistant",
        workspace_id=ws.id,
        business_idea="I want to build an AI nutrition assistant that helps users plan meals based on their goals, dietary preferences and available ingredients."
    )
    db.add(proj_nutrition)

    # Create Smart Bicycle Rental project
    proj_bike = Project(
        name="Smart Bicycle Rental",
        workspace_id=ws.id,
        business_idea="I want to build a smart bicycle rental system for university campuses."
    )
    db.add(proj_bike)
    db.commit()

    chat_service = AIChatService()

    # Query AI Nutrition project
    res_nutr = await chat_service.process_chat_message(
        db=db,
        user_id=user.id,
        project_id=proj_nutrition.id,
        user_message="What AI can we use?"
    )
    msg_nutr = res_nutr["message"]
    # Guarantee response is about nutrition / meal planning / NLP and NOT OCR or invoices
    assert "ocr" not in msg_nutr.lower() or "tesseract" not in msg_nutr.lower()
    assert "invoice" not in msg_nutr.lower()
    assert "textract" not in msg_nutr.lower()

    # Query Smart Bicycle project
    res_bike = await chat_service.process_chat_message(
        db=db,
        user_id=user.id,
        project_id=proj_bike.id,
        user_message="What solution do you recommend?"
    )
    msg_bike = res_bike["message"]
    # Guarantee response is about bicycle / transport / campus / solution and NOT invoices
    assert "invoice" not in msg_bike.lower()
    assert "ocr" not in msg_bike.lower()


@pytest.mark.asyncio
async def test_multilingual_and_initial_state_sync(setup_db):
    db = setup_db
    email = f"multi_lang_{uuid.uuid4().hex[:6]}@example.com"
    user = User(email=email, hashed_password="hashed_secret_pass")
    db.add(user)
    db.commit()

    ws = Workspace(name="Multilingual Workspace", owner_id=user.id)
    db.add(ws)
    db.commit()

    # Create project with initially empty business idea
    proj_empty = Project(
        name="Gujarati AI Nutrition",
        workspace_id=ws.id,
        business_idea=""
    )
    db.add(proj_empty)
    db.commit()

    chat_service = AIChatService()

    # User enters Gujarati prompt as first message
    gujarati_idea = "મારે એવું AI બનાવવું છે જે લોકો માટે personalized meal plan બનાવી શકે."
    res_1 = await chat_service.process_chat_message(
        db=db,
        user_id=user.id,
        project_id=proj_empty.id,
        user_message=gujarati_idea
    )

    # Verify project business_idea was auto-populated in DB
    db.refresh(proj_empty)
    assert proj_empty.business_idea == gujarati_idea

    # Follow up in English
    res_2 = await chat_service.process_chat_message(
        db=db,
        user_id=user.id,
        project_id=proj_empty.id,
        user_message="What database should we use?",
        conversation_id=res_1["conversation_id"]
    )
    assert res_2["conversation_id"] == res_1["conversation_id"]
    assert "PostgreSQL" in res_2["message"] or "database" in res_2["message"].lower()

    # Follow up in Hindi
    res_3 = await chat_service.process_chat_message(
        db=db,
        user_id=user.id,
        project_id=proj_empty.id,
        user_message="अब हिंदी में समझाओ।",
        conversation_id=res_1["conversation_id"]
    )
    assert res_3["conversation_id"] == res_1["conversation_id"]
    # Ensure no OCR or invoice leakage
    assert "ocr" not in res_3["message"].lower()
    assert "invoice" not in res_3["message"].lower()
