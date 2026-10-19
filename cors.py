import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = ["X-API-Key", "Content-Type"]


def parse_origins(raw: str | None) -> list[str]:
    """Turn 'https://a.example, http://localhost:5173/' into a clean list of origins.

    Empty or missing means NO browser origin is allowed. A wildcard or a malformed entry
    raises, so a bad setting stops the app starting instead of silently opening the API.
    """
    origins: list[str] = []
    for entry in (raw or "").split(","):
        origin = entry.strip().rstrip("/")  # an Origin header never has a trailing slash
        if not origin:
            continue
        if origin == "*":
            raise ValueError("CORS_ORIGINS must list explicit origins, never '*'")
        if not origin.startswith(("http://", "https://")) or "/" in origin.split("://", 1)[1]:
            raise ValueError(f"Invalid CORS origin (expected scheme://host[:port]): {entry.strip()!r}")
        if origin not in origins:
            origins.append(origin)
    return origins


def configure_cors(app: FastAPI) -> None:
    """Allow browser calls only from the origins listed in the CORS_ORIGINS setting."""
    origins = parse_origins(os.getenv("CORS_ORIGINS"))
    if not origins:
        logger.info("CORS_ORIGINS is empty: no browser origin is allowed")
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
        allow_credentials=False,  # the API key is a header, not a cookie
        max_age=600,
    )
    logger.info("CORS allowed origins: %s", ", ".join(origins))
