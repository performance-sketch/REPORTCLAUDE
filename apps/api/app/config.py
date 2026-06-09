from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = Field(..., description="Async DSN (asyncpg)")
    database_sync_url: str = Field(..., description="Sync DSN (psycopg2) para Alembic")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Meta Ads
    meta_app_id: str = Field(default="", description="TODO: set META_APP_ID")
    meta_app_secret: str = Field(default="", description="TODO: set META_APP_SECRET")
    meta_access_token: str = Field(..., description="Long-lived access token")
    meta_ad_account_ids: str = Field(..., description="Comma-separated account IDs")
    meta_api_version: str = "v19.0"

    # Rezdy
    rezdy_api_key: str = Field(..., description="TODO: set REZDY_API_KEY")
    rezdy_base_url: str = "https://api.rezdy.com/v1"
    rezdy_webhook_secret: str = Field(default="", description="Webhook signing secret")

    # App
    app_env: str = "development"
    app_secret_key: str = Field(..., min_length=32)
    sync_trigger_secret: str = Field(..., min_length=16)
    allowed_origins: str = "http://localhost:3000"

    # Workers
    meta_ads_sync_interval_minutes: int = 30
    meta_ads_lookback_days: int = 3
    meta_ads_full_lookback_days: int = 30
    rezdy_reconciliation_lookback_days: int = 7

    @field_validator("meta_ad_account_ids")
    @classmethod
    def parse_account_ids(cls, v: str) -> str:
        return v

    @property
    def meta_account_id_list(self) -> list[str]:
        return [a.strip() for a in self.meta_ad_account_ids.split(",") if a.strip()]

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
