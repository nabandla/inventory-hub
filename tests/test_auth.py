import pytest
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

import auth
import main
from auth import READ_ROLE, WRITE_ROLE
from routers.items import get_repository
from scripts.export_openapi import build
from tests.fakes import InMemoryItemRepository
from tests.tokens import (
    OTHER_KEY,
    TENANT,
    auth_header,
    hs256_forged_token,
    make_token,
    tampered_token,
    unsigned_token,
)


class ExplodingRepo:
    """Any use means a request got past authentication when it should not have."""

    def __getattr__(self, name):
        raise AssertionError("repository was reached without passing authentication")


@pytest.fixture
def locked(auth_env):
    """Auth configured; the repository blows up if a request ever reaches it."""
    main.app.dependency_overrides[get_repository] = lambda: ExplodingRepo()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture
def open_repo(auth_env):
    """Auth configured; a harmless in-memory repository behind it."""
    main.app.dependency_overrides[get_repository] = lambda: InMemoryItemRepository()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


# --- no token / bad token -> 401, and the repository is never reached ------------------

def test_missing_token_is_401_with_bearer_challenge(locked):
    response = locked.get("/v1/items")

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing access token"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic dXNlcjpwYXNz", "Bearer ", "Token abc", "bearer"])
def test_wrong_scheme_or_empty_token_is_401(locked, header):
    assert locked.get("/v1/items", headers={"Authorization": header}).status_code == 401


def test_old_api_key_header_no_longer_works(locked):
    assert locked.get("/v1/items", headers={"X-API-Key": "anything"}).status_code == 401


@pytest.mark.parametrize(
    "label,token",
    [
        ("garbage", "not-a-token"),
        ("expired", make_token(exp_in=-3600)),
        ("not valid yet", make_token(nbf_in=3600)),
        ("wrong audience (token for another API)", make_token(aud="99999999-9999-9999-9999-999999999999")),
        ("wrong issuer (another tenant)", make_token(iss="https://login.microsoftonline.com/other-tenant/v2.0")),
        ("signed by an impostor's key", make_token(key=OTHER_KEY)),
        ("no expiry claim", make_token(omit=("exp",))),
        ("no audience claim", make_token(omit=("aud",))),
        ("no issuer claim", make_token(omit=("iss",))),
        ("alg=none (unsigned)", unsigned_token()),
        ("HS256 signed with the public key", hs256_forged_token()),
        ("payload edited after signing", tampered_token()),
    ],
)
def test_bad_tokens_are_401(locked, label, token):
    response = locked.get("/v1/items", headers=auth_header(token))

    assert response.status_code == 401, label
    assert response.json() == {"detail": "Invalid or expired access token"}
    assert token not in response.text and token not in str(response.headers)


def test_small_clock_difference_is_tolerated(open_repo):
    just_expired = make_token(exp_in=-30)  # leeway is 60s

    assert open_repo.get("/v1/items", headers=auth_header(just_expired)).status_code == 200


def test_unknown_signing_key_is_401(locked, monkeypatch):
    class UnknownKey:
        def get_signing_key_from_jwt(self, token):
            raise PyJWKClientError("Unable to find a signing key that matches")

    monkeypatch.setattr(auth, "_jwks_client", lambda tenant_id: UnknownKey())

    assert locked.get("/v1/items", headers=auth_header()).status_code == 401


# --- roles -> 403 ------------------------------------------------------------------------

def test_read_only_token_can_read_but_not_write(open_repo):
    reader = auth_header(roles=[READ_ROLE])

    assert open_repo.get("/v1/items", headers=reader).status_code == 200
    assert open_repo.post("/v1/items", headers=reader, json={"sku": "A", "name": "x"}).status_code == 403
    assert open_repo.put("/v1/items/1", headers=reader, json={"name": "x", "quantity": 1}).status_code == 403
    assert open_repo.delete("/v1/items/1", headers=reader).status_code == 403


def test_write_only_token_can_write_but_not_read(open_repo):
    writer = auth_header(roles=[WRITE_ROLE])

    assert open_repo.post("/v1/items", headers=writer, json={"sku": "A", "name": "x"}).status_code == 201
    assert open_repo.get("/v1/items", headers=writer).status_code == 403
    assert open_repo.get("/v1/items/1", headers=writer).status_code == 403


@pytest.mark.parametrize(
    "roles", [None, [], ["Other.Role"], "Items.Read", "Items.Read Items.Write"], ids=["absent", "empty", "other", "string", "joined"]
)
def test_tokens_without_a_usable_roles_claim_are_403(locked, roles):
    response = locked.get("/v1/items", headers=auth_header(roles=roles))

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


# --- fail closed / dependencies unavailable -> 503 ---------------------------------------

@pytest.mark.parametrize("missing", ["AZURE_TENANT_ID", "API_AUDIENCE"])
@pytest.mark.parametrize("with_token", [True, False])
def test_fails_closed_when_authentication_is_not_configured(locked, monkeypatch, missing, with_token):
    monkeypatch.delenv(missing)
    headers = auth_header() if with_token else {}

    response = locked.get("/v1/items", headers=headers)

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is not configured"}


def test_empty_settings_also_fail_closed(locked, monkeypatch):
    monkeypatch.setenv("API_AUDIENCE", "")

    assert locked.get("/v1/items", headers=auth_header()).status_code == 503


def test_unreachable_key_server_is_503_not_401(locked, monkeypatch):
    class Down:
        def get_signing_key_from_jwt(self, token):
            raise PyJWKClientConnectionError("cannot reach login.microsoftonline.com")

    monkeypatch.setattr(auth, "_jwks_client", lambda tenant_id: Down())

    response = locked.get("/v1/items", headers=auth_header())

    assert response.status_code == 503
    assert "microsoftonline" not in response.text


def test_the_real_key_server_address_uses_the_configured_tenant():
    auth._jwks_client.cache_clear()
    client = auth._jwks_client(TENANT)

    assert client.uri == f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys"
    auth._jwks_client.cache_clear()


# --- the whole contract is protected -----------------------------------------------------

def test_every_v1_operation_in_the_contract_refuses_a_request_without_a_token(locked):
    paths = build()["paths"]
    checked = 0
    for path, operations in paths.items():
        if not path.startswith("/v1"):
            continue
        for method in operations:
            url = path.replace("{item_id}", "1")
            body = {"sku": "A", "name": "x", "quantity": 1} if method in ("post", "put") else None
            response = locked.request(method.upper(), url, json=body)
            assert response.status_code == 401, f"{method.upper()} {path} is not protected"
            checked += 1
    assert checked >= 5  # list, create, get, update, delete


@pytest.mark.parametrize("path", ["/health", "/health/db"])
def test_health_routes_stay_open_without_a_token(auth_env, monkeypatch, path):
    monkeypatch.setattr(main, "check_db", lambda: True)

    assert TestClient(main.app).get(path).status_code == 200


def test_swagger_documents_bearer_authentication():
    schemes = build()["components"]["securitySchemes"]

    assert any(s.get("type") == "http" and s.get("scheme") == "bearer" for s in schemes.values())
    assert not any(s.get("type") == "apiKey" for s in schemes.values())
