"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.db import init_db, session_scope
from app.services.data_loader import seed_all
from app.triggers.engine import run_detection
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    if settings.seed_on_startup:
        with session_scope() as db:
            seed_all(db)
            # Run initial detection so API has results on first request
            run_detection(db, settings.default_workspace)
            # Materialize actions for stable IDs in scenarios/overrides
            from app.services.scenario import materialize_actions
            materialize_actions(db, settings.default_workspace)
    yield
    # Shutdown — nothing needed for SQLite


app = FastAPI(
    title="Yield Intelligence",
    description="Marketing ROI, budget optimization, and transformation accelerator.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api")
def api_root():
    return {
        "name": "Yield Intelligence API",
        "version": "0.1.0",
        "environment": settings.environment,
        "docs": "/docs",
    }


# Serve the built React SPA from backend/static (populated during build)
# Railway build step runs `npm run build && cp -r frontend/dist backend/static`
STATIC_DIR = Path(__file__).parent.parent / "static"

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(STATIC_DIR / "assets")),
        name="assets",
    )

    # Serve favicon and other root-level static files
    @app.get("/favicon.svg")
    def favicon():
        return FileResponse(STATIC_DIR / "favicon.svg")

    # SPA fallback — any non-API path returns index.html
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # API paths handled by router; anything else serves the SPA
        if full_path.startswith("api/") or full_path.startswith("v1/") or full_path.startswith("admin/"):
            return {"detail": "Not Found"}, 404
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    def root():
        return {
            "name": "Yield Intelligence API",
            "version": "0.1.0",
            "environment": settings.environment,
            "docs": "/docs",
            "note": "Frontend not built. Run `npm run build && cp -r frontend/dist backend/static` to enable SPA.",
        }
