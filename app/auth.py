"""API-key auth: Bearer header or api_key query param, matching the spec."""

from fastapi import HTTPException, Request

from app.config import get_settings


def require_api_key(request: Request) -> None:
    keys = get_settings().api_key_set
    if not keys:  # auth disabled (dev mode)
        return
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        if auth_header[7:].strip() in keys:
            return
    if request.query_params.get("api_key") in keys:
        return
    raise HTTPException(status_code=401, detail="Invalid API key.")
