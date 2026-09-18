import json
import logging
import re
from typing import Any, Dict, Optional

from app.services.ai.prompts import (
    BUSINESS_ANALYSIS_SYSTEM_PROMPT, build_business_analysis_prompt,
    AI_OPPORTUNITIES_SYSTEM_PROMPT, build_ai_opportunities_prompt,
    SOLUTION_BLUEPRINT_SYSTEM_PROMPT, build_solution_blueprint_prompt,
    ARCHITECTURE_SYSTEM_PROMPT, build_architecture_prompt,
    DATA_API_SYSTEM_PROMPT, build_data_api_prompt,
    UX_SYSTEM_PROMPT, build_ux_prompt,
    ROADMAP_SYSTEM_PROMPT, build_roadmap_prompt
)
from app.services.ai.provider import LLMProvider, LLMProviderError
from app.services.ai.schemas import (
    BusinessAnalysisResult, AIOpportunitiesResult, SolutionBlueprintResult,
    ArchitectureResult, DataApiDesignResult, UXDesignResult, RoadmapResult,
    FullTransformationBlueprint
)

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Exception raised when orchestrator fails at any stage."""
    pass


class AIOrchestrator:
    """
    Manages the complete 7-stage AI transformation pipeline.
    Ensures structured context propagation from earlier stages to downstream stages.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or LLMProvider()

    def _clean_json(self, raw_text: str) -> str:
        text = raw_text.strip()
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()
        return text

    def _normalize_dict_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize key variations in LLM JSON output to match Pydantic schema field names."""
        key_alias_map = {
            "frontend": "frontend_architecture",
            "frontend_arch": "frontend_architecture",
            "frontend_architecture_details": "frontend_architecture",
            "backend": "backend_architecture",
            "backend_arch": "backend_architecture",
            "backend_architecture_details": "backend_architecture",
            "database": "database_architecture",
            "database_arch": "database_architecture",
            "db_architecture": "database_architecture",
            "ai": "ai_services",
            "ai_service": "ai_services",
            "ai_architecture": "ai_services",
            "dataflow": "data_flow",
            "data_flows": "data_flow",
            "service_components": "services",
            "microservices": "services",
        }
        normalized = {}
        for k, v in data.items():
            norm_k = key_alias_map.get(str(k).lower(), k)
            normalized[norm_k] = v
        return normalized

    async def _execute_stage(self, system_prompt: str, user_prompt: str, schema_cls: Any) -> Any:
        try:
            raw = await self.provider.generate_completion(system_prompt, user_prompt, json_mode=True)
            cleaned = self._clean_json(raw)
            data = json.loads(cleaned)
            if isinstance(data, dict):
                data = self._normalize_dict_keys(data)
            return schema_cls(**data)
        except OrchestratorError:
            raise
        except json.JSONDecodeError as exc:
            logger.error("Stage %s: JSON parse error", schema_cls.__name__)
            raise OrchestratorError(f"AI stage {schema_cls.__name__} returned malformed output.") from exc
        except Exception as exc:
            logger.error("Stage %s failed: %s", schema_cls.__name__, type(exc).__name__)
            raise OrchestratorError(f"AI stage {schema_cls.__name__} failed. Please try again.") from exc

    async def run_full_pipeline(self, business_idea: str) -> FullTransformationBlueprint:
        """
        Runs the full 7-stage AI transformation pipeline sequentially.
        """
        import time
        pipeline_start = time.monotonic()
        logger.info("Pipeline start: full 7-stage transformation")

        logger.info("Stage 1/7: Business Analysis")
        analysis = await self._execute_stage(
            BUSINESS_ANALYSIS_SYSTEM_PROMPT,
            build_business_analysis_prompt(business_idea),
            BusinessAnalysisResult
        )

        logger.info("Stage 2/7: AI Opportunities")
        analysis_summary = (
            f"Problem: {analysis.problem}\n"
            f"Pain Points: {', '.join(analysis.pain_points)}\n"
            f"Goals: {', '.join(analysis.goals)}\n"
            f"Requirements: {', '.join(analysis.requirements)}"
        )
        ai_opps = await self._execute_stage(
            AI_OPPORTUNITIES_SYSTEM_PROMPT,
            build_ai_opportunities_prompt(analysis_summary),
            AIOpportunitiesResult
        )

        logger.info("Stage 3/7: Solution Blueprint")
        opps_summary = ", ".join([o.opportunity_name for o in ai_opps.opportunities])
        solution_context = f"{analysis_summary}\nAI Opportunities: {opps_summary}"
        solution = await self._execute_stage(
            SOLUTION_BLUEPRINT_SYSTEM_PROMPT,
            build_solution_blueprint_prompt(solution_context),
            SolutionBlueprintResult
        )

        logger.info("Stage 4/7: Architecture")
        arch_context = (
            f"Solution: {solution.recommended_solution}\n"
            f"Modules: {[m.module_name for m in solution.system_modules]}\n"
            f"Tech Stack: {solution.technology_stack.model_dump_json()}"
        )
        architecture = await self._execute_stage(
            ARCHITECTURE_SYSTEM_PROMPT,
            build_architecture_prompt(arch_context),
            ArchitectureResult
        )

        logger.info("Stage 5/7: Database & API Design")
        data_api_context = (
            f"Backend Architecture: {architecture.backend_architecture}\n"
            f"Services: {[s.name for s in architecture.services]}"
        )
        data_api = await self._execute_stage(
            DATA_API_SYSTEM_PROMPT,
            build_data_api_prompt(data_api_context),
            DataApiDesignResult
        )

        logger.info("Stage 6/7: UX Recommendations")
        ux_context = (
            f"System Modules: {[m.module_name for m in solution.system_modules]}\n"
            f"APIs: {[api.path for api in data_api.rest_apis]}"
        )
        ux = await self._execute_stage(
            UX_SYSTEM_PROMPT,
            build_ux_prompt(ux_context),
            UXDesignResult
        )

        logger.info("Stage 7/7: Implementation Roadmap")
        roadmap_context = (
            f"Solution: {solution.recommended_solution}\n"
            f"Modules count: {len(solution.system_modules)}\n"
            f"Entities count: {len(data_api.entities)}\n"
            f"Screens count: {len(ux.required_screens)}"
        )
        roadmap = await self._execute_stage(
            ROADMAP_SYSTEM_PROMPT,
            build_roadmap_prompt(roadmap_context),
            RoadmapResult
        )

        result = FullTransformationBlueprint(
            business_analysis=analysis,
            ai_opportunities=ai_opps,
            solution_blueprint=solution,
            architecture=architecture,
            data_api_design=data_api,
            ux_design=ux,
            roadmap=roadmap
        )
        duration = round((time.monotonic() - pipeline_start) * 1000)
        logger.info("Pipeline complete: 7 stages in %dms", duration)
        return result

    async def regenerate_stage(
        self,
        stage_name: str,
        business_idea: str,
        existing_blueprint: Dict[str, Any]
    ) -> Any:
        """Regenerate a specific single stage using existing blueprint context."""
        stage_map = {
            "business_analysis": (BUSINESS_ANALYSIS_SYSTEM_PROMPT, build_business_analysis_prompt(business_idea), BusinessAnalysisResult),
            "ai_opportunities": (AI_OPPORTUNITIES_SYSTEM_PROMPT, build_ai_opportunities_prompt(business_idea), AIOpportunitiesResult),
            "solution_blueprint": (SOLUTION_BLUEPRINT_SYSTEM_PROMPT, build_solution_blueprint_prompt(business_idea), SolutionBlueprintResult),
            "architecture": (ARCHITECTURE_SYSTEM_PROMPT, build_architecture_prompt(business_idea), ArchitectureResult),
            "data_api_design": (DATA_API_SYSTEM_PROMPT, build_data_api_prompt(business_idea), DataApiDesignResult),
            "ux_design": (UX_SYSTEM_PROMPT, build_ux_prompt(business_idea), UXDesignResult),
            "roadmap": (ROADMAP_SYSTEM_PROMPT, build_roadmap_prompt(business_idea), RoadmapResult),
        }
        if stage_name not in stage_map:
            raise OrchestratorError(f"Invalid stage name: {stage_name}")

        sys_p, usr_p, schema = stage_map[stage_name]
        return await self._execute_stage(sys_p, usr_p, schema)
