import logging
import os
import secrets

from dotenv import load_dotenv
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

load_dotenv()

logger = logging.getLogger(__name__)

# auto_error=False so we return our own consistent 401 (and Swagger shows an "Authorize" button)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: str | None = Security(api_key_header)) -> None:
    """Dependency that rejects requests without the correct X-API-Key header.

    Fails closed: if the server has no API_KEY configured, every protected request is refused.
    """
    expected = os.getenv("API_KEY")
    if not expected:
        logger.error("API_KEY is not configured; refusing all protected requests")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured"
        )

    # Constant-time comparison on bytes (also safe for non-ASCII input)
    if not provided or not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
