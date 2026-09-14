from pathlib import Path

from forge.config import settings
from forge.llm import siliconflow_client


def synthesize(text: str, out_path: Path,
               model: str | None = None,
               voice: str | None = None,
               speed: float = 1.0,
               response_format: str = "mp3") -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m = model or settings.tts_model
    v = voice or settings.tts_voice
    c = siliconflow_client()
    with c.audio.speech.with_streaming_response.create(
        model=m, voice=v, input=text, response_format=response_format, speed=speed
    ) as resp:
        resp.stream_to_file(str(out_path))
    return out_path
