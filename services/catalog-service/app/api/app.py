from __future__ import annotations

import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import Base, engine
from ..observability import configure_error_monitoring
from ..security import (
    BrowserSecurityMiddleware,
    RequestLoggingMiddleware,
    configure_request_logging,
)
from ..seed import seed_database
from .routes.auth import router as auth_router
from .routes.admin import router as admin_router
from .routes.admin_analytics import router as admin_analytics_router
from .routes.admin_operations import router as admin_operations_router
from .routes.catalog import router as catalog_router
from .routes.customer import router as customer_router
from .routes.orders import router as orders_router
from .routes.quotes import router as quotes_router
from .routes.research import router as research_router


mimetypes.add_type("image/webp", ".webp")


def _initialize_database(runtime_settings: Settings) -> None:
    # Production schema changes are an explicit deployment step (Alembic), never
    # an implicit application side effect.
    if runtime_settings.is_production:
        return
    Base.metadata.create_all(bind=engine)
    with Session(bind=engine) as session:
        seed_database(
            session,
            None,
            runtime_settings.resolved_supply_chain_csv_path(),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _initialize_database(app.state.catalog_settings)
    yield


def create_app(app_settings: Settings | None = None) -> FastAPI:
    runtime_settings = app_settings or get_settings()
    runtime_settings.validate_runtime_security()
    monitoring_enabled = configure_error_monitoring(runtime_settings)
    configure_request_logging(runtime_settings.request_log_level)
    app = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        redirect_slashes=False,
        docs_url=None if runtime_settings.is_production else "/docs",
        redoc_url=None if runtime_settings.is_production else "/redoc",
        openapi_url=None if runtime_settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.catalog_settings = runtime_settings
    app.state.error_monitoring_enabled = monitoring_enabled
    cors_origins = (
        ["*"]
        if runtime_settings.cors_origins.strip() == "*"
        else list(runtime_settings.allowed_browser_origins)
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_origins != ["*"],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(BrowserSecurityMiddleware, settings=runtime_settings)
    # Add last so even origin rejections receive a correlation ID and request log.
    app.add_middleware(RequestLoggingMiddleware)

    media_path = runtime_settings.resolved_media_path()
    if media_path.exists():
        app.mount(runtime_settings.media_url_path, StaticFiles(directory=media_path), name="media")

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(admin_operations_router)
    app.include_router(admin_analytics_router)
    app.include_router(catalog_router)
    app.include_router(customer_router)
    app.include_router(quotes_router)
    app.include_router(orders_router)
    app.include_router(research_router)
    return app


app = create_app()
