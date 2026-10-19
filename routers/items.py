from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from auth import require_api_key
from db import get_db
from repository import DuplicateSkuError, ItemRepository
from schemas import Item, ItemCreate, ItemUpdate

# The guard on the router protects every current and future /items route
router = APIRouter(prefix="/items", tags=["items"], dependencies=[Depends(require_api_key)])

ItemId = Path(gt=0, description="Item id")


def get_repository(conn=Depends(get_db)) -> ItemRepository:
    return ItemRepository(conn)


@router.post("", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, repo: ItemRepository = Depends(get_repository)):
    try:
        return repo.create(payload.sku, payload.name, payload.quantity)
    except DuplicateSkuError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="An item with this SKU already exists")


@router.get("", response_model=list[Item])
def list_items(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: ItemRepository = Depends(get_repository),
):
    return repo.list(limit, offset)


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int = ItemId, repo: ItemRepository = Depends(get_repository)):
    item = repo.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.put("/{item_id}", response_model=Item)
def update_item(
    payload: ItemUpdate,
    item_id: int = ItemId,
    repo: ItemRepository = Depends(get_repository),
):
    item = repo.update(item_id, payload.name, payload.quantity)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int = ItemId, repo: ItemRepository = Depends(get_repository)):
    if not repo.delete(item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
