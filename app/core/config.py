import os
from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings managed via Pydantic v2.
    Loads from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server configuration
    ENVIRONMENT: str = Field(default="development", description="Runtime environment (development/production/test)")
    HOST: str = Field(default="0.0.0.0", description="Bind host")
    PORT: int = Field(default=8000, description="Bind port")
    LOG_LEVEL: str = Field(default="info", description="Logging level")

    # Gemini configuration
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API Key")
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash-native-audio-preview-12-2025",
        description="Google Gemini Live Audio model name",
    )
    GEMINI_VOICE: str = Field(default="Fenrir", description="Gemini voice name (e.g. Fenrir, Aoede, Kore, Puck, Charon)")

    # Security & Limits
    ALLOWED_ORIGINS: str = Field(
        default="*",
        description="Comma-separated allowed origins or * for all",
    )
    MAX_SESSION_SECONDS: int = Field(default=600, description="Max session duration in seconds")
    MAX_CONCURRENT_SESSIONS: int = Field(default=50, description="Max concurrent active voice sessions")

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    def is_origin_allowed(self, origin: str | None) -> bool:
        if "*" in self.origins_list or not origin:
            return True
        return origin in self.origins_list


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()

