from fastapi import APIRouter

from app.api.routes.assets import router as assets_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.evals import router as evals_router
from app.api.routes.release_gates import router as release_gates_router
from app.api.routes.telemetry import router as telemetry_router

api_router = APIRouter()
api_router.include_router(assets_router, prefix="/assets", tags=["assets"])
api_router.include_router(datasets_router, prefix="/datasets", tags=["datasets"])
api_router.include_router(evals_router, prefix="/evals", tags=["evals"])
api_router.include_router(release_gates_router, prefix="/release-gates", tags=["release-gates"])
api_router.include_router(telemetry_router, prefix="/telemetry", tags=["telemetry"])
