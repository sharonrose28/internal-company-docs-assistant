import logging

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.core.metrics import PERMISSION_FAILURES

logger = structlog.get_logger()
security_logger = logging.getLogger("app.authorization")


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__("not_found", message, status.HTTP_404_NOT_FOUND)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__("forbidden", message, status.HTTP_403_FORBIDDEN)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            PERMISSION_FAILURES.labels(request.url.path).inc()
            security_logger.warning(
                "permission_denied",
                extra={"operation": request.url.path, "method": request.method},
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        await logger.aexception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "internal_error", "message": "An internal error occurred"}},
        )
