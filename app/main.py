from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.api.routes_admin import admin_router
from app.config import get_settings
from app.db.schema import init_db
from app.storage.local import init_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings.sqlite_path)
    init_storage()
    yield


app = FastAPI(title="tts-service", lifespan=lifespan)
app.include_router(router)
app.include_router(admin_router)
