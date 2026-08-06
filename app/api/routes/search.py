from fastapi import APIRouter

from app.api.dependencies import CurrentUser, RetrievalServiceDep, SessionDep
from app.repositories.document import DocumentRepository
from app.schemas.search import SearchRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    user: CurrentUser,
    session: SessionDep,
    service: RetrievalServiceDep,
) -> SearchResponse:
    items = await service.search(
        payload.query, user, DocumentRepository(session), payload.mode, payload.filters
    )
    return SearchResponse(items=items)
