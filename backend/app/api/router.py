from fastapi import APIRouter
from app.api.v1.endpoints import ai_analysis, auth, workspaces, projects, ai_pipeline, export, ai_chat, memory_endpoints, knowledge, public_chatbot, analytics, feedback, handoff

api_router = APIRouter()

# Knowledge Base & RAG routes
api_router.include_router(knowledge.router, prefix="/v1", tags=["Knowledge Base & RAG"])
api_router.include_router(knowledge.router, prefix="", tags=["Knowledge Base & RAG"])


# Authentication routes
api_router.include_router(auth.router, prefix="/v1/auth", tags=["Auth"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Workspace routes
api_router.include_router(workspaces.router, prefix="/v1/workspaces", tags=["Workspaces"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])

# Project routes
api_router.include_router(projects.router, prefix="/v1/projects", tags=["Projects"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])

# Project Memory & Decisions routes
api_router.include_router(memory_endpoints.router, prefix="/v1", tags=["Project Memory & Decisions"])
api_router.include_router(memory_endpoints.router, prefix="", tags=["Project Memory & Decisions"])

# AI Chat Consultant routes (/api/ai/chat & /api/v1/ai/chat)
api_router.include_router(ai_chat.router, prefix="/v1/ai", tags=["AI Chat Consultant"])
api_router.include_router(ai_chat.router, prefix="/ai", tags=["AI Chat Consultant"])

# AI Pipeline routes
api_router.include_router(ai_pipeline.router, prefix="/v1", tags=["AI Pipeline"])
api_router.include_router(ai_pipeline.router, prefix="", tags=["AI Pipeline"])

# Export routes
api_router.include_router(export.router, prefix="/v1", tags=["Export"])
api_router.include_router(export.router, prefix="", tags=["Export"])

# Legacy single-stage Task 1 AI endpoint
api_router.include_router(ai_analysis.router, prefix="/v1/ai", tags=["AI Analysis"])
api_router.include_router(ai_analysis.router, prefix="/ai", tags=["AI Analysis"])

# Public Chatbot routes (Module 6+7)
api_router.include_router(public_chatbot.router, prefix="/v1", tags=["Public Chatbot"])
api_router.include_router(public_chatbot.router, prefix="", tags=["Public Chatbot"])

# Analytics routes (Module 13)
api_router.include_router(analytics.router, prefix="/v1", tags=["Analytics"])
api_router.include_router(analytics.router, prefix="", tags=["Analytics"])

# Feedback routes (Module 14)
api_router.include_router(feedback.router, prefix="/v1", tags=["Feedback"])
api_router.include_router(feedback.router, prefix="", tags=["Feedback"])

# Handoff routes (Module 15)
api_router.include_router(handoff.router, prefix="/v1", tags=["Handoff"])
api_router.include_router(handoff.router, prefix="", tags=["Handoff"])

