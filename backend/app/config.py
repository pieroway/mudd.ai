"""Application configuration from environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    trusted_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("trusted_origins")
    @classmethod
    def reject_wildcard_origins(cls, value: str) -> str:
        if "*" in (origin.strip() for origin in value.split(",")):
            raise ValueError("TRUSTED_ORIGINS must contain exact origins, not '*'")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        """Return exact browser origins allowed to call the application."""
        return [origin.strip() for origin in self.trusted_origins.split(",") if origin.strip()]

    def allows_origin(self, origin: str | None) -> bool:
        """Allow native clients without Origin; browser origins must be trusted."""
        return origin is None or origin in self.allowed_origins

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
