from __future__ import annotations

import mimetypes

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import Base, engine
from ..seed import seed_database
from .routes.auth import router as auth_router
from .routes.admin import router as admin_router
from .routes.catalog import router as catalog_router
from .routes.orders import router as orders_router
from .routes.quotes import router as quotes_router
from .routes.research import router as research_router


settings = get_settings()
mimetypes.add_type("image/webp", ".webp")


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.cors_origins == "*" else [origin.strip() for origin in settings.cors_origins.split(",")],
        allow_credentials=False if settings.cors_origins == "*" else True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    legacy_media_path = settings.resolved_legacy_media_path()
    if legacy_media_path.exists():
        app.mount(settings.media_url_path, StaticFiles(directory=legacy_media_path), name="media")

    @app.on_event("startup")
    def on_startup() -> None:
        Base.metadata.create_all(bind=engine)
        with Session(bind=engine) as session:
            seed_database(
                session,
                settings.resolved_legacy_sqlite_path(),
                settings.resolved_supply_chain_csv_path(),
            )

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(catalog_router)
    app.include_router(quotes_router)
    app.include_router(orders_router)
    app.include_router(research_router)
    return app


app = create_app()
