from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Startup Novelty API"
    app_env: str = "development"
    log_level: str = "INFO"
    http_timeout_seconds: float = Field(default=15.0, gt=0)
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4.1-mini"
    openrouter_http_referer: AnyHttpUrl | None = None
    openrouter_x_title: str | None = "VC Foresight MVP"
    cors_allow_origins: list[str] = ["*"]
    vc_portfolio_db_path: Path = Path("data/vc_portfolio.db")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
