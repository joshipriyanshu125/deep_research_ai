import os
import json
from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for the backend package
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT_ENV = os.path.join(os.path.dirname(BACKEND_DIR), ".env")
BACKEND_ENV = os.path.join(BACKEND_DIR, ".env")


class Settings(BaseSettings):
    PROJECT_NAME: str = "Deep Research AI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = "supersecretjwtkey_change_in_production_deep_research_ai"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "deep_research_ai"

    # LLM Providers
    LLM_PROVIDER: str = "openrouter"  # openrouter, openai, gemini, anthropic, mock
    OPENROUTER_API_KEY: Optional[str] = ""
    OPENAI_API_KEY: Optional[str] = ""
    GEMINI_API_KEY: Optional[str] = ""
    ANTHROPIC_API_KEY: Optional[str] = ""
    LLM_MODEL: Optional[str] = "openrouter/free"
    LLM_BASE_URL: Optional[str] = "https://openrouter.ai/api/v1"
    DEFAULT_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Search APIs
    TAVILY_API_KEY: Optional[str] = ""
    SERPER_API_KEY: Optional[str] = ""
    USE_MOCK_FALLBACK: bool = True

    # Execution limits
    MAX_CONCURRENT_RESEARCH_TASKS: int = 5
    RESEARCH_TIMEOUT_SECONDS: int = 600
    MAX_SEARCH_DEPTH: int = 3
    MAX_SEARCH_BREADTH: int = 5

    # Redis & Distributed Queue (Day 96–100)
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    USE_REDIS: bool = False

    # Vector DB (Day 96–100)
    VECTOR_DB_TYPE: str = "in_memory"  # in_memory, qdrant, chroma
    VECTOR_DB_URL: Optional[str] = "http://localhost:6333"
    VECTOR_DB_API_KEY: Optional[str] = None
    VECTOR_DB_COLLECTION: str = "deep_research_embeddings"

    # Logging & Observability (Day 96–100)
    LOG_FORMAT: str = "text"  # text, json
    LOG_LEVEL: str = "INFO"
    PROMETHEUS_METRICS_ENABLED: bool = True

    # Workers & Scalability (Day 96–100)
    WORKER_CONCURRENCY: int = 4
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    WORKER_JOB_TIMEOUT_SECONDS: int = 1800
    # "local" starts the in-process worker; "distributed" queues jobs for
    # app.workers.distributed_worker, which should run as a separate process.
    WORKER_MODE: str = "local"

    # JWT Authentication & Token Security
    JWT_ACCESS_SECRET: Optional[str] = None
    JWT_ACCESS_EXPIRES_IN: str = "15m"
    JWT_REFRESH_SECRET: Optional[str] = None
    JWT_REFRESH_EXPIRES_IN: str = "7d"

    # Email & SMTP Service (Days 67–69)
    SMTP_SERVER: Optional[str] = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = ""
    SMTP_PASSWORD: Optional[str] = ""
    EMAIL_FROM: Optional[str] = "noreply@deepresearch.ai"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip().strip('"\'')
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=[BACKEND_ENV, ROOT_ENV, ".env"],
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False
    )


settings = Settings()

