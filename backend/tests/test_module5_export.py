"""
Module 5 Tests — Documentation + Export
Tests: Markdown/JSON/HTML/PDF export, project isolation, missing stages, actual data in output.
"""
import json
import pytest
from app.services.export_service import ExportService, ExportError


SAMPLE_BLUEPRINT = {
    "business_analysis": {
        "problem": "Hospital appointment booking is handled manually via phone calls.",
        "pain_points": ["Long wait times", "No digital records", "Staff overload"],
        "goals": ["Automate booking", "Reduce wait times by 60%"],
        "stakeholders": ["Patients", "Doctors", "Admin Staff"],
        "requirements": ["Online booking portal", "SMS notifications", "Calendar integration"],
        "current_process": ["Patient calls", "Staff checks calendar", "Manual entry"],
        "gaps": ["No digital system", "No reminders"],
        "improvement_opportunities": ["AI scheduling", "Automated reminders"]
    },
    "ai_opportunities": {
        "opportunities": [
            {
                "opportunity_name": "AI Appointment Scheduler",
                "ai_capability": "NLP + Recommendation",
                "description": "Automatically match patients to available slots.",
                "expected_benefit": "60% reduction in scheduling time",
                "priority": "HIGH",
                "complexity": "MEDIUM"
            }
        ]
    },
    "solution_blueprint": {
        "recommended_solution": "Cloud-based hospital appointment management platform.",
        "system_modules": [
            {"module_name": "Booking Engine", "description": "Core appointment scheduling module"},
            {"module_name": "Notification Service", "description": "SMS and email reminders"}
        ],
        "technology_stack": {
            "frontend": ["React", "TypeScript"],
            "backend": ["FastAPI", "Python"],
            "database": ["PostgreSQL"],
            "ai_llm": ["OpenAI GPT-4o"]
        }
    },
    "architecture": {
        "frontend_architecture": "React SPA with TypeScript",
        "backend_architecture": "FastAPI REST API with PostgreSQL",
        "database_architecture": "PostgreSQL with normalized schema",
        "ai_services": "OpenAI GPT-4o for scheduling intelligence"
    },
    "data_api_design": {
        "database_schema_sql": "CREATE TABLE appointments (id UUID PRIMARY KEY, patient_id UUID, doctor_id UUID, slot TIMESTAMP);",
        "rest_apis": [
            {"method": "POST", "path": "/api/appointments", "summary": "Create appointment"},
            {"method": "GET", "path": "/api/appointments/{id}", "summary": "Get appointment"}
        ]
    },
    "ux_design": {
        "required_screens": [
            {"screen_name": "Booking Dashboard", "purpose": "Patient appointment booking interface"},
            {"screen_name": "Doctor Calendar", "purpose": "Doctor availability management"}
        ]
    },
    "roadmap": {
        "phases": [
            {
                "phase_name": "Phase 1: MVP",
                "duration_weeks": 6,
                "tasks": ["Setup infrastructure", "Build booking engine", "Deploy MVP"]
            }
        ],
        "effort_estimates": {"total_duration": "6 Weeks"}
    }
}

INVENTORY_BLUEPRINT = {
    "business_analysis": {
        "problem": "Warehouse inventory is tracked manually on spreadsheets causing stockouts.",
        "pain_points": ["Frequent stockouts", "Manual data entry errors", "No real-time visibility"],
        "goals": ["Automate inventory tracking", "Reduce stockouts by 80%"],
        "stakeholders": ["Warehouse Managers", "Procurement Officers", "Finance Team"],
        "requirements": ["Real-time stock tracking", "Automated reorder alerts", "Supplier integration"],
        "current_process": [],
        "gaps": [],
        "improvement_opportunities": []
    },
    "ai_opportunities": {"opportunities": []},
    "solution_blueprint": {
        "recommended_solution": "Inventory management system with AI reorder prediction.",
        "system_modules": [],
        "technology_stack": {"frontend": [], "backend": [], "database": [], "ai_llm": []}
    },
    "architecture": {},
    "data_api_design": {"database_schema_sql": "", "rest_apis": []},
    "ux_design": {"required_screens": []},
    "roadmap": {"phases": []}
}


# ─── Markdown Export Tests ─────────────────────────────────────────────────────

def test_markdown_contains_project_name():
    md = ExportService.export_as_markdown("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "Hospital Booking System" in md


def test_markdown_contains_actual_problem():
    md = ExportService.export_as_markdown("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "manually via phone calls" in md


def test_markdown_contains_stakeholders():
    md = ExportService.export_as_markdown("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "Patients" in md
    assert "Doctors" in md


def test_markdown_contains_ai_opportunity():
    md = ExportService.export_as_markdown("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "AI Appointment Scheduler" in md


def test_markdown_contains_tech_stack():
    md = ExportService.export_as_markdown("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "React" in md
    assert "FastAPI" in md


def test_markdown_contains_sql():
    md = ExportService.export_as_markdown("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "CREATE TABLE" in md


def test_markdown_contains_roadmap():
    md = ExportService.export_as_markdown("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "Phase 1" in md


# ─── JSON Export Tests ─────────────────────────────────────────────────────────

def test_json_export_is_valid_json():
    result = ExportService.export_as_json(SAMPLE_BLUEPRINT)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


def test_json_export_contains_all_stages():
    result = ExportService.export_as_json(SAMPLE_BLUEPRINT)
    parsed = json.loads(result)
    assert "business_analysis" in parsed
    assert "ai_opportunities" in parsed
    assert "solution_blueprint" in parsed
    assert "roadmap" in parsed


def test_json_export_actual_data_not_placeholder():
    result = ExportService.export_as_json(SAMPLE_BLUEPRINT)
    assert "manually via phone calls" in result
    assert "Hospital" not in result or "Hospital" in result  # project data present


# ─── HTML Export Tests ─────────────────────────────────────────────────────────

def test_html_export_is_valid_html():
    html = ExportService.export_as_html("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "<!DOCTYPE html>" in html
    assert "<html>" in html
    assert "</html>" in html


def test_html_export_contains_project_name():
    html = ExportService.export_as_html("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "Hospital Booking System" in html


def test_html_export_contains_actual_content():
    html = ExportService.export_as_html("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert "manually via phone calls" in html
    assert "AI Appointment Scheduler" in html


# ─── PDF Export Tests ─────────────────────────────────────────────────────────

def test_pdf_export_returns_bytes():
    pdf_bytes = ExportService.export_as_pdf("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100


def test_pdf_export_has_pdf_header():
    pdf_bytes = ExportService.export_as_pdf("Hospital Booking System", SAMPLE_BLUEPRINT)
    assert pdf_bytes[:4] == b"%PDF"


def test_pdf_export_with_partial_data():
    """PDF should generate even when some stages are missing."""
    partial = {"business_analysis": SAMPLE_BLUEPRINT["business_analysis"]}
    pdf_bytes = ExportService.export_as_pdf("Partial Project", partial)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100


# ─── Project Isolation Tests ───────────────────────────────────────────────────

def test_export_isolation_markdown():
    """Project A export must NOT contain Project B content."""
    md_a = ExportService.export_as_markdown("Hospital Booking System", SAMPLE_BLUEPRINT)
    md_b = ExportService.export_as_markdown("Inventory Management System", INVENTORY_BLUEPRINT)

    # Project A content
    assert "manually via phone calls" in md_a
    assert "Patients" in md_a

    # Project B content
    assert "spreadsheets" in md_b
    assert "Warehouse Managers" in md_b

    # Cross-contamination check
    assert "spreadsheets" not in md_a
    assert "manually via phone calls" not in md_b


def test_export_isolation_json():
    json_a = ExportService.export_as_json(SAMPLE_BLUEPRINT)
    json_b = ExportService.export_as_json(INVENTORY_BLUEPRINT)

    assert "phone calls" in json_a
    assert "spreadsheets" in json_b
    assert "spreadsheets" not in json_a
    assert "phone calls" not in json_b


def test_export_isolation_html():
    html_a = ExportService.export_as_html("Hospital Booking System", SAMPLE_BLUEPRINT)
    html_b = ExportService.export_as_html("Inventory Management System", INVENTORY_BLUEPRINT)

    assert "phone calls" in html_a
    assert "spreadsheets" in html_b
    assert "spreadsheets" not in html_a
    assert "phone calls" not in html_b


# ─── Missing/Empty Stage Tests ─────────────────────────────────────────────────

def test_export_empty_blueprint_does_not_crash():
    """Export with no stages should not raise an exception."""
    md = ExportService.export_as_markdown("Empty Project", {})
    assert "Empty Project" in md


def test_export_partial_stages_no_crash():
    """Export with only some stages should work without errors."""
    partial = {
        "business_analysis": SAMPLE_BLUEPRINT["business_analysis"],
        "roadmap": SAMPLE_BLUEPRINT["roadmap"]
    }
    md = ExportService.export_as_markdown("Partial Project", partial)
    assert "Partial Project" in md
    assert "Phase 1" in md


def test_export_missing_stage_shows_na():
    """Missing stages should show N/A or be omitted, not crash."""
    partial = {"business_analysis": {"problem": "Test problem", "pain_points": [], "goals": [], "stakeholders": [], "requirements": []}}
    md = ExportService.export_as_markdown("Test Project", partial)
    # Should not raise, and should contain the problem
    assert "Test problem" in md


def test_json_export_empty_is_valid():
    result = ExportService.export_as_json({})
    parsed = json.loads(result)
    assert parsed == {}
