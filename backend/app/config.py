"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://muduser:mudpass@postgres:5432/muddb"

    # Redis
    redis_url: str = "redis://redis:6379"

    # AI Provider
    ai_provider: str = "fake"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ai_model: str = "claude-3-haiku"

    # Features
    ai_narration_enabled: bool = False
    ai_command_interpretation_enabled: bool = False
    ai_world_generation_enabled: bool = False
