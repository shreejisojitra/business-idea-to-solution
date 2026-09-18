import pytest
from app.services.ai.schemas import ArchitectureResult, ServiceComponent
from app.services.ai.orchestrator import AIOrchestrator


def test_architecture_result_full_valid():
    data = {
        "frontend_architecture": "React Vite Single Page Application",
        "backend_architecture": "FastAPI REST microservices",
        "services": [
            {"name": "Intake API", "type": "API Service", "responsibility": "Upload receipts"}
        ],
        "database_architecture": "PostgreSQL relational DB",
        "ai_services": "OpenAI / Gemini LLM Provider",
        "integrations": ["QuickBooks API", "Xero API"],
        "data_flow": ["Upload -> OCR -> Approve -> Accounting"]
    }
    arch = ArchitectureResult(**data)
    assert arch.frontend_architecture == "React Vite Single Page Application"
    assert len(arch.services) == 1
    assert arch.security is not None
    assert arch.deployment is not None


def test_architecture_result_coercion_and_defaults():
    # Test string list coercion & key normalization
    data = {
        "frontend": ["React SPA", "Glassmorphic Theme"],
        "backend": "FastAPI Async engine",
        "database": "PostgreSQL",
        "ai": "Tesseract OCR & GPT-4o",
        "integrations": "QuickBooks API",
        "data_flow": ["Input -> Output"]
    }
    orchestrator = AIOrchestrator()
    norm = orchestrator._normalize_dict_keys(data)
    arch = ArchitectureResult(**norm)
    assert "React SPA" in arch.frontend_architecture
    assert arch.backend_architecture == "FastAPI Async engine"
    assert arch.database_architecture == "PostgreSQL"
    assert arch.integrations == ["QuickBooks API"]


def test_architecture_result_dict_services_coercion():
    data = {
        "frontend_architecture": "React SPA",
        "backend_architecture": "FastAPI",
        "database_architecture": "PostgreSQL",
        "ai_services": "LLM",
        "services": {"OCR Engine": "Extract text", "Sync Engine": "Push to accounting"}
    }
    arch = ArchitectureResult(**data)
    assert len(arch.services) == 2
    assert arch.services[0].name == "OCR Engine"
    assert arch.services[0].responsibility == "Extract text"
