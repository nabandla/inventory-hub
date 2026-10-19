from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

Sku = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ItemCreate(BaseModel):
    sku: Sku
    name: Name
    quantity: int = Field(default=0, ge=0)


class ItemUpdate(BaseModel):
    # The SKU is the item's business identity and is deliberately not editable.
    name: Name
    quantity: int = Field(ge=0)


class ErrorResponse(BaseModel):
    """Shape of every error this API returns on purpose (401, 404, 409, 503)."""

    detail: str


class Item(BaseModel):
    id: int
    sku: str
    name: str
    quantity: int
    created_at: datetime
    updated_at: datetime
