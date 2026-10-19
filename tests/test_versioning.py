import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_item_routes_live_under_v1():
    paths = client.get("/openapi.json").json()["paths"]

    item_paths = [p for p in paths if "items" in p]
    assert item_paths, "no item routes found"
    assert all(p.startswith("/v1/items") for p in item_paths)


@pytest.mark.parametrize("path", ["/items", "/items/1", "/v2/items"])
def test_unversioned_and_unknown_versions_are_not_served(path):
    # Not served at all: 404 (not 401) because no such route exists
    assert client.get(path, headers={"X-API-Key": "anything"}).status_code == 404


@pytest.mark.parametrize("path", ["/health", "/health/db"])
def test_operational_endpoints_are_not_versioned(path):
    paths = client.get("/openapi.json").json()["paths"]

    assert path in paths
    assert f"/v1{path}" not in paths
