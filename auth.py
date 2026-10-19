"""Authentication and authorisation: Microsoft Entra ID access tokens (JWTs).

Callers get a short-lived token from Entra ID and send it as `Authorization: Bearer <token>`.
This module checks the token is genuine, meant for THIS API, unexpired, and carries the role
the route needs (Items.Read / Items.Write).
"""
import logging
import os
from functools import lru_cache

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError

load_dotenv()

logger = logging.getLogger(__name__)

READ_ROLE = "Items.Read"
WRITE_ROLE = "Items.Write"

CLOCK_SKEW_SECONDS = 60  # tolerate small clock differences between Microsoft and us
ALLOWED_ALGORITHMS = ["RS256"]  # fixed: never trust the algorithm named inside the token

# auto_error=False so we return our own consistent 401 (and Swagger shows an "Authorize" button)
bearer_scheme = HTTPBearer(auto_error=False, description="Microsoft Entra ID access token")


def _settings() -> tuple[str, str] | None:
    tenant_id = os.getenv("AZURE_TENANT_ID")
    audience = os.getenv("API_AUDIENCE")
    if not tenant_id or not audience:
        return None
    return tenant_id, audience


@lru_cache(maxsize=4)
def _jwks_client(tenant_id: str) -> PyJWKClient:
    """Fetches (and caches) Microsoft's public signing keys for this tenant."""
    return PyJWKClient(
        f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
        cache_keys=True,
        lifespan=3600,
        timeout=10,
    )


def validate_token(token: str, tenant_id: str, audience: str) -> dict:
    """Return the token's claims if it is valid; raise a jwt exception otherwise."""
    signing_key = _jwks_client(tenant_id).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=ALLOWED_ALGORITHMS,
        audience=audience,
        issuer=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        leeway=CLOCK_SKEW_SECONDS,
        options={"require": ["exp", "nbf", "iss", "aud"]},
    )


def require_role(role: str):
    """Build a dependency that only lets through callers whose token carries `role`.

    - 503: authentication is not configured (fails closed) or Microsoft's keys are unreachable
    - 401: no token, or a token that is invalid, expired, or meant for another API
    - 403: a genuine token that lacks the required role
    """

    def dependency(
        credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    ) -> dict:
        settings = _settings()
        if settings is None:
            logger.error("AZURE_TENANT_ID / API_AUDIENCE not configured; refusing protected requests")
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")

        if credentials is None or not credentials.credentials:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Missing access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        tenant_id, audience = settings
        try:
            claims = validate_token(credentials.credentials, tenant_id, audience)
        except PyJWKClientConnectionError:
            logger.error("Could not fetch Microsoft's signing keys")
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to verify access tokens right now"
            )
        except (PyJWKClientError, InvalidTokenError) as exc:
            # The reason (expired? wrong audience?) goes to the log, not to the caller
            logger.info("Rejected access token: %s", type(exc).__name__)
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        roles = claims.get("roles")
        if not isinstance(roles, list) or role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return claims

    return dependency
