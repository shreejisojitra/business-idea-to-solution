import json
from unittest.mock import AsyncMock, patch
import pytest

from app.db.models import User, Workspace, Project, Blueprint, ProjectDecision, ProjectMemory
from app.services.ai.chat_service import AIChatService
from app.services.ai.tool_registry import ToolRegistry, ToolAccessDeniedError


def setup_test_project(db, title: str = "Test Placement Assistant", idea: str = "AI placement assistant for college students"):
    user = User(email=f"test_{title.lower().replace(' ', '_').replace(':', '')}@example.com", hashed_password="hashed_pw")
    db.add(user)
    db.commit()

    workspace = Workspace(name="Test Workspace", owner_id=user.id)
    db.add(workspace)
    db.commit()

    project = Project(name=title, workspace_id=workspace.id, business_idea=idea)
    db.add(project)
    db.commit()

    return user, workspace, project


MOCK_STAGE_JSON = {
    "business_analysis": json.dumps({
        "problem": "Meal planning is time-consuming.",
        "pain_points": ["Lack of nutrition knowledge"],
        "goals": ["Automated meal plan"],
        "stakeholders": ["User", "Dietitian"],
        "requirements": ["Calorie tracker"],
        "current_process": ["Manual notes"],
        "gaps": ["No real-time advice"],
        "improvement_opportunities": ["AI suggestions"]
    }),
    "ai_opportunities": json.dumps({
        "opportunities": [{
            "opportunity_name": "AI Meal Planner",
            "ai_capability": "LLM Generation",
            "description": "Custom meal plan generation",
            "expected_benefit": "Instant diet plan",
            "required_data": "User goal & ingredients",
            "complexity": "Low",
            "priority": "High"
        }]
    }),
    "solution_blueprint": json.dumps({
        "recommended_solution": "AI Nutrition Mobile & Web App",
        "system_modules": [{"module_name": "Meal Planner", "description": "Generates weekly plan", "key_features": ["Calorie goal"]}],
        "technology_stack": {"frontend": ["React Native"], "backend": ["FastAPI"], "database": ["PostgreSQL"], "ai_llm": ["OpenAI"], "infrastructure": ["AWS"]},
        "implementation_approach": "Agile Sprints"
    }),
    "architecture": json.dumps({
        "frontend_architecture": "React Native Mobile App",
        "backend_architecture": "FastAPI Microservices",
        "services": [{"name": "Nutrition Service", "type": "Backend API", "responsibility": "Calorie calculation"}],
        "database_architecture": "Relational PostgreSQL",
        "ai_services": "OpenAI Chat Completions API",
        "integrations": ["Fitness Tracker API"],
        "data_flow": ["Mobile App -> FastAPI -> OpenAI API"]
    }),
    "data_api_design": json.dumps({
        "entities": [{"entity_name": "MealPlan", "description": "Weekly meal plans", "fields": [{"name": "id", "type": "UUID", "description": "PK", "is_primary_key": True, "is_required": True}]}],
        "database_schema_sql": "CREATE TABLE meal_plans (id UUID PRIMARY KEY);",
        "rest_apis": [{"method": "POST", "path": "/api/v1/meal-plans", "summary": "Create meal plan"}],
        "integration_requirements": ["JWT authentication"]
    }),
    "ux_design": json.dumps({
        "user_journeys": [{"persona": "Fitness Enthusiast", "steps": ["Enter goal", "Select dietary preference", "View plan"]}],
        "required_screens": [{"screen_name": "Dashboard", "purpose": "Daily macro overview", "key_components": ["Calorie Gauge", "Meal List"]}],
        "ux_recommendations": ["Use clear color-coded macro indicators"]
    }),
    "roadmap": json.dumps({
        "phases": [{"phase_name": "Phase 1: Core Planner", "duration_weeks": 4, "goals": ["Calorie calculator"], "tasks": ["Setup FastAPI", "Build React Native UI"]}],
        "milestones": ["Beta Launch"],
        "effort_estimates": {"total": "6 weeks"},
        "resource_requirements": ["Fullstack Engineer"],
        "overall_strategy": "Iterative release"
    })
}


@pytest.mark.asyncio
async def test_tool_intent_detection(db):
    user, ws, project = setup_test_project(db, "Nutrition App 1", "AI Nutrition Assistant for meal planning")
    chat_service = AIChatService()

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_STAGE_JSON["business_analysis"]

        res = await chat_service.process_chat_message(db, user.id, project.id, "Analyze my business idea.")
        assert res["stage_triggered"] == "business_analysis"
        assert "Business Analysis Completed" in res["message"]

        bp = db.query(Blueprint).filter(Blueprint.project_id == project.id).first()
        assert bp is not None
        assert bp.business_analysis is not None
        assert bp.stage_statuses.get("business_analysis") == "CURRENT"


@pytest.mark.asyncio
async def test_generate_everything_sequential_pipeline(db):
    user, ws, project = setup_test_project(db, "Smart Bicycle Rental", "Smart bicycle rental platform with unlock & payment")
    chat_service = AIChatService()

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = [
            MOCK_STAGE_JSON["business_analysis"],
            MOCK_STAGE_JSON["ai_opportunities"],
            MOCK_STAGE_JSON["solution_blueprint"],
            MOCK_STAGE_JSON["architecture"],
            MOCK_STAGE_JSON["data_api_design"],
            MOCK_STAGE_JSON["ux_design"],
            MOCK_STAGE_JSON["roadmap"]
        ]

        res = await chat_service.process_chat_message(db, user.id, project.id, "Generate everything.")
        assert res["stage_triggered"] == "full_pipeline"
        assert "Complete 7-Stage AI Transformation Engine Executed" in res["message"]

        bp = db.query(Blueprint).filter(Blueprint.project_id == project.id).first()
        assert bp is not None
        assert bp.business_analysis is not None
        assert bp.roadmap is not None
        assert bp.stage_statuses.get("roadmap") == "CURRENT"


@pytest.mark.asyncio
async def test_decision_aware_tool_execution(db):
    user, ws, project = setup_test_project(db, "E-Commerce Store", "Online store platform")

    dec = ProjectDecision(
        project_id=project.id,
        category="database",
        decision="Use MongoDB for store catalog",
        status="accepted"
    )
    db.add(dec)
    db.commit()

    chat_service = AIChatService()

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_STAGE_JSON["data_api_design"]

        res = await chat_service.process_chat_message(db, user.id, project.id, "Design the database and APIs.")
        assert res["stage_triggered"] == "data_api_design"

        bp = db.query(Blueprint).filter(Blueprint.project_id == project.id).first()
        assert bp.data_api_design is not None
        assert bp.stage_statuses.get("data_api_design") == "CURRENT"


@pytest.mark.asyncio
async def test_constraint_aware_roadmap(db):
    user, ws, project = setup_test_project(db, "SaaS CRM", "Lightweight CRM for freelancers")

    mem1 = ProjectMemory(project_id=project.id, category="team", key="team_size", value="2 developers")
    mem2 = ProjectMemory(project_id=project.id, category="timeline", key="timeline", value="6 weeks")
    db.add_all([mem1, mem2])
    db.commit()

    chat_service = AIChatService()

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_STAGE_JSON["roadmap"]

        res = await chat_service.process_chat_message(db, user.id, project.id, "Create the roadmap.")
        assert res["stage_triggered"] == "roadmap"
        bp = db.query(Blueprint).filter(Blueprint.project_id == project.id).first()
        assert bp.roadmap is not None


@pytest.mark.asyncio
async def test_stale_output_detection(db):
    user, ws, project = setup_test_project(db, "Healthcare App", "Patient portal and teleconsultation")
    chat_service = AIChatService()

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_STAGE_JSON["solution_blueprint"]

        await chat_service.process_chat_message(db, user.id, project.id, "Create the solution.")

    bp = db.query(Blueprint).filter(Blueprint.project_id == project.id).first()
    assert bp.solution_blueprint is not None

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Understood. Removing payment from scope."
        await chat_service.process_chat_message(db, user.id, project.id, "Remove payment from the MVP scope.")

    db.refresh(bp)
    assert bp.stage_statuses.get("solution_blueprint") == "STALE"


@pytest.mark.asyncio
async def test_tool_security_isolation(db):
    user1, ws1, proj1 = setup_test_project(db, "Project Security A", "Idea A")
    user2, ws2, proj2 = setup_test_project(db, "Project Security B", "Idea B")

    tool_registry = ToolRegistry()

    with pytest.raises(ToolAccessDeniedError):
        tool_registry.validate_project_access(db, user1.id, proj2.id)
