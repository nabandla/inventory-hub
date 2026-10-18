from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_ok_when_database_reachable(monkeypatch):
    # Fake the database: CI has no .env, no password and no network access to Azure SQL.
    monkeypatch.setattr(main, "check_db", lambda: True)

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_db_returns_503_when_database_down(monkeypatch):
    monkeypatch.setattr(main, "check_db", lambda: False)

    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}


def test_health_db_error_body_does_not_leak_details(monkeypatch):
    monkeypatch.setattr(main, "check_db", lambda: False)

    body = client.get("/health/db").text.lower()

    for sensitive in ("password", "server", "database.windows.net", "uid", "traceback"):
        assert sensitive not in body
