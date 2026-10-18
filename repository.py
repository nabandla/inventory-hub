import pyodbc

# Column list is a constant (never built from user input). Values always go in as ? parameters.
COLUMNS = ("id", "sku", "name", "quantity", "created_at", "updated_at")
_INSERTED = ", ".join(f"INSERTED.{c}" for c in COLUMNS)
_SELECT = ", ".join(COLUMNS)

# SQL Server error numbers for UNIQUE constraint / unique index violations
_UNIQUE_VIOLATION_CODES = ("2627", "2601")


class DuplicateSkuError(Exception):
    def __init__(self, sku: str):
        super().__init__(f"SKU already exists: {sku}")
        self.sku = sku


def _to_dict(row) -> dict:
    return dict(zip(COLUMNS, row))


class ItemRepository:
    """All SQL for the items table. Takes an open connection; the caller closes it."""

    def __init__(self, conn):
        self._conn = conn

    def create(self, sku: str, name: str, quantity: int) -> dict:
        cur = self._conn.cursor()
        try:
            cur.execute(
                f"INSERT INTO dbo.items (sku, name, quantity) OUTPUT {_INSERTED} VALUES (?, ?, ?)",
                sku, name, quantity,
            )
            row = cur.fetchone()
            self._conn.commit()
        except pyodbc.IntegrityError as exc:
            self._conn.rollback()
            if any(code in str(exc) for code in _UNIQUE_VIOLATION_CODES):
                raise DuplicateSkuError(sku) from exc
            raise
        except Exception:
            self._conn.rollback()
            raise
        return _to_dict(row)

    def get(self, item_id: int) -> dict | None:
        cur = self._conn.cursor()
        cur.execute(f"SELECT {_SELECT} FROM dbo.items WHERE id = ?", item_id)
        row = cur.fetchone()
        return _to_dict(row) if row else None

    def list(self, limit: int, offset: int) -> list[dict]:
        cur = self._conn.cursor()
        cur.execute(
            f"SELECT {_SELECT} FROM dbo.items ORDER BY id OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            offset, limit,
        )
        return [_to_dict(row) for row in cur.fetchall()]

    def update(self, item_id: int, name: str, quantity: int) -> dict | None:
        cur = self._conn.cursor()
        try:
            cur.execute(
                "UPDATE dbo.items SET name = ?, quantity = ?, updated_at = SYSUTCDATETIME() "
                f"OUTPUT {_INSERTED} WHERE id = ?",
                name, quantity, item_id,
            )
            row = cur.fetchone()
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return _to_dict(row) if row else None

    def delete(self, item_id: int) -> bool:
        cur = self._conn.cursor()
        try:
            cur.execute("DELETE FROM dbo.items WHERE id = ?", item_id)
            deleted = cur.rowcount > 0
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return deleted
