from __future__ import annotations
import structlog
import httpx
from rag.config import get_settings

log = structlog.get_logger()

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


def text_to_speech(text: str, voice_id: str = None) -> bytes:
    s = get_settings()
    vid = voice_id or s.elevenlabs_voice_id

    headers = {
        "xi-api-key": s.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text[:500],  # cap at 500 chars to save quota
        # "model_id": "eleven_monolingual_v1",
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        }
    }

    response = httpx.post(
        f"{ELEVENLABS_URL}/{vid}",
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    log.info("tts_done", chars=len(text))
    return response.content


async def text_to_speech_stream(text: str, voice_id: str = None):
    """Async generator that streams audio chunks."""
    s = get_settings()
    vid = voice_id or s.elevenlabs_voice_id

    # headers = {
    #     "xi-api-key": s.elevenlabs_api_key,
    #     "Content-Type": "application/json",
    #     "Accept": "audio/mpeg",
    # }
    headers = {
        "xi-api-key": s.elevenlabs_api_key,
        "Authorization": f"Bearer {s.elevenlabs_api_key}",
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text[:500],
        # "model_id": "eleven_monolingual_v1",
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        async with client.stream(
            "POST",
            f"{ELEVENLABS_URL}/{vid}/stream",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=1024):
                if chunk:
                    yield chunk
