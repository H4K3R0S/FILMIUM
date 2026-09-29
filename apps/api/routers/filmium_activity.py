from typing import Annotated

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_activity_service
from apps.api.schemas.filmium_activity import ActivityItemResponse
from core.domains.filmium.activity_service import ActivityService

# ==========          FILMIUM ACTIVITY ROUTER          ==========

router = APIRouter(
    prefix="/api/v1/filmium",
    tags=["FILMIUM Activity"],
)

ActivityServiceDependency = Annotated[
    ActivityService,
    Depends(get_activity_service),
]


# ==========          FILMIUM ISTORIJA AKTIVNOSTI          ==========

@router.get(
    "/activity",
    response_model=list[ActivityItemResponse],
)
def list_activity(
    service: ActivityServiceDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ActivityItemResponse]:
    """Vraća najnovije FILMIUM activity događaje."""

    return [
        ActivityItemResponse.from_domain(activity)
        for activity in service.list_recent_events(limit)
    ]