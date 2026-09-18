import json
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def get_mock_pipeline_responses(domain_title: str):
    return [
        # Stage 1
        json.dumps({
            "problem": f"Problem description for {domain_title}",
            "pain_points": ["Inconsistent access", "High delay"],
            "goals": ["Digital transformation", "Automation"],
            "stakeholders": ["End User", "Administrator"],
            "requirements": ["Scalable platform", "Mobile friendly"],
            "current_process": ["Manual paperwork/phone calls"],
            "gaps": ["Lack of real-time status"],
            "improvement_opportunities": ["Self-service web app", "AI chatbot"]
        }),
        # Stage 2
        json.dumps({
            "opportunities": [{
                "opportunity_name": f"AI Assistant for {domain_title}",
                "ai_capability": "LLM Conversational Agent",
                "description": "Smart assistant for guidance",
                "expected_benefit": "80% reduction in response time",
                "required_data": "Knowledge base",
                "complexity": "Medium",
                "priority": "High"
            }]
        }),
        # Stage 3
        json.dumps({
            "recommended_solution": f"AI-Powered Solution for {domain_title}",
            "system_modules": [{"module_name": "Core Engine", "description": "Processing engine", "key_features": ["Rule validation"]}],
            "technology_stack": {"frontend": ["React", "Vite"], "backend": ["FastAPI"], "database": ["PostgreSQL"], "ai_llm": ["OpenAI"], "infrastructure": ["Docker"]},
            "implementation_approach": "Phased rollout"
        }),
        # Stage 4
        json.dumps({
            "frontend_architecture": "React Vite Single Page App",
            "backend_architecture": "FastAPI Microservices / REST API",
            "services": [{"name": "Core Service", "type": "API Service", "responsibility": "Main business logic"}],
            "database_architecture": "PostgreSQL Database",
            "ai_services": "Orchestrator Gateway",
            "integrations": ["SMS/Email gateway"],
            "data_flow": ["UI -> FastAPI -> DB"]
        }),
        # Stage 5
        json.dumps({
            "entities": [{"entity_name": "UserRequest", "description": "Requests entity", "fields": [{"name": "id", "type": "UUID", "description": "PK", "is_primary_key": True, "is_required": True}]}],
            "database_schema_sql": "CREATE TABLE user_requests (id UUID PRIMARY KEY);",
            "rest_apis": [{"method": "POST", "path": "/api/v1/requests", "summary": "Submit request"}],
            "integration_requirements": ["OAuth2/JWT"]
        }),
        # Stage 6
        json.dumps({
            "user_journeys": [{"persona": "Citizen / Patient", "steps": ["Landing", "Input data", "View recommendations"]}],
            "required_screens": [{"screen_name": "Main Dashboard", "purpose": "Overview screen", "key_components": ["Search bar", "Results card"]}],
            "ux_recommendations": ["Accessible font size", "High contrast mode"]
        }),
        # Stage 7
        json.dumps({
            "phases": [{"phase_name": "Phase 1: Foundation", "duration_weeks": 4, "goals": ["Core release"], "tasks": ["Database setup", "API implementation"]}],
            "milestones": ["MVP Launch"],
            "effort_estimates": {"total_duration": "6 weeks"},
            "resource_requirements": ["Frontend Dev", "Backend Dev"],
            "overall_strategy": "Incremental updates"
        })
    ]


@pytest.mark.asyncio
async def test_hospital_booking_case():
    """Verify 7-stage pipeline for Case 1: Hospital appointment booking."""
    uid = uuid.uuid4().hex[:8]
    email = f"hosp_test_{uid}@example.com"
    reg_resp = client.post("/api/auth/register", json={"email": email, "password": "Password123!"})
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    ws_id = client.get("/api/workspaces/", headers=headers).json()[0]["id"]

    proj_resp = client.post(
        "/api/projects/",
        headers=headers,
        json={"name": "Hospital Booking System", "workspace_id": ws_id}
    )
    proj_id = proj_resp.json()["id"]

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = get_mock_pipeline_responses("Hospital Appointment Booking")
        res = client.post(
            f"/api/projects/{proj_id}/generate",
            headers=headers,
            json={"business_idea": "Hospital appointment booking is handled manually via phone calls."}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["business_analysis"]["problem"] == "Problem description for Hospital Appointment Booking"


@pytest.mark.asyncio
async def test_farmers_schemes_case():
    """Verify 7-stage pipeline for Case 2: Farmers government schemes eligibility."""
    uid = uuid.uuid4().hex[:8]
    email = f"farmer_test_{uid}@example.com"
    reg_resp = client.post("/api/auth/register", json={"email": email, "password": "Password123!"})
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    ws_id = client.get("/api/workspaces/", headers=headers).json()[0]["id"]

    proj_resp = client.post(
        "/api/projects/",
        headers=headers,
        json={"name": "Farmers Scheme Portal", "workspace_id": ws_id}
    )
    proj_id = proj_resp.json()["id"]

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = get_mock_pipeline_responses("Farmers Government Schemes")
        res = client.post(
            f"/api/projects/{proj_id}/generate",
            headers=headers,
            json={"business_idea": "Farmers have difficulty finding government schemes and determining their eligibility."}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["business_analysis"]["problem"] == "Problem description for Farmers Government Schemes"
