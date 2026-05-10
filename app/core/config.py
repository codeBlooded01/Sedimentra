from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Genomic Intelligence System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://gis_user:gis_pass@localhost:5432/genomic_db"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # File Storage
    TMP_UPLOAD_DIR: str = "/tmp/gis_uploads"
    MAX_UPLOAD_SIZE_MB: int = 500  # 500MB max per file

    # Validation Thresholds
    SHANNON_INDEX_MIN: float = 0.0
    SHANNON_INDEX_MAX: float = 7.0
    SPARSITY_SINGLETON_THRESHOLD: int = 1

    # Required CSV Headers
    ASV_TABLE_REQUIRED_COLS: list[str] = ["ASV_ID"]
    TAXONOMY_REQUIRED_COLS: list[str] = [
        "ASV_ID", "Kingdom", "Phylum", "Class",
        "Order", "Family", "Genus", "Species"
    ]

    # Auth / JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_EMAIL_DOMAINS: Optional[str] = None
    REQUIRE_EMAIL_VERIFICATION: bool = True

    # Email settings
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: Optional[str] = None

    # Frontend URL for password reset links
    FRONTEND_URL: str = "http://localhost:5173"

    @property
    def allowed_domains_list(self) -> list[str]:
        domains = self.ALLOWED_EMAIL_DOMAINS
        if not domains:
            return []
        return [d.strip().lower() for d in domains.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
