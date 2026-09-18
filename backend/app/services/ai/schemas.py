from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------
# 1. Business Analysis Schema
# ---------------------------------------------------------
class BusinessIdeaInput(BaseModel):
    """Input payload for business analysis."""
    business_idea: str = Field(
        ...,
        description="Raw business idea, problem statement, or domain context to analyze.",
        min_length=5,
        examples=["Hospital appointment booking is handled manually via phone calls."]
    )

    @field_validator("business_idea")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Business idea input cannot be empty or contain only whitespace.")
        return trimmed


class BusinessAnalysisResult(BaseModel):
    """Structured response model representing full business analysis."""
    problem: str = Field(..., description="Core business problem or main challenge.")
    pain_points: List[str] = Field(default_factory=list, description="Key difficulties or friction.")
    goals: List[str] = Field(default_factory=list, description="Desired future solution targets.")
    stakeholders: List[str] = Field(default_factory=list, description="Affected user roles or entities.")
    requirements: List[str] = Field(default_factory=list, description="Derived functional requirements.")
    current_process: List[str] = Field(default_factory=list, description="Existing workflow steps.")
    gaps: List[str] = Field(default_factory=list, description="Missing capabilities or vulnerabilities.")
    improvement_opportunities: List[str] = Field(default_factory=list, description="Strategic transformation opportunities.")

    @field_validator("pain_points", "goals", "stakeholders", "requirements", "current_process", "gaps", "improvement_opportunities", mode="before")
    @classmethod
    def coerce_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [value.strip()]
        return value


# ---------------------------------------------------------
# 2. AI Opportunities Schema
# ---------------------------------------------------------
class AIOpportunityItem(BaseModel):
    opportunity_name: str = Field(..., description="Name of the AI opportunity")
    ai_capability: str = Field(..., description="LLM, NLP, Computer Vision, Predictive Analytics, etc.")
    description: str = Field(..., description="How AI is applied")
    expected_benefit: str = Field(..., description="Quantifiable benefit or ROI")
    required_data: str = Field(..., description="Data required to power AI feature")
    complexity: str = Field("Medium", description="Low, Medium, High")
    priority: str = Field("High", description="High, Medium, Low")


class AIOpportunitiesResult(BaseModel):
    opportunities: List[AIOpportunityItem] = Field(default_factory=list)


# ---------------------------------------------------------
# 3. Solution Blueprint Schema
# ---------------------------------------------------------
class ModuleItem(BaseModel):
    module_name: str
    description: str
    key_features: List[str] = Field(default_factory=list)


class TechStack(BaseModel):
    frontend: List[str] = Field(default_factory=list)
    backend: List[str] = Field(default_factory=list)
    database: List[str] = Field(default_factory=list)
    ai_llm: List[str] = Field(default_factory=list)
    infrastructure: List[str] = Field(default_factory=list)


class SolutionBlueprintResult(BaseModel):
    recommended_solution: str
    system_modules: List[ModuleItem] = Field(default_factory=list)
    technology_stack: TechStack
    implementation_approach: str


# ---------------------------------------------------------
# 4. Architecture Schema
# ---------------------------------------------------------
class ServiceComponent(BaseModel):
    name: str
    type: str  # Frontend, API Service, Microservice, DB, AI Engine
    responsibility: str


class ArchitectureResult(BaseModel):
    frontend_architecture: str = Field(default="React SPA with glassmorphic UI and modular state management.")
    backend_architecture: str = Field(default="FastAPI REST API layer adhering to clean modular service architecture.")
    services: List[ServiceComponent] = Field(default_factory=list)
    database_architecture: str = Field(default="Relational PostgreSQL database for persistent storage.")
    ai_services: str = Field(default="Multi-provider LLM Client supporting sequential prompt pipelines.")
    integrations: List[str] = Field(default_factory=list)
    data_flow: List[str] = Field(default_factory=list)
    security: Optional[str] = Field(default="TLS 1.3 encryption, OAuth2 / JWT authentication, role-based access control, and audited data storage.")
    deployment: Optional[str] = Field(default="Containerized deployment via Docker with Uvicorn and Nginx reverse proxy.")
    architecture_summary: Optional[str] = Field(default="Scalable modular microservice architecture.")

    @field_validator(
        "frontend_architecture",
        "backend_architecture",
        "database_architecture",
        "ai_services",
        "security",
        "deployment",
        "architecture_summary",
        mode="before"
    )
    @classmethod
    def coerce_str_value(cls, v: Any) -> str:
        if isinstance(v, list):
            return " ".join([str(item) for item in v])
        if isinstance(v, dict):
            return json.dumps(v)
        return str(v) if v is not None else ""

    @field_validator("integrations", "data_flow", mode="before")
    @classmethod
    def coerce_list_value(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [v.strip()]
        if isinstance(v, dict):
            return [f"{k}: {val}" for k, val in v.items()]
        return v if isinstance(v, list) else []

    @field_validator("services", mode="before")
    @classmethod
    def coerce_services_value(cls, v: Any) -> List[Any]:
        if isinstance(v, str):
            return [{"name": "Core Service", "type": "API Service", "responsibility": v}]
        if isinstance(v, dict):
            return [{"name": k, "type": "Microservice", "responsibility": str(val)} for k, val in v.items()]
        return v if isinstance(v, list) else []


# ---------------------------------------------------------
# 5. Database & API Design Schema
# ---------------------------------------------------------
class EntityField(BaseModel):
    name: str
    type: str
    description: str
    is_primary_key: bool = False
    is_required: bool = True


class EntityItem(BaseModel):
    entity_name: str
    description: str
    fields: List[EntityField] = Field(default_factory=list)


class APIEndpointItem(BaseModel):
    method: str  # GET, POST, PUT, DELETE
    path: str
    summary: str
    request_body: Optional[str] = None
    response_body: Optional[str] = None


class DataApiDesignResult(BaseModel):
    entities: List[EntityItem] = Field(default_factory=list)
    database_schema_sql: str
    rest_apis: List[APIEndpointItem] = Field(default_factory=list)
    integration_requirements: List[str] = Field(default_factory=list)


# ---------------------------------------------------------
# 6. UX Recommendations Schema
# ---------------------------------------------------------
class UserJourney(BaseModel):
    persona: str
    steps: List[str] = Field(default_factory=list)


class ScreenItem(BaseModel):
    screen_name: str
    purpose: str
    key_components: List[str] = Field(default_factory=list)


class UXDesignResult(BaseModel):
    user_journeys: List[UserJourney] = Field(default_factory=list)
    required_screens: List[ScreenItem] = Field(default_factory=list)
    ux_recommendations: List[str] = Field(default_factory=list)


# ---------------------------------------------------------
# 7. Implementation Roadmap Schema
# ---------------------------------------------------------
class RoadmapPhase(BaseModel):
    phase_name: str
    duration_weeks: int
    goals: List[str] = Field(default_factory=list)
    tasks: List[str] = Field(default_factory=list)


class RoadmapResult(BaseModel):
    phases: List[RoadmapPhase] = Field(default_factory=list)
    milestones: List[str] = Field(default_factory=list)
    effort_estimates: Dict[str, str] = Field(default_factory=dict)
    resource_requirements: List[str] = Field(default_factory=list)
    overall_strategy: str


# ---------------------------------------------------------
# Complete Full Transformation Blueprint Wrapper
# ---------------------------------------------------------
class FullTransformationBlueprint(BaseModel):
    business_analysis: BusinessAnalysisResult
    ai_opportunities: AIOpportunitiesResult
    solution_blueprint: SolutionBlueprintResult
    architecture: ArchitectureResult
    data_api_design: DataApiDesignResult
    ux_design: UXDesignResult
    roadmap: RoadmapResult
