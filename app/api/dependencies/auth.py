from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings


async def require_api_access(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    if not settings.platform_api_key:
        return
    if x_api_key == settings.platform_api_key:
        return
    raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def get_workspace_id(
    x_workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-ID"),
) -> str:
    workspace_id = (x_workspace_id or settings.default_workspace_id).strip()
    return workspace_id or settings.default_workspace_id
