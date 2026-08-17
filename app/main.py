from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import install_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.mount("/metrics", make_asgi_app())
    install_exception_handlers(app)
    app.include_router(api_router)

    # Container platforms can serve the compiled React application and API
    # from one origin. API routes are registered first so the SPA fallback can
    # never shadow authentication, document, chat, health, or metrics routes.
    frontend = Path("/app/frontend-dist")
    if frontend.is_dir():
        assets = frontend / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def frontend_fallback(path: str) -> FileResponse:
            candidate = (frontend / path).resolve()
            if candidate.is_file() and frontend in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(frontend / "index.html")

    return app


app = create_app()
