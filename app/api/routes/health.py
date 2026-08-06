from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.dependencies import SessionDep

router = APIRouter(tags=["operations"])


@router.get("/health")
async def health(session: SessionDep):
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status.HTTP_503_SERVICE_UNAVAILABLE, {"status": "unhealthy"})
    return {"status": "healthy"}

