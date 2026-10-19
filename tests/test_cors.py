import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cors import configure_cors, parse_origins
from routers import items
from routers.items import get_repository
from tests.fakes import InMemoryItemRepository

ALLOWED = "http://localhost:5173"
OTHER = "https://evil.example"
KEY = "cors-test-key"


def build_app(monkeypatch, origins):
    """A fresh app wired like main.py, with the given CORS_ORIGINS setting."""
    if origins is None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("CORS_ORIGINS", origins)
    monkeypatch.setenv("API_KEY", KEY)
    app = FastAPI()
    configure_cors(app)
    app.include_router(items.router)
    app.dependency_overrides[get_repository] = lambda: InMemoryItemRepository()
    return TestClient(app)


def preflight(client, origin, method="POST", headers="x-api-key,content-type"):
    return client.options(
        "/v1/items",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


# --- parsing -------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [None, "", "   ", " , ,"])
def test_empty_setting_allows_nothing(raw):
    assert parse_origins(raw) == []


def test_parses_trims_and_dedupes():
    raw = " http://localhost:5173/ , https://app.example.com,https://app.example.com/ "

    assert parse_origins(raw) == ["http://localhost:5173", "https://app.example.com"]


@pytest.mark.parametrize("raw", ["*", "https://a.example,*", "localhost:5173", "ftp://a.example", "https://a.example/path"])
def test_rejects_wildcards_and_malformed_origins(raw):
    with pytest.raises(ValueError):
        parse_origins(raw)


# --- behaviour -----------------------------------------------------------------------

def test_preflight_from_allowed_origin_succeeds_without_an_api_key(monkeypatch):
    client = build_app(monkeypatch, ALLOWED)

    response = preflight(client, ALLOWED)  # note: no X-API-Key sent on a preflight

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "x-api-key" in allowed_headers and "content-type" in allowed_headers
    assert "POST" in response.headers["access-control-allow-methods"]


def test_preflight_from_unlisted_origin_is_refused(monkeypatch):
    client = build_app(monkeypatch, ALLOWED)

    response = preflight(client, OTHER)

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_preflight_asking_for_unlisted_header_is_refused(monkeypatch):
    client = build_app(monkeypatch, ALLOWED)

    response = preflight(client, ALLOWED, headers="x-api-key,x-sneaky")

    assert response.status_code == 400


def test_empty_setting_refuses_every_browser_origin(monkeypatch):
    client = build_app(monkeypatch, "")

    response = preflight(client, ALLOWED)

    assert "access-control-allow-origin" not in response.headers
    assert response.status_code in (400, 405)


def test_actual_request_from_allowed_origin_gets_cors_header_and_still_needs_a_key(monkeypatch):
    client = build_app(monkeypatch, ALLOWED)

    without_key = client.get("/v1/items", headers={"Origin": ALLOWED})
    with_key = client.get("/v1/items", headers={"Origin": ALLOWED, "X-API-Key": KEY})

    assert without_key.status_code == 401  # CORS is not authentication
    assert with_key.status_code == 200
    assert with_key.headers["access-control-allow-origin"] == ALLOWED


def test_actual_request_from_unlisted_origin_gets_no_cors_header(monkeypatch):
    client = build_app(monkeypatch, ALLOWED)

    response = client.get("/v1/items", headers={"Origin": OTHER, "X-API-Key": KEY})

    assert "access-control-allow-origin" not in response.headers


def test_credentials_are_never_allowed(monkeypatch):
    client = build_app(monkeypatch, ALLOWED)

    response = preflight(client, ALLOWED)

    assert "access-control-allow-credentials" not in response.headers


def test_multiple_origins_each_get_their_own_header(monkeypatch):
    other_ok = "https://app.example.com"
    client = build_app(monkeypatch, f"{ALLOWED},{other_ok}")

    assert preflight(client, ALLOWED).headers["access-control-allow-origin"] == ALLOWED
    assert preflight(client, other_ok).headers["access-control-allow-origin"] == other_ok


def _has_cors_middleware(app):
    return any(m.cls.__name__ == "CORSMiddleware" for m in app.user_middleware)


@pytest.mark.parametrize("origins,expected", [(ALLOWED, True), ("", False)])
def test_main_app_applies_the_cors_setting_at_startup(monkeypatch, origins, expected):
    import importlib

    import main

    monkeypatch.setenv("CORS_ORIGINS", origins)
    try:
        reloaded = importlib.reload(main)  # re-runs main.py as a fresh start would
        assert _has_cors_middleware(reloaded.app) is expected
    finally:
        monkeypatch.undo()
        importlib.reload(main)  # restore the module for the other tests
