import pyodbc
import pytest

import db

SETTINGS = {
    "DB_SERVER": "example.database.windows.net",
    "DB_NAME": "testdb",
    "DB_USER": "tester",
    "DB_PASSWORD": "secret-pass",
    "DB_DRIVER": "ODBC Driver 18 for SQL Server",
}

TIMEOUT_ERROR = (
    "08001",
    "[08001] [Microsoft][ODBC Driver 18 for SQL Server]TCP Provider: Timeout error [258]. (258) (SQLDriverConnect)",
)
PAUSED_ERROR = (
    "42000",
    "[42000] Database 'x' on server 'y' is not currently available. Please retry the connection later. (40613)",
)
LOGIN_FAILED = (
    "28000",
    "[28000] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]Login failed for user 'app_inventory'. (18456)",
)


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(db, "_now", fake.monotonic)
    monkeypatch.setattr(db, "_sleep", fake.sleep)
    for key, value in SETTINGS.items():
        monkeypatch.setenv(key, value)
    return fake


def scripted_connect(monkeypatch, clock, outcomes, attempt_seconds=30):
    """Replace pyodbc.connect: each call consumes one outcome (an exception args tuple or a connection)."""
    calls = []

    def fake_connect(conn_str):
        calls.append(conn_str)
        clock.now += attempt_seconds  # a failed attempt takes time, like a real login timeout
        outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(outcome, tuple):
            raise pyodbc.Error(*outcome)
        return outcome

    monkeypatch.setattr(db.pyodbc, "connect", fake_connect)
    return calls


# --- which errors count as temporary -------------------------------------------------

@pytest.mark.parametrize(
    "args,expected",
    [
        (TIMEOUT_ERROR, True),
        (PAUSED_ERROR, True),
        (("HYT00", "Login timeout expired"), True),
        (("08S01", "Communication link failure"), True),
        (LOGIN_FAILED, False),
        (("08001", "Login failed for user 'x'. (18456)"), False),  # even with a connection SQLSTATE
        (("42000", "Incorrect syntax near 'SELEC'. (102)"), False),
        (("23000", "Violation of UNIQUE KEY constraint (2627)"), False),
        (("login failed",), False),
        ((), False),
    ],
)
def test_is_transient(args, expected):
    assert db.is_transient(pyodbc.Error(*args)) is expected


# --- retry behaviour -----------------------------------------------------------------

def test_retries_temporary_errors_then_succeeds(monkeypatch, clock):
    sentinel = object()
    calls = scripted_connect(monkeypatch, clock, [TIMEOUT_ERROR, PAUSED_ERROR, sentinel])

    assert db.get_connection(max_wait_seconds=90) is sentinel
    assert len(calls) == 3
    assert clock.sleeps == [2, 4]


def test_never_retries_a_login_failure(monkeypatch, clock):
    calls = scripted_connect(monkeypatch, clock, [LOGIN_FAILED])

    with pytest.raises(pyodbc.Error):
        db.get_connection(max_wait_seconds=90)

    assert len(calls) == 1
    assert clock.sleeps == []


def test_default_is_a_single_attempt(monkeypatch, clock):
    calls = scripted_connect(monkeypatch, clock, [TIMEOUT_ERROR])

    with pytest.raises(pyodbc.Error):
        db.get_connection()

    assert len(calls) == 1
    assert clock.sleeps == []


def test_gives_up_when_the_budget_is_spent(monkeypatch, clock):
    start = clock.now
    calls = scripted_connect(monkeypatch, clock, [TIMEOUT_ERROR])  # fails forever

    with pytest.raises(pyodbc.Error):
        db.get_connection(max_wait_seconds=90)

    assert len(calls) == 3  # 30s attempt, wait 2, 30s attempt, wait 4, 30s attempt, out of budget
    assert clock.now - start <= 90 + 30  # never overshoots by more than one attempt


def test_waits_double_and_are_capped(monkeypatch, clock):
    calls = scripted_connect(monkeypatch, clock, [TIMEOUT_ERROR] * 7 + [object()], attempt_seconds=0)

    db.get_connection(max_wait_seconds=1000)

    assert clock.sleeps == [2, 4, 8, 16, 16, 16, 16]
    assert len(calls) == 8


def test_error_raised_after_giving_up_is_the_real_one(monkeypatch, clock):
    scripted_connect(monkeypatch, clock, [TIMEOUT_ERROR])

    with pytest.raises(pyodbc.Error) as caught:
        db.get_connection(max_wait_seconds=60)

    assert "258" in str(caught.value)


# --- who uses the patient mode -------------------------------------------------------

def test_api_requests_get_the_retry_budget_and_the_connection_is_closed(monkeypatch):
    seen = {}

    class FakeConn:
        closed = False

        def close(self):
            self.closed = True

    conn = FakeConn()

    def fake_get_connection(max_wait_seconds=0.0):
        seen["budget"] = max_wait_seconds
        return conn

    monkeypatch.setattr(db, "get_connection", fake_get_connection)

    gen = db.get_db()
    assert next(gen) is conn
    assert seen["budget"] == db.REQUEST_RETRY_BUDGET_SECONDS
    with pytest.raises(StopIteration):
        next(gen)
    assert conn.closed is True


def test_health_check_makes_a_single_attempt(monkeypatch, clock):
    calls = scripted_connect(monkeypatch, clock, [TIMEOUT_ERROR])

    assert db.check_db() is False
    assert len(calls) == 1
    assert clock.sleeps == []


def test_connection_timeout_per_attempt_is_in_the_connection_string(monkeypatch, clock):
    calls = scripted_connect(monkeypatch, clock, [object()])

    db.get_connection()

    assert f"Connection Timeout={db.ATTEMPT_TIMEOUT_SECONDS}" in calls[0]
