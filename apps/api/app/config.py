from pydantic import model_validator
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

    # Companies House API
    ch_api_key: str = ""
    # Override in tests or staging; production value is the live CH API.
    ch_base_url: str = "https://api.company-information.service.gov.uk"

    # Application secret — used for JWT signing
    secret_key: str = "change-me-in-production"

    # CORS — allow the Next.js dev server; override per environment
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _check_production_secret(self) -> "Settings":
        """Fail fast if the default insecure secret key is used in production."""
        if self.is_production and self.secret_key == "change-me-in-production":
            raise ValueError(
                "SECRET_KEY must be changed from the default value in production. "
                "Generate a secure key with: openssl rand -hex 32"
            )
        return self


# Module-level singleton; imported by route modules and services.
settings = Settings()
