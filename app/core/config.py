from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Database — split per microservice (the AI service reads/writes against three Postgres DBs)
    # `candidate_database_url`  → hiremind_candidate (owns: candidate*, parse_jobs, resume_embeddings, fake_profile_scores)
    # `company_database_url`    → hiremind_company   (owns: jobs*, job_embeddings, match_scores, ghost_job_scores, duplicate_job_clusters, hiring_predictions, hiring_outcomes, ml_models)
    # `users_database_url`      → hiremind_users     (read-only, optional — used only if we need to resolve user_id → user details)
    candidate_database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/hiremind_candidate"
    )
    company_database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/hiremind_company"
    )
    users_database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/hiremind_users"
    )
    pgvector_dim: int = 768

    # Redis / Celery (declared now, used when we add Celery)
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # LLM
    llm_backend: Literal["grok", "groq", "mock"] = "mock"
    grok_api_key: str = ""
    grok_api_base: str = "https://api.x.ai/v1"
    grok_model: str = "grok-2-latest"
    groq_api_key: str = ""
    groq_api_base: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    # Embeddings
    embedding_model: str = "sentence-transformers/all-mpnet-base-v2"

    # External verification
    github_token: str = ""  # optional; lifts rate limit from 60/hr to 5000/hr
    github_timeout_seconds: float = 10.0

    # OCR
    ocr_engine: Literal["paddle", "tesseract"] = "tesseract"

    # Vector store
    vector_store_backend: Literal["pgvector", "pinecone"] = "pgvector"
    pinecone_api_key: str = ""
    pinecone_index: str = ""

    # Artifacts (uploaded resumes etc.)
    artifacts_dir: str = "./artifacts"

    # ML
    model_registry_path: str = "./artifacts/models"
    model_version: str = "v1"

    # CORS — comma-separated origins; "*" allowed in development
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
