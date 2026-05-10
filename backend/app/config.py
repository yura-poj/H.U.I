import os


def _get_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    DATABASE_URL = os.environ.get("DATABASE_URL")
    MAX_CONTENT_LENGTH = _get_int("MAX_CONTENT_LENGTH", 1_048_576)
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
    TRUST_PROXY_HEADERS = _get_bool("TRUST_PROXY_HEADERS", False)
    RATE_LIMIT_ENABLED = _get_bool("RATE_LIMIT_ENABLED", True)
    RATE_LIMIT_MAX_REQUESTS = _get_int("RATE_LIMIT_MAX_REQUESTS", 120)
    RATE_LIMIT_WINDOW_SECONDS = _get_int("RATE_LIMIT_WINDOW_SECONDS", 60)
    REGISTRATION_IP_LIMIT = _get_int("REGISTRATION_IP_LIMIT", 3)
    REGISTRATION_IP_WINDOW_SECONDS = _get_int("REGISTRATION_IP_WINDOW_SECONDS", 86400)
    MAX_USERNAME_LENGTH = _get_int("MAX_USERNAME_LENGTH", 32)
    MAX_PASSWORD_LENGTH = _get_int("MAX_PASSWORD_LENGTH", 128)
    MAX_INSULT_LENGTH = _get_int("MAX_INSULT_LENGTH", 1000)
    AUTH_TOKEN_TTL_DAYS = _get_int("AUTH_TOKEN_TTL_DAYS", 30)
