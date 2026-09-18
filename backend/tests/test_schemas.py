import pytest
from pydantic import ValidationError

from app.services.ai.schemas import BusinessAnalysisResult, BusinessIdeaInput


def test_business_idea_input_valid():
    """Test valid BusinessIdeaInput initialization."""
    inp = BusinessIdeaInput(business_idea="Hospital appointment booking is handled manually via phone calls.")
    assert inp.business_idea == "Hospital appointment booking is handled manually via phone calls."


def test_business_idea_input_trimming():
    """Test whitespace trimming on BusinessIdeaInput."""
    inp = BusinessIdeaInput(business_idea="   Hospital appointment booking is manual.   ")
    assert inp.business_idea == "Hospital appointment booking is manual."


def test_business_idea_input_empty_raises():
    """Test that empty or whitespace-only input raises validation error."""
    with pytest.raises(ValidationError):
        BusinessIdeaInput(business_idea="   ")


def test_business_analysis_result_valid():
    """Test BusinessAnalysisResult schema validation with full payload."""
    data = {
        "problem": "Manual hospital appointment booking",
        "pain_points": ["Long waiting time", "High call volume"],
        "goals": ["Automate booking", "24/7 availability"],
        "stakeholders": ["Patient", "Doctor", "Admin"],
        "requirements": ["Online portal", "SMS alerts"],
        "current_process": ["Patient calls receptionist", "Receptionist checks register"],
        "gaps": ["No self-service option", "No automated reminders"],
        "improvement_opportunities": ["Self-service booking app", "AI conversational bot"]
    }
    result = BusinessAnalysisResult(**data)
    assert result.problem == "Manual hospital appointment booking"
    assert len(result.pain_points) == 2
    assert "Patient" in result.stakeholders
    assert len(result.improvement_opportunities) == 2


def test_business_analysis_result_handles_string_inputs():
    """Test that single string inputs for list fields are gracefully co-erced into lists."""
    data = {
        "problem": "Manual booking",
        "pain_points": "Long waiting time",
        "goals": ["Automate"],
        "stakeholders": ["Patient"],
        "requirements": ["Portal"],
        "current_process": ["Calls"],
        "gaps": ["No app"],
        "improvement_opportunities": ["Online app"]
    }
    result = BusinessAnalysisResult(**data)
    assert result.pain_points == ["Long waiting time"]
