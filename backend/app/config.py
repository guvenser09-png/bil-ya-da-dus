"""QuizRoyale Backend Application Configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://quizroyale:quizroyale_dev_2026@localhost:5432/quizroyale"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRATION_MINUTES: int = 30  # 30 minutes
    JWT_REFRESH_EXPIRATION_DAYS: int = 30  # 30 days

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60  # general API
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10  # auth endpoints (login/register)

    # Anthropic AI
    ANTHROPIC_API_KEY: str = ""

    # Game Settings
    LOBBY_TIMEOUT_SECONDS: int = 20
    MIN_PLAYERS: int = 5
    MAX_PLAYERS: int = 20
    ROUND_COUNT: int = 5

    # App Info
    APP_NAME: str = "QuizRoyale"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
