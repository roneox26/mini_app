"""Centralized economy settings with database overrides."""
from flask import current_app

from app.models import AppSetting


def _setting(key: str, fallback):
    setting = AppSetting.query.get(key)
    if not setting:
        return fallback
    return setting.value


def get_int(key: str, fallback: int) -> int:
    try:
        return int(_setting(key, fallback))
    except (TypeError, ValueError):
        return fallback


def mining_session_seconds() -> int:
    hours = get_int("mining_session_hours", current_app.config["MINING_SESSION_HOURS"])
    return max(1, hours) * 3600


def normal_mining_rate() -> int:
    return max(0, get_int("normal_rate", current_app.config["DEFAULT_MINING_RATE"]))