from datetime import datetime, timezone

from repository import DuplicateSkuError


class InMemoryItemRepository:
    """Same interface as ItemRepository, but backed by a dict. Used to test the API without a database."""

    def __init__(self):
        self._items: dict[int, dict] = {}
        self._next_id = 1

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)

    def create(self, sku, name, quantity):
        if any(i["sku"] == sku for i in self._items.values()):
            raise DuplicateSkuError(sku)
        now = self._now()
        item = {"id": self._next_id, "sku": sku, "name": name, "quantity": quantity,
                "created_at": now, "updated_at": now}
        self._items[self._next_id] = item
        self._next_id += 1
        return dict(item)

    def get(self, item_id):
        item = self._items.get(item_id)
        return dict(item) if item else None

    def list(self, limit, offset):
        ordered = [self._items[k] for k in sorted(self._items)]
        return [dict(i) for i in ordered[offset:offset + limit]]

    def update(self, item_id, name, quantity):
        item = self._items.get(item_id)
        if not item:
            return None
        item.update(name=name, quantity=quantity, updated_at=self._now())
        return dict(item)

    def delete(self, item_id):
        return self._items.pop(item_id, None) is not None
