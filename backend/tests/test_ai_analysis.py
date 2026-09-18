import json
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai.business_analysis_service import BusinessAnalysisService, AIAnalysisError
from app.services.ai.provider import LLMProviderError

client = TestClient(app)


def test_health_check():
    """Test healthcheck endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "llm_provider" in data


@pytest.mark.asyncio
async def test_analyze_business_idea_success():
    """Test successful business analysis via endpoint with mocked LLM provider."""
    mock_llm_output = json.dumps({
        "problem": "Manual hospital appointment booking via phone calls.",
        "pain_points": [
            "Long waiting time",
            "High receptionist workload",
            "Human scheduling errors"
        ],
        "goals": [
            "Enable online self-service booking",
            "Reduce appointment processing time"
        ],
        "stakeholders": [
            "Patients",
            "Doctors",
            "Hospital Administrators"
        ],
        "requirements": [
            "Patient portal for scheduling",
            "Doctor schedule management",
            "Automated confirmation notifications"
        ],
        "current_process": [
            "Patient dials hospital phone line",
            "Receptionist checks manual register",
            "Booking is recorded manually"
        ],
        "gaps": [
            "No after-hours booking",
            "No automated reminders"
        ],
        "improvement_opportunities": [
            "24/7 web & mobile appointment booking app",
            "AI conversational assistant for booking queries"
        ]
    })

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = mock_llm_output

        response = client.post(
            "/api/ai/analyze",
            json={"business_idea": "Hospital appointment booking is handled manually via phone calls."}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["problem"] == "Manual hospital appointment booking via phone calls."
        assert len(data["pain_points"]) == 3
        assert len(data["goals"]) == 2
        assert len(data["stakeholders"]) == 3
        assert len(data["requirements"]) == 3
        assert len(data["current_process"]) == 3
        assert len(data["gaps"]) == 2
        assert len(data["improvement_opportunities"]) == 2


@pytest.mark.asyncio
async def test_analyze_business_idea_markdown_wrapped_json():
    """Test handling of LLM response wrapped in markdown code blocks."""
    raw_markdown_output = """```json
{
  "problem": "Manual appointment booking",
  "pain_points": ["Long waits"],
  "goals": ["Automate"],
  "stakeholders": ["Patients"],
  "requirements": ["Portal"],
  "current_process": ["Phone call"],
  "gaps": ["No digital system"],
  "improvement_opportunities": ["Web portal"]
}
```"""

    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = raw_markdown_output

        response = client.post(
            "/api/ai/analyze",
            json={"business_idea": "Hospital appointment booking is handled manually via phone calls."}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["problem"] == "Manual appointment booking"


def test_analyze_business_idea_empty_input():
    """Test validation error for empty business idea input."""
    response = client.post(
        "/api/ai/analyze",
        json={"business_idea": "   "}
    )
    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_analyze_business_idea_provider_error():
    """Test handling when LLM Provider fails or API key is missing."""
    with patch("app.services.ai.provider.LLMProvider.generate_completion", new_callable=AsyncMock) as mock_generate:
        mock_generate.side_effect = LLMProviderError("LLM API Key is not configured")

        response = client.post(
            "/api/ai/analyze",
            json={"business_idea": "Hospital appointment booking is handled manually via phone calls."}
        )

        assert response.status_code == 502
        data = response.json()
        assert "LLM API Key is not configured" in data["detail"]
