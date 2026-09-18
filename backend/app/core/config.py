import logging
from typing import Any, List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    PROJECT_NAME: str = "Business Transformation AI"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    @field_validator("DEBUG", mode="before")
    @classmethod
    def coerce_debug(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s not in ("false", "0", "no", "off", "release", "")

    # Security & Auth
    SECRET_KEY: str = "super_secret_jwt_key_change_in_production_123456789"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "sqlite:///./business_transformation.db"

    # CORS — comma-separated list of allowed origins.
    # Development default allows localhost. Override in production.
    # Example: CORS_ORIGINS=https://app.example.com,https://www.example.com
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"

    def get_cors_origins(self) -> List[str]:
        """Return parsed list of allowed CORS origins."""
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return origins if origins else ["http://localhost:3000"]

    # AI / LLM Config
    LLM_PROVIDER: str = "openai"  # openai, gemini, groq, ollama, custom
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TEMPERATURE: float = 0.2
    LLM_TIMEOUT_SECONDS: int = 90

    # Ollama-specific (used when LLM_PROVIDER=ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Document Upload Limits
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Rate Limiting (Module 12)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_AI_REQUESTS: int = 20
    RATE_LIMIT_AI_WINDOW_SECONDS: int = 3600
    RATE_LIMIT_PUBLIC_REQUESTS: int = 30
    RATE_LIMIT_PUBLIC_WINDOW_SECONDS: int = 60
    MAX_CHAT_MESSAGE_LENGTH: int = 4000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def warn_insecure_defaults(self) -> None:
        """Log warnings when production-unsafe defaults are detected."""
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == "super_secret_jwt_key_change_in_production_123456789":
                logger.critical("SECURITY: SECRET_KEY is using the default insecure value in production!")
            if not self.LLM_API_KEY or self.LLM_API_KEY in ("your_llm_api_key_here", "mock_key_for_testing"):
                logger.warning("LLM_API_KEY is not set — AI will use mock fallback responses.")
            if self.DATABASE_URL.startswith("sqlite"):
                logger.warning("DATABASE_URL is SQLite — not recommended for production.")


settings = Settings()
