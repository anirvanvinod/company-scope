from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All values can be overridden via environment variables or a .env file.
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

    # Redis (cache and Celery broker)
    redis_url: str = "redis://localhost:6379/0"

    # MinIO (S3-compatible object storage for cached documents)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_documents: str = "companyscope-documents"

    # Companies House API — required for ingestion (implemented in later phases)
    ch_api_key: str = ""

    # Application secret — used for session signing (auth implemented in later phases)
    secret_key: str = "change-me-in-production"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Module-level singleton; imported by route modules and services.
settings = Settings()
