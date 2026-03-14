from __future__ import annotations

import hashlib
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.pronunciations import (
    create_pronunciation,
    delete_pronunciation,
    list_pronunciations,
    update_pronunciation,
)
from app.middleware.auth import verify_api_key

admin_router = APIRouter()


def _owner_key_hash(api_key: str | None) -> str:
    if not api_key:
        # should not happen: verify_api_key required
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


_LANGUAGE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


class PronunciationOut(BaseModel):
    id: str
    language: str
    grapheme: str
    alias: str
    created_at: str
    updated_at: str


class PronunciationListOut(BaseModel):
    items: list[PronunciationOut]


class PronunciationCreateIn(BaseModel):
    language: str = Field(default="de-DE")
    grapheme: str = Field(min_length=1, max_length=200)
    alias: str = Field(min_length=1, max_length=400)


class PronunciationUpdateIn(BaseModel):
    alias: str = Field(min_length=1, max_length=400)


@admin_router.get(
    "/admin/pronunciations",
    dependencies=[Depends(verify_api_key)],
    response_model=PronunciationListOut,
)
async def list_rules(
    language: str | None = Query(default=None),
    api_key: str | None = Depends(verify_api_key),
) -> PronunciationListOut:
    if language is not None and not _LANGUAGE_RE.match(language):
        raise HTTPException(status_code=400, detail="Invalid language format (expected like de-DE)")

    settings = get_settings()
    owner = _owner_key_hash(api_key)
    items = list_pronunciations(settings.sqlite_path, owner_key_hash=owner, language=language)
    return PronunciationListOut(
        items=[
            PronunciationOut(
                id=i.id,
                language=i.language,
                grapheme=i.grapheme,
                alias=i.alias,
                created_at=i.created_at,
                updated_at=i.updated_at,
            )
            for i in items
        ]
    )


@admin_router.post(
    "/admin/pronunciations",
    dependencies=[Depends(verify_api_key)],
    response_model=PronunciationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    payload: PronunciationCreateIn,
    api_key: str | None = Depends(verify_api_key),
) -> PronunciationOut:
    if payload.language and not _LANGUAGE_RE.match(payload.language):
        raise HTTPException(status_code=400, detail="Invalid language format (expected like de-DE)")

    settings = get_settings()
    owner = _owner_key_hash(api_key)

    prn_id = "prn_" + hashlib.sha256(f"{owner}:{payload.language}:{payload.grapheme}".encode("utf-8")).hexdigest()[:16]

    try:
        prn = create_pronunciation(
            settings.sqlite_path,
            prn_id=prn_id,
            owner_key_hash=owner,
            language=payload.language,
            grapheme=payload.grapheme,
            alias=payload.alias,
        )
    except Exception as exc:  # sqlite integrity
        # likely uniqueness violation
        raise HTTPException(status_code=409, detail="Pronunciation already exists") from exc

    return PronunciationOut(
        id=prn.id,
        language=prn.language,
        grapheme=prn.grapheme,
        alias=prn.alias,
        created_at=prn.created_at,
        updated_at=prn.updated_at,
    )


@admin_router.put(
    "/admin/pronunciations/{prn_id}",
    dependencies=[Depends(verify_api_key)],
    response_model=PronunciationOut,
)
async def update_rule(
    prn_id: str,
    payload: PronunciationUpdateIn,
    api_key: str | None = Depends(verify_api_key),
) -> PronunciationOut:
    settings = get_settings()
    owner = _owner_key_hash(api_key)

    prn = update_pronunciation(
        settings.sqlite_path,
        prn_id=prn_id,
        owner_key_hash=owner,
        alias=payload.alias,
    )
    if prn is None:
        raise HTTPException(status_code=404, detail="Not found")

    return PronunciationOut(
        id=prn.id,
        language=prn.language,
        grapheme=prn.grapheme,
        alias=prn.alias,
        created_at=prn.created_at,
        updated_at=prn.updated_at,
    )


@admin_router.delete(
    "/admin/pronunciations/{prn_id}",
    dependencies=[Depends(verify_api_key)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rule(
    prn_id: str,
    api_key: str | None = Depends(verify_api_key),
) -> None:
    settings = get_settings()
    owner = _owner_key_hash(api_key)

    ok = delete_pronunciation(settings.sqlite_path, prn_id=prn_id, owner_key_hash=owner)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
