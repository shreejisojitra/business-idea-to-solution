import json
import logging
import re
from typing import Any, Dict, Optional

from app.services.ai.prompts import BUSINESS_ANALYSIS_SYSTEM_PROMPT, build_business_analysis_prompt
from app.services.ai.provider import LLMProvider, LLMProviderError
from app.services.ai.schemas import BusinessAnalysisResult

logger = logging.getLogger(__name__)


class AIAnalysisError(Exception):
    """Custom exception raised when business analysis generation or parsing fails."""
    pass


class BusinessAnalysisService:
    """
    Core AI engine for business analysis.
    Transforms raw business idea / problem input into structured BusinessAnalysisResult.
    """

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or LLMProvider()

    def _clean_json_response(self, raw_text: str) -> str:
        """
        Clean LLM response string to extract pure JSON content.
        Strips markdown code blocks like ```json ... ``` and surrounding whitespace.
        """
        text = raw_text.strip()
        
        # Strip markdown code blocks if present
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            text = match.group(1).strip()
            
        return text

    def _normalize_keys(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize dictionary keys (handling camelCase or alternative spellings from LLM outputs).
        """
        key_map = {
            "painpoints": "pain_points",
            "painPoints": "pain_points",
            "currentProcess": "current_process",
            "improvementOpportunities": "improvement_opportunities",
            "improvement_opportunity": "improvement_opportunities",
            "opportunity": "improvement_opportunities",
            "opportunities": "improvement_opportunities"
        }
        
        normalized = {}
        for k, v in data.items():
            mapped_key = key_map.get(k, k)
            normalized[mapped_key] = v
            
        return normalized

    async def analyze_business_idea(self, business_idea: str) -> BusinessAnalysisResult:
        """
        Perform AI business analysis on a business idea/problem statement.
        
        Returns:
            BusinessAnalysisResult Pydantic model with 8 required fields.
        Raises:
            AIAnalysisError if processing fails or LLM output cannot be parsed into valid schema.
        """
        cleaned_input = business_idea.strip()
        if not cleaned_input:
            raise AIAnalysisError("Business idea input cannot be empty.")

        system_prompt = BUSINESS_ANALYSIS_SYSTEM_PROMPT
        user_prompt = build_business_analysis_prompt(cleaned_input)

        try:
            logger.info("Sending business idea to LLM provider...")
            raw_response = await self.provider.generate_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True
            )
        except LLMProviderError as exc:
            logger.error(f"LLM Provider execution error: {str(exc)}")
            raise AIAnalysisError(f"AI Provider error: {str(exc)}") from exc
        except Exception as exc:
            logger.error(f"Unexpected error calling LLM provider: {str(exc)}")
            raise AIAnalysisError(f"Failed to communicate with AI provider: {str(exc)}") from exc

        # Clean JSON response
        cleaned_json_str = self._clean_json_response(raw_response)

        try:
            parsed_dict = json.loads(cleaned_json_str)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse LLM output as JSON. Output was: {raw_response}")
            raise AIAnalysisError(
                f"AI generated malformed non-JSON output. Raw response: {raw_response[:200]}..."
            ) from exc

        if not isinstance(parsed_dict, dict):
            raise AIAnalysisError("AI output must be a JSON object.")

        # Normalize any camelCase keys
        normalized_dict = self._normalize_keys(parsed_dict)

        # Validate against Pydantic schema
        try:
            result = BusinessAnalysisResult(**normalized_dict)
            return result
        except Exception as exc:
            logger.error(f"Schema validation failed for LLM output: {str(exc)}")
            raise AIAnalysisError(
                f"AI response did not match required business analysis schema: {str(exc)}"
            ) from exc
