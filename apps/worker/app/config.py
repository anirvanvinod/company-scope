from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Worker service settings loaded from environment variables.

    See .env.example at the repo root for the full variable reference.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    # Database
    database_url: str = (
        "postgresql+asyncpg://companyscope:companyscope@localhost:5432/companyscope"
    )

    # Redis (Celery broker and result backend)
    redis_url: str = "redis://localhost:6379/0"

    # MinIO (S3-compatible object storage for cached documents)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_documents: str = "companyscope-documents"

    # Companies House API — required for ingestion tasks (implemented in later phases)
    ch_api_key: str = ""
    ch_base_url: str = "https://api.company-information.service.gov.uk"

    # AI inference endpoint (Ollama or OpenAI-compatible vLLM)
    # Set ai_enabled=false to skip AI calls and always use the template fallback.
    ai_enabled: bool = False
    ai_inference_url: str = "http://localhost:11434"
    ai_model_name: str = "mistral:7b-instruct"
    ai_timeout_seconds: float = 8.0


# Module-level singleton; imported by task modules.
settings = Settings()
