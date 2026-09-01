import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.db import get_session_factory
from app.db.seed import seed_world
from app.api.websocket import router as ws_router
from app.api.health import router as health_router

logger = logging.getLogger(__name__)

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown."""
    logger.info("🎮 MUD Server starting...")
    async with get_session_factory()() as session:
        async with session.begin():
            await seed_world(session)
    yield
    logger.info("🎮 MUD Server shutting down...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="AI-Enhanced MUD",
        description="Multiplayer text-based game with AI enhancements",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health_router, tags=["health"])
    app.include_router(ws_router, tags=["game"])

    return app


app = create_app()
