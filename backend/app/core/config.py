"""Application configuration management using Pydantic Settings.

Loads environment variables from backend/.env or system environment with typed
validation, production safety checks, and secure secrets masking.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve path to backend/.env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Centralized, typed application settings."""

    # Application Identification
    APP_NAME: str = "PayFlow Copilot"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # Database Configuration (PostgreSQL with async psycopg 3)
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/payflow_copilot"

    # Security & JWT Authentication
    SECRET_KEY: str = "dev-insecure-secret-key-change-in-production-payflow-copilot-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    LOGIN_RATE_LIMIT: int = 10
    REGISTER_RATE_LIMIT: int = 5
    CHAT_RATE_LIMIT: int = 30
    DOCUMENT_RATE_LIMIT: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Razorpay Standard Checkout
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # External AI Services (Gemini & Groq)
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    # Backwards-compatible alias used by existing local deployments.
    GROQ_MODEL: str = ""
    GROQ_TIMEOUT_SECONDS: int = 60
    GROQ_MAX_RETRIES: int = 2
    EVALUATION_PROVIDER: str = "groq"

    # Phase 3 knowledge base configuration
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_NAME: str = "payflow_knowledge"
    EMBEDDING_PROVIDER: str = "gemini"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_ENDPOINT: str = ""
    EMBEDDING_BATCH_SIZE: int = 32
    KNOWLEDGE_MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024
    KNOWLEDGE_CHUNK_SIZE: int = 900
    KNOWLEDGE_CHUNK_OVERLAP: int = 180
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = ""
    LLM_API_KEY: str = ""
    KNOWLEDGE_SIMILARITY_THRESHOLD: float = 0.0

    # CORS Configuration
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        """Support comma-separated string or JSON array from environment variables."""
        if isinstance(value, str):
            val = value.strip()
            if not val:
                return []
            if val.startswith("[") and val.endswith("]"):
                try:
                    import json

                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in val.split(",") if origin.strip()]
        elif isinstance(value, (list, tuple)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return []

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: Any) -> str:
        """Ensure standard postgresql+psycopg:// async driver prefix is used."""
        if isinstance(value, str):
            url = value.strip()
            if url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql+psycopg://", 1)
            if url.startswith("postgresql://") and not url.startswith("postgresql+"):
                return url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Enforce strict production security constraints."""
        is_prod = self.APP_ENV.lower() in ("production", "prod")

        if is_prod:
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production environments.")

            insecure_defaults = (
                "dev-insecure-secret-key-change-in-production-payflow-copilot-2026",
                "secret",
                "changeme",
            )
            if self.SECRET_KEY in insecure_defaults or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "In production, SECRET_KEY must be a cryptographically secure key of at least 32 characters."
                )

            if not self.DATABASE_URL or "localhost" in self.DATABASE_URL:
                raise ValueError("Production DATABASE_URL must not use localhost.")
            if self.ALGORITHM != "HS256":
                raise ValueError("Only the configured HS256 JWT algorithm is supported.")
            if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0 or self.ACCESS_TOKEN_EXPIRE_MINUTES > 60:
                raise ValueError("Production access tokens must expire within 60 minutes.")
            if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
                raise ValueError("Production CORS_ORIGINS must explicitly list trusted origins.")
        if self.RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise ValueError("RATE_LIMIT_WINDOW_SECONDS must be positive.")
        if any(value <= 0 for value in (self.LOGIN_RATE_LIMIT, self.REGISTER_RATE_LIMIT, self.CHAT_RATE_LIMIT, self.DOCUMENT_RATE_LIMIT)):
            raise ValueError("Rate limits must be positive.")

        return self

    @model_validator(mode="after")
    def validate_knowledge_settings(self) -> "Settings":
        """Reject invalid vector and chunking settings before serving requests."""
        if self.EMBEDDING_PROVIDER.lower() == "gemini":
            if self.EMBEDDING_MODEL != "gemini-embedding-001":
                raise ValueError("Gemini embeddings require EMBEDDING_MODEL=gemini-embedding-001")
            if not 1 <= self.EMBEDDING_DIMENSION <= 3072:
                raise ValueError("EMBEDDING_DIMENSION must be between 1 and 3072")
        if self.KNOWLEDGE_CHUNK_SIZE <= 0 or not 0 <= self.KNOWLEDGE_CHUNK_OVERLAP < self.KNOWLEDGE_CHUNK_SIZE:
            raise ValueError("Knowledge chunk overlap must be smaller than chunk size")
        if not 0 <= self.KNOWLEDGE_SIMILARITY_THRESHOLD <= 1:
            raise ValueError("KNOWLEDGE_SIMILARITY_THRESHOLD must be between 0 and 1")
        return self

    @property
    def masked_database_url(self) -> str:
        """Return DATABASE_URL with user password redacted for safe logging."""
        try:
            parsed = urlparse(self.DATABASE_URL)
            if parsed.password:
                netloc = f"{parsed.username}:***@{parsed.hostname}"
                if parsed.port:
                    netloc += f":{parsed.port}"
                return urlunparse(parsed._replace(netloc=netloc))
            return self.DATABASE_URL
        except Exception:
            return "postgresql+psycopg://***@***"

    @property
    def llm_model(self) -> str:
        """Return the explicitly configured model, supporting the legacy Groq name."""
        return self.LLM_MODEL or self.GROQ_MODEL or "openai/gpt-oss-120b"

    def __repr__(self) -> str:
        """Prevent secrets from leaking when settings instance is printed or logged."""
        return (
            f"Settings("
            f"APP_NAME={self.APP_NAME!r}, "
            f"APP_ENV={self.APP_ENV!r}, "
            f"DEBUG={self.DEBUG}, "
            f"DATABASE_URL={self.masked_database_url!r}, "
            f"SECRET_KEY='***', "
            f"ALGORITHM={self.ALGORITHM!r}, "
            f"ACCESS_TOKEN_EXPIRE_MINUTES={self.ACCESS_TOKEN_EXPIRE_MINUTES}, "
            f"GEMINI_API_KEY={'***' if self.GEMINI_API_KEY else 'unset'!r}, "
            f"GROQ_API_KEY={'***' if self.GROQ_API_KEY else 'unset'!r}, "
            f"QDRANT_API_KEY={'***' if self.QDRANT_API_KEY else 'unset'!r}, "
            f"EMBEDDING_API_KEY={'***' if self.EMBEDDING_API_KEY else 'unset'!r}, "
            f"LLM_API_KEY={'***' if self.LLM_API_KEY else 'unset'!r}, "
            f"CORS_ORIGINS={self.CORS_ORIGINS!r}"
            f")"
        )

    def __str__(self) -> str:
        return self.__repr__()


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of application settings."""
    return Settings()
