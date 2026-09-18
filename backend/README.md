# Business Transformation AI — Backend Service

FastAPI backend and AI Core engine for Business Transformation AI.

## Features & Task 1 (AI Business Analysis Core)

- **AI Provider Flexibility**: Supports OpenAI, Gemini, Groq, Ollama (local LLM), and OpenAI-compatible REST APIs.
- **Strict JSON Output & Schema Validation**: Pydantic models enforce valid business analysis output.
- **Robust Error Handling**: Gracefully handles malformed LLM responses, missing API keys, markdown fence wrapping, and invalid inputs.
- **Dual Route Endpoints**: Serves `POST /api/ai/analyze` and `POST /api/v1/ai/analyze`.

---

## Environment Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Configure your AI provider settings in `.env`:
   ```env
   LLM_PROVIDER=openai           # Options: openai, gemini, groq, ollama, custom
   LLM_MODEL=gpt-4o-mini         # e.g., gpt-4o-mini, gemini-1.5-flash, llama-3.3-70b
   LLM_API_KEY=your_actual_key   # Your LLM API key
   LLM_BASE_URL=https://api.openai.com/v1
   ```

---

## Running Locally

1. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

3. Access interactive Swagger API documentation:
   - [http://localhost:8000/docs](http://localhost:8000/docs)
   - Healthcheck: [http://localhost:8000/health](http://localhost:8000/health)

---

## Testing

Run the test suite using pytest:

```bash
pytest -v
```

All unit tests for Pydantic schemas, endpoint routing, mock LLM generation, and error handling run deterministically without requiring an active paid API key.
