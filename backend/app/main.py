"""FastAPI application: CORS, routers and the background offline checker.

Run (from the backend/ folder):  ..\\.venv\\Scripts\\uvicorn app.main:app --reload
Interactive API docs:            http://localhost:8000/docs
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.alerts import check_offline_nodes
from app.config import settings
from app.db import SessionLocal, utcnow
from app.routers import alert_rules, alerts, auth, dashboard, ingest, nodes, readings

log = logging.getLogger("slope_monitor")


def _run_offline_check() -> int:
    db = SessionLocal()
    try:
        return check_offline_nodes(db, utcnow())
    finally:
        db.close()


async def offline_checker() -> None:
    """Every OFFLINE_CHECK_INTERVAL_S seconds, open alerts for nodes that went quiet."""
    while True:
        try:
            opened = await asyncio.to_thread(_run_offline_check)
            if opened:
                log.info("Opened %d offline alert(s)", opened)
        except Exception:  # keep the loop alive whatever happens
            log.exception("Offline check failed")
        await asyncio.sleep(settings.OFFLINE_CHECK_INTERVAL_S)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Start the background task when the server starts, stop it on shutdown.
    task = asyncio.create_task(offline_checker())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="Slope Monitor API",
    description="Multi-node slope monitoring dashboard (ENGG4601 thesis prototype).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, dashboard, nodes, alert_rules, readings, alerts, ingest):
    app.include_router(module.router)


@app.get("/api/health", tags=["health"])
def health() -> dict:
    """Simple check that the server is running (no login needed)."""
    return {"status": "ok", "time": utcnow()}
