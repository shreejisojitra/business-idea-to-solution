import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.services.ai.business_analysis_service import BusinessAnalysisService, AIAnalysisError
from app.services.ai.schemas import BusinessAnalysisResult, BusinessIdeaInput

logger = logging.getLogger(__name__)

router = APIRouter()
analysis_service = BusinessAnalysisService()


@router.post(
    "/analyze",
    response_model=BusinessAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Analyze Business Idea",
    description="Transforms a raw business idea, problem statement, or process context into a structured business analysis blueprint."
)
async def analyze_business_idea(payload: BusinessIdeaInput) -> BusinessAnalysisResult:
    """
    Endpoint for AI Business Analysis.
    
    Accepts:
        {"business_idea": "Hospital appointment booking is handled manually via phone calls."}
        
    Returns:
        Structured BusinessAnalysisResult JSON with 8 required analysis sections.
    """
    try:
        result = await analysis_service.analyze_business_idea(payload.business_idea)
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except AIAnalysisError as ai_err:
        logger.error(f"AI Business Analysis Error: {str(ai_err)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(ai_err)
        )
    except Exception as exc:
        logger.exception("Unhandled error during AI business analysis")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected internal error occurred: {str(exc)}"
        )
