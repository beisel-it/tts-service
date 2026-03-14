"""Admin and health-check routes (Task B3).

Endpoints:
  GET /health       — public health check (no auth required)
  GET /admin/voices — list voices from the active backend (API-key protected)
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.backends.router import BackendRouter, InvalidBackendError
from app.config import build_router_config, get_settings
from app.middleware.auth import verify_api_key

admin_router = APIRouter()

# Module-level startup timestamp for uptime calculation
_APP_START_TIME: datetime = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Dependency: BackendRouter
# ---------------------------------------------------------------------------


def get_backend_router() -> BackendRouter:
    """Build a BackendRouter from the current AppSettings (production default)."""
    settings = get_settings()
    config = build_router_config(settings)
    return BackendRouter(config)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@admin_router.get("/health", include_in_schema=True)
def health_check() -> dict[str, Any]:
    """Public health-check endpoint — no authentication required.

    Returns:
        status: "ok" always (service is up if this responds).
        database: "ok" or "error".
        queue_depth: number of pending/processing jobs.
        uptime_seconds: seconds since app startup.
    """
    settings = get_settings()

    db_status = "ok"
    queue_depth = 0
    try:
        with sqlite3.connect(settings.sqlite_path, timeout=2) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE status IN ('pending', 'processing')"
            ).fetchone()
            queue_depth = row[0] if row else 0
    except Exception:
        db_status = "error"

    uptime = (datetime.now(UTC) - _APP_START_TIME).total_seconds()

    return {
        "status": "ok",
        "database": db_status,
        "queue_depth": queue_depth,
        "uptime_seconds": int(uptime),
    }


# ---------------------------------------------------------------------------
# GET /admin/voices
# ---------------------------------------------------------------------------


@admin_router.get("/admin/voices", dependencies=[Depends(verify_api_key)])
def list_voices(router: BackendRouter = Depends(get_backend_router)) -> dict[str, Any]:
    """List voices available from the currently configured default backend.

    Returns:
        backend: name of the active backend.
        voices: list of {id, name, language} dicts.

    Raises:
        503: if the backend call fails.
    """
    try:
        backend = router.get_backend()
        voices = backend.list_voices()
    except InvalidBackendError as exc:
        return JSONResponse(
            status_code=503,
            content={"error_message": str(exc)},
        )
    except NotImplementedError as exc:
        return JSONResponse(
            status_code=503,
            content={"error_message": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"error_message": str(exc)},
        )

    return {
        "backend": backend.name,
        "voices": [
            {"id": v.voice_id, "name": v.name, "language": v.language}
            for v in voices
        ],
    }
