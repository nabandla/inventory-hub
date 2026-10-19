"""Make test access tokens signed with a throwaway key, and a stand-in for Microsoft's key server."""
import base64
import hashlib
import hmac
import json
import time
import types

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from auth import READ_ROLE, WRITE_ROLE

TENANT = "11111111-1111-1111-1111-111111111111"
AUDIENCE = "22222222-2222-2222-2222-222222222222"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)  # an impostor's key

_BOTH = (READ_ROLE, WRITE_ROLE)


def make_token(
    roles=_BOTH,
    *,
    aud=AUDIENCE,
    iss=ISSUER,
    exp_in=3600,
    nbf_in=-10,
    key=SIGNING_KEY,
    omit=(),
    extra=None,
) -> str:
    """A correctly signed RS256 token. Pass roles=None to leave the claim out, omit=('exp',) to drop others."""
    now = int(time.time())
    claims = {"aud": aud, "iss": iss, "iat": now, "nbf": now + nbf_in, "exp": now + exp_in, "azp": "test-client"}
    if roles is not None:
        claims["roles"] = list(roles) if isinstance(roles, (tuple, list)) else roles
    claims.update(extra or {})
    for name in omit:
        claims.pop(name, None)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def auth_header(token: str | None = None, **kwargs) -> dict:
    return {"Authorization": f"Bearer {token or make_token(**kwargs)}"}


def unsigned_token() -> str:
    """alg=none: claims with no signature at all."""
    now = int(time.time())
    claims = {"aud": AUDIENCE, "iss": ISSUER, "nbf": now - 10, "exp": now + 3600, "roles": list(_BOTH)}
    return jwt.encode(claims, key=None, algorithm="none")


def hs256_forged_token() -> str:
    """The classic confusion attack: sign with HS256 using the server's PUBLIC key as the secret."""
    public_pem = SIGNING_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    now = int(time.time())
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "test-key"}).encode())
    payload = b64(
        json.dumps(
            {"aud": AUDIENCE, "iss": ISSUER, "nbf": now - 10, "exp": now + 3600, "roles": list(_BOTH)}
        ).encode()
    )
    signature = b64(hmac.new(public_pem, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def tampered_token() -> str:
    """A genuine token whose payload was edited afterwards (roles changed) - signature no longer matches."""
    header, payload, signature = make_token(roles=[READ_ROLE]).split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    claims["roles"] = [READ_ROLE, WRITE_ROLE]
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{forged}.{signature}"


class FakeJwks:
    """Behaves like PyJWKClient but returns our test public key instead of calling Microsoft."""

    def __init__(self, key=SIGNING_KEY):
        self._public = key.public_key()

    def get_signing_key_from_jwt(self, token):
        jwt.get_unverified_header(token)  # garbage input fails here, exactly like the real client
        return types.SimpleNamespace(key=self._public)
