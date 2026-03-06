from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import check_db_connection, init_db

configure_logging()

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


@app.get("/health/live", tags=["system"])
async def liveness() -> dict[str, str]:
    return {"status": "alive", "service": settings.app_name}


@app.get("/health/ready", tags=["system"])
async def readiness():
    db_ok = check_db_connection()
    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": settings.app_name,
                "checks": {"database": "down"},
            },
        )
    return {"status": "ready", "service": settings.app_name, "checks": {"database": "ok"}}
