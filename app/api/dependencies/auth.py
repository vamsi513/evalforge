from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import settings

_ROLE_RANK = {"viewer": 1, "editor": 2, "admin": 3}


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


async def get_user_role(
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
) -> str:
    role = (x_user_role or settings.default_user_role or "viewer").strip().lower()
    if role not in _ROLE_RANK:
        raise HTTPException(status_code=400, detail="Invalid X-User-Role. Use viewer, editor, or admin.")
    return role


def _require_min_role(min_role: str):
    min_rank = _ROLE_RANK[min_role]

    async def _checker(role: str = Header(default="", alias="X-User-Role")) -> None:
        if not settings.platform_api_key:
            return
        resolved = (role or settings.default_user_role or "viewer").strip().lower()
        if resolved not in _ROLE_RANK:
            raise HTTPException(status_code=400, detail="Invalid X-User-Role. Use viewer, editor, or admin.")
        if _ROLE_RANK[resolved] < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{resolved}' cannot access this endpoint. Required role: {min_role} or higher.",
            )

    return _checker


require_viewer_role = _require_min_role("viewer")
require_editor_role = _require_min_role("editor")
require_admin_role = _require_min_role("admin")
