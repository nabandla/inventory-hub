import pyodbc
import pytest
from fastapi.testclient import TestClient

import main
from routers.items import get_repository
from tests.fakes import InMemoryItemRepository


@pytest.fixture
def repo():
    return InMemoryItemRepository()


@pytest.fixture
def client(repo):
    main.app.dependency_overrides[get_repository] = lambda: repo
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def make_item(client, sku="SKU-1", name="Widget", quantity=5):
    return client.post("/items", json={"sku": sku, "name": name, "quantity": quantity})


def test_create_item_returns_201_and_item(client):
    response = make_item(client)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert (body["sku"], body["name"], body["quantity"]) == ("SKU-1", "Widget", 5)
    assert "created_at" in body and "updated_at" in body


def test_create_item_quantity_defaults_to_zero(client):
    response = client.post("/items", json={"sku": "A", "name": "No qty"})

    assert response.status_code == 201
    assert response.json()["quantity"] == 0


def test_create_item_trims_whitespace(client):
    response = make_item(client, sku="  SKU-9  ", name="  Bolt  ")

    assert response.json()["sku"] == "SKU-9"
    assert response.json()["name"] == "Bolt"


@pytest.mark.parametrize(
    "payload",
    [
        {"sku": "", "name": "x", "quantity": 1},
        {"sku": "   ", "name": "x", "quantity": 1},
        {"sku": "A", "name": "", "quantity": 1},
        {"sku": "A", "name": "x", "quantity": -1},
        {"sku": "A", "name": "x", "quantity": "many"},
        {"sku": "S" * 51, "name": "x", "quantity": 1},
        {"name": "missing sku", "quantity": 1},
    ],
)
def test_create_item_rejects_invalid_input(client, payload):
    assert client.post("/items", json=payload).status_code == 422


def test_create_duplicate_sku_returns_409(client):
    make_item(client, sku="DUP")

    response = make_item(client, sku="DUP", name="Other")

    assert response.status_code == 409
    assert response.json() == {"detail": "An item with this SKU already exists"}


def test_get_item(client):
    make_item(client)

    response = client.get("/items/1")

    assert response.status_code == 200
    assert response.json()["sku"] == "SKU-1"


def test_get_missing_item_returns_404(client):
    response = client.get("/items/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


@pytest.mark.parametrize("bad_id", ["0", "-5", "abc"])
def test_get_item_rejects_bad_id(client, bad_id):
    assert client.get(f"/items/{bad_id}").status_code == 422


def test_list_items_in_id_order_with_pagination(client):
    for n in range(1, 6):
        make_item(client, sku=f"S{n}", name=f"Item {n}")

    everything = client.get("/items").json()
    page = client.get("/items", params={"limit": 2, "offset": 2}).json()

    assert [i["sku"] for i in everything] == ["S1", "S2", "S3", "S4", "S5"]
    assert [i["sku"] for i in page] == ["S3", "S4"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_list_items_rejects_bad_paging(client, params):
    assert client.get("/items", params=params).status_code == 422


def test_list_items_empty(client):
    assert client.get("/items").json() == []


def test_update_item(client):
    make_item(client)

    response = client.put("/items/1", json={"name": "Widget v2", "quantity": 42})

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["quantity"], body["sku"]) == ("Widget v2", 42, "SKU-1")
    assert client.get("/items/1").json()["quantity"] == 42


def test_update_missing_item_returns_404(client):
    response = client.put("/items/999", json={"name": "x", "quantity": 1})

    assert response.status_code == 404


def test_update_rejects_negative_quantity(client):
    make_item(client)

    assert client.put("/items/1", json={"name": "x", "quantity": -3}).status_code == 422


def test_delete_item_then_gone(client):
    make_item(client)

    first = client.delete("/items/1")
    second = client.delete("/items/1")

    assert first.status_code == 204
    assert first.content == b""
    assert second.status_code == 404
    assert client.get("/items/1").status_code == 404


def test_database_failure_returns_503_without_details(client, monkeypatch):
    class BrokenRepo:
        def list(self, limit, offset):
            raise pyodbc.Error("08001", "[secret-server.database.windows.net] login failed for user 'x'")

    main.app.dependency_overrides[get_repository] = lambda: BrokenRepo()

    response = TestClient(main.app).get("/items")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "secret" not in response.text
