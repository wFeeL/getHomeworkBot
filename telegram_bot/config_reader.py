"""Application configuration.

Configuration is read from environment variables (optionally via a `.env` file).

IMPORTANT: the bot must not modify `.env` at runtime.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot settings.

    Required environment variables:
      - BOT_TOKEN
      - WEATHER_API

    Optional:
      - SUPER_ADMIN_TELEGRAM_ID
      - PG_DSN (preferred), or POSTGRES_* variables
      - MIN_DATE / MAX_DATE (YYYY-MM-DD)
    """

    bot_token: str = Field(alias="BOT_TOKEN")
    weather_api: str = Field(alias="WEATHER_API")

    super_admin_telegram_id: Optional[str] = Field(default=None, alias="SUPER_ADMIN_TELEGRAM_ID")

    # Prefer PG_DSN, but we can derive DSN from POSTGRES_* variables.
    pg_dsn: Optional[str] = Field(default=None, alias="PG_DSN")

    # Default academic year range (can be overridden via env)
    min_date: date = Field(default=date(2025, 9, 1), alias="MIN_DATE")
    max_date: date = Field(default=date(2026, 5, 31), alias="MAX_DATE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _derive_pg_dsn_if_missing(self) -> "Settings":
        if self.pg_dsn:
            return self

        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "password")
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "postgres")

        # asyncpg accepts both postgresql:// and postgres://
        self.pg_dsn = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        return self


config = Settings()
