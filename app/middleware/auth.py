from __future__ import annotations

import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str | None:
    settings = get_settings()
    expected_keys = settings.get_api_key_values()

    if not expected_keys:
        # Dev mode: no key configured, allow all requests
        return None

    if not api_key or not any(hmac.compare_digest(api_key, k) for k in expected_keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

    return api_key
