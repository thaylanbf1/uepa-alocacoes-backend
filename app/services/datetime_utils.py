from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings

settings = get_settings()
APP_TIMEZONE_NAME = settings.APP_TIMEZONE
APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)


def ensure_app_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=APP_TIMEZONE)
    return value.astimezone(APP_TIMEZONE)


def ensure_utc(value: datetime) -> datetime:
    return ensure_app_timezone(value).astimezone(timezone.utc)


def to_storage_datetime(value: datetime) -> datetime:
    return ensure_app_timezone(value).replace(tzinfo=None)


def from_storage_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=APP_TIMEZONE)
    return value.astimezone(APP_TIMEZONE)
