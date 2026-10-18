import pyodbc
import pytest

import db

SETTINGS = {
    "DB_SERVER": "example.database.windows.net",
    "DB_NAME": "testdb",
    "DB_USER": "tester",
    "DB_PASSWORD": "pa;ss}word",
    "DB_DRIVER": "ODBC Driver 18 for SQL Server",
}


@pytest.fixture
def settings(monkeypatch):
    for key, value in SETTINGS.items():
        monkeypatch.setenv(key, value)


def test_get_connection_raises_when_settings_missing(monkeypatch):
    for key in SETTINGS:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="DB_PASSWORD"):
        db.get_connection()


def test_connection_string_escapes_special_characters(settings, monkeypatch):
    captured = {}

    def fake_connect(conn_str):
        captured["conn_str"] = conn_str
        return object()

    monkeypatch.setattr(db.pyodbc, "connect", fake_connect)

    db.get_connection()

    # ';' is safe inside braces and a literal '}' is doubled
    assert "PWD={pa;ss}}word};" in captured["conn_str"]
    assert "Encrypt=yes" in captured["conn_str"]
    assert "TrustServerCertificate=no" in captured["conn_str"]


def test_check_db_false_when_connection_fails(settings, monkeypatch):
    def boom(conn_str):
        raise pyodbc.Error("login failed")

    monkeypatch.setattr(db.pyodbc, "connect", boom)

    assert db.check_db() is False


def test_check_db_false_when_settings_missing(monkeypatch):
    for key in SETTINGS:
        monkeypatch.delenv(key, raising=False)

    assert db.check_db() is False


def test_check_db_true_and_closes_connection(settings, monkeypatch):
    class FakeCursor:
        def execute(self, sql):
            assert sql == "SELECT 1"
            return self

        def fetchone(self):
            return (1,)

    class FakeConnection:
        closed = False

        def cursor(self):
            return FakeCursor()

        def close(self):
            self.closed = True

    conn = FakeConnection()
    monkeypatch.setattr(db.pyodbc, "connect", lambda conn_str: conn)

    assert db.check_db() is True
    assert conn.closed is True
