import json
import logging
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Custom exception raised when an LLM provider request fails."""
    pass


def _safe_provider_error(status_code: int, provider: str) -> LLMProviderError:
    """Return a safe user-facing error without exposing API keys or internal details."""
    if status_code == 401:
        return LLMProviderError(f"{provider} authentication failed. Check your API key configuration.")
    if status_code == 429:
        return LLMProviderError(f"{provider} rate limit reached. Please wait before retrying.")
    if status_code == 404:
        return LLMProviderError(f"{provider} model not found. Check your LLM_MODEL configuration.")
    if status_code >= 500:
        return LLMProviderError(f"{provider} service is temporarily unavailable. Please try again later.")
    return LLMProviderError(f"{provider} returned an unexpected response (HTTP {status_code}).")


class LLMProvider:
    """
    Flexible, provider-agnostic LLM Client wrapper.
    Supports OpenAI, Groq, Gemini, Ollama, and fallback mock generation for testing.
    """

    # Sentinel so callers can explicitly pass api_key=None to mean "no key" (not "use default")
    _UNSET = object()

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key=_UNSET,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout_seconds: Optional[int] = None
    ):
        self.provider = (provider or settings.LLM_PROVIDER).lower()
        self.model = model or settings.LLM_MODEL
        # Only fall back to settings if caller did NOT explicitly pass api_key
        self.api_key = settings.LLM_API_KEY if api_key is LLMProvider._UNSET else api_key
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.timeout_seconds = timeout_seconds or settings.LLM_TIMEOUT_SECONDS

    def _has_valid_key(self) -> bool:
        return bool(
            self.api_key and self.api_key not in ["your_llm_api_key_here", "mock_key_for_testing", ""]
        )

    async def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = True
    ) -> str:
        """
        Generate completion from configured LLM provider.
        For chat prompts (consultant), raises LLMProviderError if provider is unavailable.
        For pipeline stage prompts, falls back to structured mock JSON.
        """
        if not self._has_valid_key() and self.provider != "ollama":
            logger.info("No valid cloud LLM API key — using mock fallback. Provider: %s", self.provider)
            # _generate_mock_fallback raises LLMProviderError for chat prompts
            return self._generate_mock_fallback(system_prompt, user_prompt)

        try:
            if self.provider in ["openai", "groq", "custom"]:
                return await self._call_openai_compatible(system_prompt, user_prompt, json_mode)
            elif self.provider == "gemini":
                return await self._call_gemini(system_prompt, user_prompt, json_mode)
            elif self.provider == "ollama":
                return await self._call_ollama(system_prompt, user_prompt, json_mode)
            else:
                return await self._call_openai_compatible(system_prompt, user_prompt, json_mode)
        except LLMProviderError:
            # Re-raise LLMProviderError so chat_service can show a clean user-facing message
            raise
        except httpx.TimeoutException:
            logger.warning("LLM request timed out (provider=%s, timeout=%ss)", self.provider, self.timeout_seconds)
            raise LLMProviderError(f"AI provider request timed out after {self.timeout_seconds}s. Please try again.")
        except httpx.ConnectError:
            logger.warning("LLM provider unreachable (provider=%s)", self.provider)
            raise LLMProviderError("AI provider is currently unreachable. Please check your network and provider configuration.")
        except Exception as exc:
            logger.warning("Unexpected LLM error (provider=%s): %s", self.provider, type(exc).__name__)
            raise LLMProviderError("An unexpected error occurred while contacting the AI provider. Please try again.")

    async def _call_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool
    ) -> str:
        """Call OpenAI-compatible Chat Completions endpoint."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise _safe_provider_error(response.status_code, self.provider)
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content

    async def _call_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool
    ) -> str:
        """Call Google Gemini REST API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        prompt_text = f"{system_prompt}\n\nUser Input:\n{user_prompt}"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json" if json_mode else "text/plain"
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise _safe_provider_error(response.status_code, "gemini")
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _call_ollama(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool
    ) -> str:
        """Call local Ollama endpoint."""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {"temperature": self.temperature}
        }
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise _safe_provider_error(response.status_code, "ollama")
            data = response.json()
            return data["message"]["content"]

    def _generate_mock_fallback(self, system_prompt: str, user_prompt: str) -> str:
        """Generates structured JSON mock responses for the 7 pipeline stages only (not for chat)."""
        sp = system_prompt.lower()

        # Extract domain context if embedded in prompt
        domain_name = "this solution"
        if "project:" in sp:
            domain_name = sp.split("project:")[1].split("\n")[0].strip()
        elif "business idea:" in sp:
            domain_name = sp.split("business idea:")[1].split("\n")[0].strip()[:40]

        # Chat/conversational prompts must NOT return fake responses — raise so caller shows a real error
        if "consultant" in sp or "conversational" in sp or "qa" in sp:
            raise LLMProviderError(
                "AI provider is not configured. Please set a valid LLM_API_KEY in your environment to use the AI consultant."
            )

        # Stage 1: Business Analysis
        if "stage 1" in sp or "business analysis system" in sp:
            return json.dumps({
                "problem": f"Operational inefficiencies and manual overhead in managing {domain_name}.",
                "pain_points": [
                    f"High time spent manually handling processes for {domain_name}",
                    "Lack of real-time insights and automated recommendation engine",
                    "Scaling constraints due to fragmented user workflows"
                ],
                "goals": [
                    f"Automate core user workflows for {domain_name}",
                    "Improve user satisfaction and operational speed by 80%",
                    "Deliver personalized recommendations and insights"
                ],
                "stakeholders": ["End Users / Customers", "Operations Managers", "System Administrators"],
                "requirements": [
                    "User authentication and profile management",
                    "AI recommendation and analytics service",
                    "REST API integration for mobile and web clients"
                ],
                "current_process": ["Manual data entry", "Static options", "Manual follow-ups"],
                "gaps": ["No automated personalized suggestions", "No real-time analytics"],
                "improvement_opportunities": ["AI-driven recommendation engine", "Automated workflow orchestration"]
            })
        
        # Stage 2: AI Opportunities
        elif "ai strategy" in sp or "ai capabilities" in sp:
            return json.dumps({
                "opportunities": [
                    {
                        "opportunity_name": f"Smart Recommendation Engine for {domain_name}",
                        "ai_capability": "Natural Language Processing & Personalization",
                        "description": f"Analyzes user preferences and goals to deliver tailored recommendations for {domain_name}.",
                        "expected_benefit": "Increases user engagement by 40% and saves 10+ hours per week",
                        "required_data": "User profile data, historic preferences, catalog data",
                        "complexity": "Medium",
                        "priority": "High"
                    },
                    {
                        "opportunity_name": "Predictive Analytics & Intent Recognition",
                        "ai_capability": "Predictive ML / NLP",
                        "description": "Predicts future user needs and intent based on historical interactions.",
                        "expected_benefit": "Proactive service delivery and automated alerts",
                        "required_data": "Interaction logs",
                        "complexity": "Low",
                        "priority": "Medium"
                    }
                ]
            })

        # Stage 3: Solution Blueprint
        elif "enterprise architect" in sp or "solution blueprint" in sp:
            return json.dumps({
                "recommended_solution": f"Intelligent End-to-End Digital Transformation Platform for {domain_name}.",
                "system_modules": [
                    {
                        "module_name": "Core Service & Intake Gateway",
                        "description": "Handles user requests, authentication, and input ingestion.",
                        "key_features": ["User onboarding", "Profile preferences", "Input validation"]
                    },
                    {
                        "module_name": "AI Recommendation & Processing Service",
                        "description": "Processes data through AI algorithms and produces customized results.",
                        "key_features": ["ML model scoring", "Personalization pipeline", "Automated alerts"]
                    },
                    {
                        "module_name": "Management & Analytics Dashboard",
                        "description": "Provides administrators and users with visual insights and metrics.",
                        "key_features": ["Interactive reporting", "Performance metrics", "Export options"]
                    }
                ],
                "technology_stack": {
                    "frontend": ["React", "Vite", "Vanilla CSS"],
                    "backend": ["Python FastAPI", "SQLAlchemy"],
                    "database": ["PostgreSQL"],
                    "ai_llm": ["OpenAI / Gemini / LangChain"],
                    "infrastructure": ["Docker", "Cloud Server"]
                },
                "implementation_approach": "Phased MVP release: Build core intake and PostgreSQL schema first, then integrate AI recommendation pipelines."
            })

        # Stage 4: Architecture
        elif "software architect" in sp or "architecture" in sp:
            return json.dumps({
                "frontend_architecture": "React Vite Single-Page Application with responsive state management.",
                "backend_architecture": "Modular FastAPI microservices architecture.",
                "services": [
                    {"name": "API Gateway", "type": "API Service", "responsibility": "Authentication and request routing"},
                    {"name": "Domain Processing Service", "type": "Microservice", "responsibility": f"Business logic for {domain_name}"},
                    {"name": "AI Engine Service", "type": "AI Engine", "responsibility": "NLP intent recognition and recommendation scoring"}
                ],
                "database_architecture": "Relational PostgreSQL database for users, entities, and logs.",
                "ai_services": "LLM Orchestration Layer connecting prompt builders to AI providers.",
                "integrations": ["Auth Service", "REST API Gateways", "Analytics Pipeline"],
                "data_flow": ["User Request -> Gateway -> Microservice -> AI Engine -> PostgreSQL -> UI Display"]
            })

        # Stage 5: Database & API Design
        elif "database architect" in sp or "database & api" in sp:
            return json.dumps({
                "entities": [
                    {
                        "entity_name": "User",
                        "description": "System user entity",
                        "fields": [
                            {"name": "id", "type": "UUID", "description": "PK", "is_primary_key": True, "is_required": True},
                            {"name": "email", "type": "VARCHAR(255)", "description": "Email address", "is_primary_key": False, "is_required": True},
                            {"name": "full_name", "type": "VARCHAR(255)", "description": "Full name", "is_primary_key": False, "is_required": False}
                        ]
                    },
                    {
                        "entity_name": "ProjectItem",
                        "description": f"Core domain record entity for {domain_name}",
                        "fields": [
                            {"name": "id", "type": "UUID", "description": "PK", "is_primary_key": True, "is_required": True},
                            {"name": "user_id", "type": "UUID", "description": "FK to User", "is_primary_key": False, "is_required": True},
                            {"name": "title", "type": "VARCHAR(255)", "description": "Item title", "is_primary_key": False, "is_required": True},
                            {"name": "status", "type": "VARCHAR(50)", "description": "Current status", "is_primary_key": False, "is_required": True}
                        ]
                    }
                ],
                "database_schema_sql": "CREATE TABLE users (\n  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n  email VARCHAR(255) UNIQUE NOT NULL,\n  full_name VARCHAR(255),\n  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP\n);\n\nCREATE TABLE project_items (\n  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n  user_id UUID REFERENCES users(id) ON DELETE CASCADE,\n  title VARCHAR(255) NOT NULL,\n  status VARCHAR(50) DEFAULT 'ACTIVE',\n  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP\n);",
                "rest_apis": [
                    {"method": "POST", "path": "/api/v1/items", "summary": "Create new record"},
                    {"method": "GET", "path": "/api/v1/items", "summary": "List records for active user"},
                    {"method": "POST", "path": "/api/v1/items/recommend", "summary": "Get AI recommendations"}
                ],
                "integration_requirements": ["OAuth2 / JWT Authorization", "HTTPS TLS 1.3"]
            })

        # Stage 6: UX Recommendations
        elif "ux designer" in sp or "ux recommendations" in sp:
            return json.dumps({
                "user_journeys": [
                    {
                        "persona": "Primary User",
                        "steps": [f"Access {domain_name} Dashboard", "Define Goals/Preferences", "View AI Suggestions", "Take Action"]
                    }
                ],
                "required_screens": [
                    {"screen_name": "Main Dashboard", "purpose": "Overview of active items and goals", "key_components": ["Summary cards", "Action buttons"]},
                    {"screen_name": "Recommendations Screen", "purpose": "Display AI generated personalized options", "key_components": ["Filtered list", "Detail modal"]}
                ],
                "ux_recommendations": [
                    "Clean light-mode layout with high-contrast typography",
                    "Visual indicator for AI confidence scores and recommendations"
                ]
            })

        # Stage 7: Implementation Roadmap
        else:
            return json.dumps({
                "phases": [
                    {
                        "phase_name": "Phase 1: Foundation & Core MVP",
                        "duration_weeks": 3,
                        "goals": [f"Setup database schema and core API for {domain_name}"],
                        "tasks": ["Implement PostgreSQL DDL", "Build FastAPI CRUD endpoints", "Build React UI frontend"]
                    },
                    {
                        "phase_name": "Phase 2: AI Engine Integration & Analytics",
                        "duration_weeks": 3,
                        "goals": ["Integrate recommendation engine and production deployment"],
                        "tasks": ["Connect LLM recommendation pipeline", "Add user preference analytics", "Deploy to cloud server"]
                    }
                ],
                "milestones": ["M1: Core API & DB Working", "M2: AI Recommendations Live"],
                "effort_estimates": {
                    "frontend_weeks": "3 weeks",
                    "backend_weeks": "3 weeks",
                    "total_duration": "6 weeks"
                },
                "resource_requirements": ["1x Fullstack Engineer", "1x AI/ML Lead"],
                "overall_strategy": "Iterative release strategy focusing on core value delivery first."
            })
