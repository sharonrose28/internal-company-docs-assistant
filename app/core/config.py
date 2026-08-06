from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Internal Company Docs Assistant"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://docs:docs@localhost:5432/docs"
    redis_url: str = "redis://localhost:6379/0"
    cache_redis_url: str = "redis://localhost:6379/1"
    cache_ttl_seconds: int = Field(default=900, ge=60, le=86400)
    max_ingestion_attempts: int = Field(default=5, ge=1, le=20)
    jwt_secret: SecretStr = SecretStr("development-only-secret-change-me")
    jwt_issuer: str = "company-docs"
    jwt_audience: str = "company-docs-api"
    access_token_minutes: int = Field(default=15, ge=1, le=1440)
    upload_dir: Path = Path("./data/uploads")
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "company_documents_hybrid_v1"
    retrieval_candidate_limit: int = Field(default=30, ge=10, le=100)
    openai_api_key: SecretStr | None = None
    embedding_model: Literal["text-embedding-3-small"] = "text-embedding-3-small"
    embedding_batch_size: int = Field(default=64, ge=1, le=256)
    embedding_max_retries: int = Field(default=4, ge=0, le=10)
    rag_model: Literal["gpt-5.6-sol"] = "gpt-5.6-sol"
    rag_reasoning_effort: Literal["none", "low", "medium", "high"] = "low"
    rag_context_tokens: int = Field(default=6000, ge=1000, le=50000)
    rag_min_confidence: float = Field(default=0.60, ge=0, le=1)
    rag_hybrid_score_threshold: float = Field(default=0.20, ge=0)
    rag_semantic_score_threshold: float = Field(default=0.35, ge=-1, le=1)
    chunk_size_tokens: int = Field(default=500, ge=100, le=2000)
    chunk_overlap_tokens: int = Field(default=100, ge=0, le=500)

    @field_validator("chunk_overlap_tokens")
    @classmethod
    def validate_overlap(cls, value: int, info) -> int:
        size = info.data.get("chunk_size_tokens", 500)
        if value >= size:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS")
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_driver(cls, value: str) -> str:
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+asyncpg://", 1)
        elif value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)

        if value.startswith("postgresql+asyncpg://") and "?" in value:
            base, query = value.split("?", 1)
            params: list[tuple[str, str]] = []
            for key, item in parse_qsl(query, keep_blank_values=True):
                if key == "channel_binding":
                    continue
                params.append(("ssl" if key == "sslmode" else key, item))
            return f"{base}?{urlencode(params)}" if params else base
        return value

    @field_validator("jwt_secret")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        return value

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
