from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)

from apps.api.dependencies import get_collection_service
from apps.api.schemas.filmium_collections import (
    CollectionCreateRequest,
    CollectionResponse,
)
from core.domains.filmium.collection_service import (
    CollectionNotFoundError,
    CollectionService,
    CollectionValidationError,
)
from core.domains.filmium.service import MediaItemNotFoundError

# ==========          COLLECTION ROUTER          ==========

router = APIRouter(
    prefix="/api/v1/filmium",
    tags=["FILMIUM Collections"],
)

CollectionServiceDependency = Annotated[
    CollectionService,
    Depends(get_collection_service),
]


# ==========          COLLECTION CRUD          ==========

@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_collection(
    request: CollectionCreateRequest,
    service: CollectionServiceDependency,
) -> CollectionResponse:
    """Kreira novu FILMIUM kolekciju."""

    try:
        collection = service.create_collection(
            request.to_domain()
        )
    except CollectionValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return CollectionResponse.from_domain(collection)


@router.get(
    "/collections",
    response_model=list[CollectionResponse],
)
def list_collections(
    service: CollectionServiceDependency,
) -> list[CollectionResponse]:
    """Vraća sve FILMIUM kolekcije."""

    return [
        CollectionResponse.from_domain(collection)
        for collection in service.list_collections()
    ]


@router.get(
    "/collections/{collection_id}",
    response_model=CollectionResponse,
)
def get_collection(
    collection_id: int,
    service: CollectionServiceDependency,
) -> CollectionResponse:
    """Vraća jednu FILMIUM kolekciju."""

    try:
        collection = service.get_collection(collection_id)
    except CollectionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return CollectionResponse.from_domain(collection)


@router.delete(
    "/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_collection(
    collection_id: int,
    service: CollectionServiceDependency,
) -> Response:
    """Briše FILMIUM kolekciju."""

    try:
        service.delete_collection(collection_id)
    except CollectionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========          COLLECTION ČLANSTVO          ==========

@router.post(
    "/collections/{collection_id}/media/{item_id}",
    response_model=CollectionResponse,
)
def add_media_to_collection(
    collection_id: int,
    item_id: int,
    service: CollectionServiceDependency,
) -> CollectionResponse:
    """Dodaje FILMIUM sadržaj u kolekciju."""

    try:
        collection = service.add_media_item(
            collection_id,
            item_id,
        )
    except CollectionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except MediaItemNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return CollectionResponse.from_domain(collection)


@router.delete(
    "/collections/{collection_id}/media/{item_id}",
    response_model=CollectionResponse,
)
def remove_media_from_collection(
    collection_id: int,
    item_id: int,
    service: CollectionServiceDependency,
) -> CollectionResponse:
    """Uklanja FILMIUM sadržaj iz kolekcije."""

    try:
        collection = service.remove_media_item(
            collection_id,
            item_id,
        )
    except CollectionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return CollectionResponse.from_domain(collection)