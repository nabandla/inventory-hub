from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from auth import READ_ROLE, WRITE_ROLE, require_role
from db import get_db
from repository import DuplicateSkuError, ItemRepository
from schemas import ErrorResponse, Item, ItemCreate, ItemUpdate

# Every operation below names the role it needs. tests/test_auth.py also proves that EVERY
# /v1 operation in the published contract refuses a request without a token, so a new route
# cannot be added unprotected by accident.
router = APIRouter(
    prefix="/v1/items",
    tags=["items"],
    responses={
        401: {"model": ErrorResponse, "description": "Missing, invalid or expired access token"},
        403: {"model": ErrorResponse, "description": "Valid token, but it lacks the required role"},
        503: {"model": ErrorResponse, "description": "Database or authentication service unavailable"},
    },
)

ItemId = Path(gt=0, description="Item id")

NOT_FOUND = {404: {"model": ErrorResponse, "description": "No item with this id"}}

can_read = [Depends(require_role(READ_ROLE))]
can_write = [Depends(require_role(WRITE_ROLE))]


def get_repository(conn=Depends(get_db)) -> ItemRepository:
    return ItemRepository(conn)


@router.post(
    "",
    response_model=Item,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item (role Items.Write)",
    dependencies=can_write,
    responses={409: {"model": ErrorResponse, "description": "An item with this SKU already exists"}},
)
def create_item(payload: ItemCreate, repo: ItemRepository = Depends(get_repository)):
    try:
        return repo.create(payload.sku, payload.name, payload.quantity)
    except DuplicateSkuError:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="An item with this SKU already exists")


@router.get(
    "",
    response_model=list[Item],
    summary="List items, ordered by id, paged (role Items.Read)",
    dependencies=can_read,
)
def list_items(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: ItemRepository = Depends(get_repository),
):
    return repo.list(limit, offset)


@router.get(
    "/{item_id}",
    response_model=Item,
    summary="Get one item (role Items.Read)",
    dependencies=can_read,
    responses=NOT_FOUND,
)
def get_item(item_id: int = ItemId, repo: ItemRepository = Depends(get_repository)):
    item = repo.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.put(
    "/{item_id}",
    response_model=Item,
    summary="Update an item's name and quantity; the SKU cannot change (role Items.Write)",
    dependencies=can_write,
    responses=NOT_FOUND,
)
def update_item(
    payload: ItemUpdate,
    item_id: int = ItemId,
    repo: ItemRepository = Depends(get_repository),
):
    item = repo.update(item_id, payload.name, payload.quantity)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item (role Items.Write)",
    dependencies=can_write,
    responses=NOT_FOUND,
)
def delete_item(item_id: int = ItemId, repo: ItemRepository = Depends(get_repository)):
    if not repo.delete(item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
