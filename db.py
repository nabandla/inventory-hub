import logging
import os
from contextlib import closing

import pyodbc
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REQUIRED_SETTINGS = ("DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_DRIVER")


def get_connection():
    """Open a new connection to Azure SQL using settings from the environment/.env."""
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
        "Connection Timeout=60"  # serverless DB may need a while to wake from auto-pause
    )
    return pyodbc.connect(conn_str)


def check_db() -> bool:
    """Return True if the database answers SELECT 1, False otherwise (never raises)."""
    try:
        # closing() guarantees conn.close() even if the query fails
        with closing(get_connection()) as conn:
            return conn.cursor().execute("SELECT 1").fetchone()[0] == 1
    except (pyodbc.Error, RuntimeError):
        # Full detail goes to the server log only, never to the caller of the API
        logger.exception("Database health check failed")
        return False
