from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.database import init_db
from app.monitor import wake_monitor
from app.routers import groups, history, machines, scheduled, wake
from app.scheduler import init_scheduler, shutdown_scheduler
from app.wol import WOL_INTERFACE, WOL_METHOD, get_wol_info


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting PyWol server...")
    logger.info(f"WOL method: {WOL_METHOD} | interface: {WOL_INTERFACE or 'default'}")
    await init_db()
    await init_scheduler()
    yield
    await wake_monitor.shutdown()
    await shutdown_scheduler()
    logger.info("PyWol server stopped.")


app = FastAPI(title="PyWol", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(machines.router, prefix="/api/machines", tags=["machines"])
app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
app.include_router(wake.router, prefix="/api/wake", tags=["wake"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(scheduled.router, prefix="/api/scheduled", tags=["scheduled"])

# System info endpoint
@app.get("/api/system/info")
async def system_info():
    """Return system and WOL configuration info."""
    return {
        "version": "0.1.0",
        "wol": get_wol_info(),
    }


# Serve frontend static files (built Quasar SPA)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


def main():
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
