from __future__ import annotations

from forge.config import settings
from forge.llm import siliconflow_client


def transcribe(wav_path: str, model: str | None = None) -> str:
    m = model or settings.asr_model
    c = siliconflow_client()
    with open(wav_path, "rb") as f:
        resp = c.audio.transcriptions.create(model=m, file=f)
    text = getattr(resp, "text", None) or ""
    return text.strip()
