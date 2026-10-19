"""Runs the real SQL against the Azure SQL dev database.

Needs a working .env and the items table (db/002_create_items_table.sql).
Excluded by default (and in CI). Run locally with:  pytest -m integration
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

import main
from db import get_connection
from repository import DuplicateSkuError, ItemRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    conn = get_connection()
    try:
        yield ItemRepository(conn)
    finally:
        conn.close()


@pytest.fixture
def sku(repo):
    value = f"TEST-{uuid.uuid4().hex[:12]}"
    yield value
    # Clean up whatever the test created
    cur = repo._conn.cursor()
    cur.execute("DELETE FROM dbo.items WHERE sku = ?", value)
    repo._conn.commit()


def test_repository_full_lifecycle(repo, sku):
    created = repo.create(sku, "Integration widget", 7)
    assert created["id"] > 0 and created["quantity"] == 7

    assert repo.get(created["id"])["sku"] == sku
    assert any(i["id"] == created["id"] for i in repo.list(limit=100, offset=0))

    updated = repo.update(created["id"], "Renamed", 9)
    assert (updated["name"], updated["quantity"]) == ("Renamed", 9)
    assert updated["updated_at"] >= created["updated_at"]

    assert repo.delete(created["id"]) is True
    assert repo.get(created["id"]) is None
    assert repo.delete(created["id"]) is False


def test_duplicate_sku_is_detected(repo, sku):
    repo.create(sku, "First", 1)

    with pytest.raises(DuplicateSkuError):
        repo.create(sku, "Second", 2)


def test_database_rejects_negative_quantity(repo, sku):
    import pyodbc

    with pytest.raises(pyodbc.IntegrityError):
        repo.create(sku, "Negative", -1)


def test_api_end_to_end_against_real_database(sku):
    client = TestClient(main.app, headers={"X-API-Key": os.environ["API_KEY"]})

    created = client.post("/v1/items", json={"sku": sku, "name": "E2E", "quantity": 3})
    assert created.status_code == 201
    item_id = created.json()["id"]

    assert client.get(f"/v1/items/{item_id}").json()["name"] == "E2E"
    assert client.post("/v1/items", json={"sku": sku, "name": "Again"}).status_code == 409
    assert client.put(f"/v1/items/{item_id}", json={"name": "E2E v2", "quantity": 4}).json()["quantity"] == 4
    assert client.delete(f"/v1/items/{item_id}").status_code == 204
    assert client.get(f"/v1/items/{item_id}").status_code == 404
