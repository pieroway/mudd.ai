"""Application configuration from environment variables."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    trusted_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    max_command_bytes: int = Field(default=4096, gt=0)
    command_rate_limit: int = Field(default=10, gt=0)
    command_rate_window_seconds: float = Field(default=1.0, gt=0)
    max_websocket_connections: int = Field(default=250, gt=0)
    connection_attempt_limit: int = Field(default=60, gt=0)
    connection_attempt_window_seconds: float = Field(default=60.0, gt=0)
    max_tracked_client_addresses: int = Field(default=10_000, gt=0)
    outbound_send_timeout_seconds: float = Field(default=2.0, gt=0)

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
    ai_provider: Literal["fake", "anthropic", "openai"] = "fake"
    anthropic_api_key: str = ""
    openai_api_key: SecretStr = SecretStr("")
    ai_model: str = ""
    ai_command_timeout_seconds: float = Field(default=5.0, gt=0)
    ai_command_max_input_bytes: int = Field(default=4096, gt=0, le=4096)
    ai_command_max_output_tokens: int = Field(default=512, ge=16, le=2048)
    ai_command_max_requests: int = Field(default=100, gt=0, le=1000)
    ai_command_max_concurrent: int = Field(default=2, gt=0, le=10)

    # Features
    ai_narration_enabled: bool = False
    ai_command_interpretation_enabled: bool = False
    ai_world_generation_enabled: bool = False
