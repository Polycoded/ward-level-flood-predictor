"""Environment-backed settings for the alerting, subscription and speed features."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage
    database_url: str = "sqlite:///./flood.db"

    # CORS: comma-separated origins; "*" is only acceptable for local demos.
    cors_origins: str = "*"

    # Everything the team sends during the hackathon is an exercise.
    exercise_mode: bool = True

    # Shared secret required to approve or cancel alerts. Empty means those
    # operator actions are refused (fail closed), never left open.
    admin_api_token: str = ""

    # Background scheduler
    enable_scheduler: bool = False
    warm_cache_on_startup: bool = True
    scheduler_interval_minutes: int = 15
    forecast_hours: int = 6
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    chennai_lat: float = 13.0827
    chennai_lon: float = 80.2707

    # Alert rules (Mit owns the authoritative values in model/alert_rules.py;
    # these are conservative defaults used until that module lands).
    min_watch_rainfall_mm: float = 20.0
    min_warning_rainfall_mm: float = 40.0
    hysteresis_hours: int = 6
    max_alerts_per_cycle: int = 50

    # OpenWA (unofficial WhatsApp Web bridge)
    openwa_base_url: str = ""
    openwa_api_key: str = ""
    openwa_session: str = "default"
    openwa_webhook_secret: str = ""
    openwa_min_interval_seconds: float = 3.0
    openwa_max_interval_seconds: float = 5.0
    openwa_max_retries: int = 3
    openwa_timeout_seconds: float = 15.0

    # Web Push
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:alerts@example.org"

    # Privacy: phone/chat identifiers are encrypted at rest with this key.
    phone_encryption_key: str = ""

    # Abuse protection
    subscription_rate_limit_per_minute: int = 20
    webhook_rate_limit_per_minute: int = 120

    # Twilio SMS fallback for numbers we cannot reach over WhatsApp.
    twilio_sms_fallback: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
