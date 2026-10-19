import logging
import os
import re
import time
from contextlib import closing

import pyodbc
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REQUIRED_SETTINGS = ("DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_DRIVER")

# --- Retry settings -------------------------------------------------------------------
# A serverless database auto-pauses when idle and needs a while to wake up; connections
# made meanwhile fail with temporary errors. API requests wait for it, patiently.
ATTEMPT_TIMEOUT_SECONDS = 30  # how long ONE connection attempt may take
REQUEST_RETRY_BUDGET_SECONDS = 90  # total time an API request may spend waiting for the DB
INITIAL_RETRY_DELAY_SECONDS = 2
MAX_RETRY_DELAY_SECONDS = 16

# SQLSTATEs that describe "could not connect / timed out / link broke"
_TRANSIENT_SQLSTATES = {"08001", "08S01", "HYT00", "HYT01"}
# SQL Server / Azure SQL error numbers that mean "try again shortly":
# 258 login timeout, 40613 database not currently available (paused/resuming),
# 40197/40501 service busy, 49918-49920 not enough resources right now
_TRANSIENT_ERROR_NUMBERS = {"258", "40613", "40197", "40501", "49918", "49919", "49920"}


def _now() -> float:
    return time.monotonic()


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def is_transient(exc: pyodbc.Error) -> bool:
    """True only for temporary failures worth retrying. Never retries a login failure."""
    parts = [str(a) for a in exc.args]
    sqlstate = parts[0] if parts else ""
    message = " ".join(parts)

    # Wrong credentials fail identically every time; retrying only wastes time
    if sqlstate.startswith("28") or "login failed for user" in message.lower():
        return False

    numbers = set(re.findall(r"\((\d{2,6})\)", message))
    if numbers & _TRANSIENT_ERROR_NUMBERS:
        return True
    return sqlstate in _TRANSIENT_SQLSTATES


def _connect_with_retry(conn_str: str, max_wait_seconds: float):
    """pyodbc.connect, retrying temporary errors with doubling waits until the budget is spent."""
    deadline = _now() + max_wait_seconds
    delay = INITIAL_RETRY_DELAY_SECONDS
    attempt = 1
    while True:
        try:
            return pyodbc.connect(conn_str)
        except pyodbc.Error as exc:
            remaining = deadline - _now()
            if not is_transient(exc) or remaining <= delay:
                raise
            logger.warning(
                "Temporary database error on attempt %d, retrying in %ds (%.0fs left in budget): %s",
                attempt, delay, remaining, exc.args[0] if exc.args else "unknown",
            )
            _sleep(delay)
            delay = min(delay * 2, MAX_RETRY_DELAY_SECONDS)
            attempt += 1


def get_connection(max_wait_seconds: float = 0.0):
    """Open a new connection to Azure SQL using settings from the environment/.env.

    By default makes ONE attempt. Pass max_wait_seconds to retry temporary errors.
    """
    missing = [key for key in REQUIRED_SETTINGS if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")

    # Braces make ';' and spaces in a value safe; a literal '}' is escaped by doubling it.
    password = os.environ["DB_PASSWORD"].replace("}", "}}")
    conn_str = (
        f"DRIVER={{{os.environ['DB_DRIVER']}}};"
        f"SERVER={os.environ['DB_SERVER']};"
        f"DATABASE={os.environ['DB_NAME']};"
        f"UID={os.environ['DB_USER']};"
        f"PWD={{{password}}};"
        "Encrypt=yes;TrustServerCertificate=no;"
        f"Connection Timeout={ATTEMPT_TIMEOUT_SECONDS}"
    )
    return _connect_with_retry(conn_str, max_wait_seconds)


def get_db():
    """FastAPI dependency: one connection per request, always closed afterwards.

    Waits patiently (with retries) if the serverless database is waking up.
    """
    conn = get_connection(max_wait_seconds=REQUEST_RETRY_BUDGET_SECONDS)
    try:
        yield conn
    finally:
        conn.close()


def check_db() -> bool:
    """Return True if the database answers SELECT 1, False otherwise (never raises).

    A health probe makes a single attempt: it must report the truth quickly, not hide it.
    """
    try:
        # closing() guarantees conn.close() even if the query fails
        with closing(get_connection()) as conn:
            return conn.cursor().execute("SELECT 1").fetchone()[0] == 1
    except (pyodbc.Error, RuntimeError):
        # Full detail goes to the server log only, never to the caller of the API
        logger.exception("Database health check failed")
        return False
