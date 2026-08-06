import logging
from time import monotonic
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import request_id_ctx, user_id_ctx
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS

logger = logging.getLogger("app.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = monotonic()
        request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
        request_token = request_id_ctx.set(request_id)
        user_token = user_id_ctx.set(None)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", request.url.path)
            elapsed = monotonic() - started
            HTTP_REQUESTS.labels(request.method, route, str(status_code)).inc()
            HTTP_LATENCY.labels(request.method, route).observe(elapsed)
            logger.info(
                "http_request_completed",
                extra={
                    "method": request.method,
                    "route": route,
                    "status_code": status_code,
                    "latency_ms": round(elapsed * 1000, 2),
                    "client_ip": request.client.host if request.client else None,
                },
            )
            request_id_ctx.reset(request_token)
            user_id_ctx.reset(user_token)
