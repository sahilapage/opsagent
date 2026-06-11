from __future__ import annotations
import io
import tempfile
import os
import structlog
import whisper
import numpy as np

log = structlog.get_logger()

_model = None

def get_model(model_size: str = "base"):
    global _model
    if _model is None:
        log.info("loading_whisper_model", size=model_size)
        _model = whisper.load_model(model_size)
        log.info("whisper_model_loaded", size=model_size)
    return _model


def transcribe_audio(audio_bytes: bytes, model_size: str = "base") -> str:
    model = get_model(model_size)
    
    # Write to temp file — whisper needs a file path
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        result = model.transcribe(tmp_path, fp16=False)
        text = result["text"].strip()
        log.info("transcription_done", chars=len(text))
        return text
    except Exception as e:
        log.error("transcription_error", error=str(e))
        raise
    finally:
        os.unlink(tmp_path)


def transcribe_file(file_path: str) -> str:
    model = get_model()
    result = model.transcribe(file_path, fp16=False)
    return result["text"].strip()
