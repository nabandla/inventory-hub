import pytest
from fastapi.testclient import TestClient

import main
from routers.items import get_repository
from tests.fakes import InMemoryItemRepository

KEY = "correct-horse-battery-staple"


class ExplodingRepo:
    """Any use means the request got past the guard when it should not have."""

    def __getattr__(self, name):
        raise AssertionError("repository was reached without passing authentication")


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("API_KEY", KEY)
    main.app.dependency_overrides[get_repository] = lambda: ExplodingRepo()
    yield
    main.app.dependency_overrides.clear()


def test_missing_key_is_rejected(configured):
    response = TestClient(main.app).get("/v1/items")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}
    assert response.headers["www-authenticate"] == "ApiKey"


def test_wrong_key_is_rejected(configured):
    response = TestClient(main.app).get("/v1/items", headers={"X-API-Key": "nope"})

    assert response.status_code == 401


def test_empty_key_header_is_rejected(configured):
    assert TestClient(main.app).get("/v1/items", headers={"X-API-Key": ""}).status_code == 401


def test_key_with_different_length_or_case_is_rejected(configured):
    client = TestClient(main.app)

    assert client.get("/v1/items", headers={"X-API-Key": KEY.upper()}).status_code == 401
    assert client.get("/v1/items", headers={"X-API-Key": KEY + "x"}).status_code == 401
    assert client.get("/v1/items", headers={"X-API-Key": KEY[:-1]}).status_code == 401


def test_non_ascii_key_does_not_crash(configured):
    response = TestClient(main.app).get("/v1/items", headers={"X-API-Key": "kéy".encode("utf-8")})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/v1/items", None),
        ("post", "/v1/items", {"sku": "A", "name": "x"}),
        ("get", "/v1/items/1", None),
        ("put", "/v1/items/1", {"name": "x", "quantity": 1}),
        ("delete", "/v1/items/1", None),
    ],
)
def test_every_items_route_requires_a_key(configured, method, path, body):
    response = getattr(TestClient(main.app), method)(path, **({"json": body} if body else {}))

    assert response.status_code == 401


def test_correct_key_is_accepted(monkeypatch):
    monkeypatch.setenv("API_KEY", KEY)
    main.app.dependency_overrides[get_repository] = lambda: InMemoryItemRepository()
    try:
        response = TestClient(main.app).get("/v1/items", headers={"X-API-Key": KEY})
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("configured_value", [None, ""])
def test_fails_closed_when_server_has_no_key(monkeypatch, configured_value):
    if configured_value is None:
        monkeypatch.delenv("API_KEY", raising=False)
    else:
        monkeypatch.setenv("API_KEY", configured_value)
    main.app.dependency_overrides[get_repository] = lambda: ExplodingRepo()
    try:
        client = TestClient(main.app)
        with_empty_key = client.get("/v1/items", headers={"X-API-Key": ""})
        with_some_key = client.get("/v1/items", headers={"X-API-Key": "anything"})
    finally:
        main.app.dependency_overrides.clear()

    assert with_empty_key.status_code == 503
    assert with_some_key.status_code == 503


def test_error_responses_never_contain_the_key(configured):
    response = TestClient(main.app).get("/v1/items", headers={"X-API-Key": "wrong"})

    assert KEY not in response.text
    assert KEY not in str(response.headers)


@pytest.mark.parametrize("path", ["/health", "/health/db"])
def test_health_routes_stay_open_without_a_key(monkeypatch, path):
    monkeypatch.setenv("API_KEY", KEY)
    monkeypatch.setattr(main, "check_db", lambda: True)

    response = TestClient(main.app).get(path)

    assert response.status_code == 200


def test_swagger_documents_the_api_key_header():
    schema = TestClient(main.app).get("/openapi.json").json()

    schemes = schema["components"]["securitySchemes"]
    assert any(s.get("name") == "X-API-Key" and s.get("in") == "header" for s in schemes.values())
