from __future__ import annotations

import httpx


class ElevenLabsPronDictError(RuntimeError):
    pass


async def upload_dictionary_from_pls(
    *,
    api_key: str,
    name: str,
    description: str,
    pls_content: str,
) -> tuple[str, str]:
    """Create a new pronunciation dictionary from a PLS file.

    Returns: (dictionary_id, version_id)

    NOTE: ElevenLabs also supports versioning, but in v1 we always create a new
    dictionary when the content changes. We store the newest locator per consumer.
    """

    files = {
        # NOTE: ElevenLabs is picky about the multipart content-type.
        # Omitting it lets httpx default to application/octet-stream (works reliably).
        "file": ("dict.pls", pls_content.encode("utf-8")),
    }
    data = {
        "name": name,
        "description": description,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post(
            "https://api.elevenlabs.io/v1/pronunciation-dictionaries/add-from-file",
            headers={"xi-api-key": api_key},
            data=data,
            files=files,
        )

    if resp.status_code >= 400:
        raise ElevenLabsPronDictError(f"ElevenLabs dict upload failed ({resp.status_code}): {resp.text}")

    j = resp.json()
    # docs use id + version_id
    dict_id = j.get("id") or j.get("pronunciation_dictionary_id")
    ver_id = j.get("version_id") or j.get("versionId")
    if not dict_id or not ver_id:
        raise ElevenLabsPronDictError(f"Unexpected ElevenLabs response: {j}")

    return str(dict_id), str(ver_id)


async def archive_dictionary(*, api_key: str, dictionary_id: str) -> None:
    """Archive a pronunciation dictionary (best-effort cleanup)."""

    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        resp = await client.patch(
            f"https://api.elevenlabs.io/v1/pronunciation-dictionaries/{dictionary_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"archived": True},
        )

    # Best-effort: don't raise on failure
    if resp.status_code >= 400:
        raise ElevenLabsPronDictError(
            f"ElevenLabs dict archive failed ({resp.status_code}) for {dictionary_id}: {resp.text}"
        )
