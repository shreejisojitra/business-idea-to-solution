import json
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_full_pipeline_end_to_end_hospital_example():
    """Test full 7-stage pipeline generation, storage, editing, and export for Hospital Booking example."""
    uid = uuid.uuid4().hex[:8]
    email = f"pipeline_doc_{uid}@example.com"
    reg_resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "full_name": "Doctor User"}
    )
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get workspace & create project
    ws_id = client.get("/api/workspaces/", headers=headers).json()[0]["id"]
    proj_resp = client.post(
        "/api/projects/",
        headers=headers,
        json={
            "name": "Hospital Booking Transformation",
            "workspace_id": ws_id,
            "business_idea": "Hospital appointment booking is handled manually via phone calls."
        }
    )
    proj_id = proj_resp.json()["id"]

    # Mock stage 1-7 responses
    mock_responses = [
        # Stage 1: Business Analysis
        json.dumps({
            "problem": "Manual hospital appointment booking",
            "pain_points": ["Long waiting time", "Manual effort"],
            "goals": ["Online booking portal"],
            "stakeholders": ["Patient", "Doctor", "Admin"],
            "requirements": ["Appointment management"],
            "current_process": ["Phone call"],
            "gaps": ["No self-service"],
            "improvement_opportunities": ["Online portal", "AI assistant"]
        }),
        # Stage 2: AI Opportunities
        json.dumps({
            "opportunities": [{
                "opportunity_name": "AI Booking Assistant",
                "ai_capability": "Conversational LLM",
                "description": "Smart chatbot for booking",
                "expected_benefit": "24/7 self-service booking",
                "required_data": "Schedule DB",
                "complexity": "Medium",
                "priority": "High"
            }]
        }),
        # Stage 3: Solution Blueprint
        json.dumps({
            "recommended_solution": "Cloud-native Healthcare Booking Platform",
            "system_modules": [{"module_name": "Appointment Module", "description": "Schedules slots", "key_features": ["Slot pick"]}],
            "technology_stack": {"frontend": ["React"], "backend": ["FastAPI"], "database": ["PostgreSQL"], "ai_llm": ["OpenAI"], "infrastructure": ["Docker"]},
            "implementation_approach": "Agile Sprints"
        }),
        # Stage 4: Architecture
        json.dumps({
            "frontend_architecture": "React SPA",
            "backend_architecture": "FastAPI REST API",
            "services": [{"name": "API Service", "type": "Backend API", "responsibility": "Business logic"}],
            "database_architecture": "Relational PostgreSQL",
            "ai_services": "OpenAI Gateway",
            "integrations": ["SMS Notifications"],
            "data_flow": ["Client -> API -> DB"]
        }),
        # Stage 5: Database & API Design
        json.dumps({
            "entities": [{"entity_name": "Appointment", "description": "Booking records", "fields": [{"name": "id", "type": "UUID", "description": "PK", "is_primary_key": True, "is_required": True}]}],
            "database_schema_sql": "CREATE TABLE appointments (id UUID PRIMARY KEY);",
            "rest_apis": [{"method": "POST", "path": "/api/v1/appointments", "summary": "Create booking"}],
            "integration_requirements": ["JWT auth"]
        }),
        # Stage 6: UX Recommendations
        json.dumps({
            "user_journeys": [{"persona": "Patient", "steps": ["Select Doctor", "Pick Time", "Confirm"]}],
            "required_screens": [{"screen_name": "Booking Screen", "purpose": "Schedule appointment", "key_components": ["Calendar", "Time Slot Grid"]}],
            "ux_recommendations": ["Clear availability indicators"]
        }),
        # Stage 7: Roadmap
        json.dumps({
            "phases": [{"phase_name": "Phase 1: MVP", "duration_weeks": 4, "goals": ["Core Booking"], "tasks": ["Setup API", "Build UI"]}],
            "milestones": ["Sprint 1 Release"],
            "effort_estimates": {"total": "8 weeks"},
            "resource_requirements": ["Fullstack Engineer"],
            "overall_strategy": "Iterative delivery"
        })
    ]

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = mock_responses

        # 3. Trigger Full Pipeline Generation
        gen_resp = client.post(
            f"/api/projects/{proj_id}/generate",
            headers=headers,
            json={"business_idea": "Hospital appointment booking is handled manually via phone calls."}
        )
        assert gen_resp.status_code == 200
        bp_data = gen_resp.json()
        assert "business_analysis" in bp_data
        assert "ai_opportunities" in bp_data
        assert "solution_blueprint" in bp_data
        assert "architecture" in bp_data
        assert "data_api_design" in bp_data
        assert "ux_design" in bp_data
        assert "roadmap" in bp_data

    # 4. Fetch saved blueprint via GET
    get_bp_resp = client.get(f"/api/projects/{proj_id}/blueprint", headers=headers)
    assert get_bp_resp.status_code == 200
    assert get_bp_resp.json()["project_id"] == proj_id

    # 5. Export blueprint as Markdown, JSON, and HTML
    md_export = client.get(f"/api/projects/{proj_id}/export?format=markdown", headers=headers)
    assert md_export.status_code == 200
    assert "Business Transformation Blueprint" in md_export.text

    json_export = client.get(f"/api/projects/{proj_id}/export?format=json", headers=headers)
    assert json_export.status_code == 200

    html_export = client.get(f"/api/projects/{proj_id}/export?format=html", headers=headers)
    assert html_export.status_code == 200
    assert "<html>" in html_export.text
