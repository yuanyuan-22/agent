from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    work_dir: Path = BASE_DIR / "runs"
    data_dir: Path = BASE_DIR / "data"

    provider: str = "siliconflow"
    chat_model: str = "Qwen/Qwen2.5-7B-Instruct"
    rewrite_model: str = "deepseek-ai/DeepSeek-V3"
    embed_model: str = "BAAI/bge-m3"
    temperature: float = 0.4

    tts_model: str = "FunAudioLLM/CosyVoice2-0.5B"
    tts_voice: str = "FunAudioLLM/CosyVoice2-0.5B:claire"
    tts_speed: float = 1.0

    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 24
    video_bg: tuple = (12, 20, 38)
    video_accent: tuple = (99, 179, 255)
    asset_dir: Path = BASE_DIR / "data" / "assets"
    music_dir: Path = BASE_DIR / "data" / "music"

    bili_timeout: float = 15
    bili_retries: int = 3

    transcript_mode: str = "cc_or_asr"
    asr_model: str = "FunAudioLLM/SenseVoiceSmall"
    asr_max_seconds: int = 240
    asr_enabled: bool = True

    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    deepseek_api_key: str = ""
    pexels_api_key: str = ""
    pexels_enabled: bool = True
    generation_enabled: bool = True
    generation_first: bool = False
    video_generation_enabled: bool = False
    image_model: str = "Qwen/Qwen-Image"
    image_fallback_model: str = "Tongyi-MAI/Z-Image-Turbo"
    video_model: str = "Wan-AI/Wan2.2-I2V-A14B"
    generation_timeout: float = 120.0
    generation_retries: int = 2
    video_poll_interval: float = 5.0
    video_poll_max: int = 60
    image_endpoint: str = "/images/generations"
    video_submit_endpoint: str = "/video/submit"
    video_status_endpoint: str = "/video/status"
    image_size: str = "768x1344"
    character_dir: Path = BASE_DIR / "data" / "characters"

    scheduler_enabled: bool = False
    scheduler_interval_minutes: int = 60

    def ensure_dirs(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)


def _apply_yaml(s: Settings, raw: dict) -> Settings:
    llm = raw.get("llm", {})
    tts = raw.get("tts", {})
    video = raw.get("video", {})
    bili = raw.get("bilibili", {})
    tr = raw.get("transcript", {})
    paths = raw.get("paths", {})

    s.provider = llm.get("provider", s.provider)
    s.chat_model = llm.get("chat_model", s.chat_model)
    s.rewrite_model = llm.get("rewrite_model", s.rewrite_model)
    s.embed_model = llm.get("embed_model", s.embed_model)
    s.temperature = float(llm.get("temperature", s.temperature))

    s.tts_model = tts.get("model", s.tts_model)
    s.tts_voice = tts.get("voice", s.tts_voice)
    s.tts_speed = float(tts.get("speed", s.tts_speed))

    s.video_width = int(video.get("width", s.video_width))
    s.video_height = int(video.get("height", s.video_height))
    s.video_fps = int(video.get("fps", s.video_fps))
    s.video_bg = tuple(video.get("bg_rgb", list(s.video_bg)))
    s.video_accent = tuple(video.get("accent_rgb", list(s.video_accent)))
    s.asset_dir = Path(video.get("asset_dir", s.asset_dir))
    s.music_dir = Path(video.get("music_dir", s.music_dir))

    s.bili_timeout = float(bili.get("timeout", s.bili_timeout))
    s.bili_retries = int(bili.get("retries", s.bili_retries))

    s.transcript_mode = tr.get("mode", s.transcript_mode)
    s.asr_model = tr.get("asr_model", s.asr_model)
    s.asr_max_seconds = int(tr.get("max_seconds", s.asr_max_seconds))
    s.asr_enabled = bool(tr.get("enabled", s.asr_enabled))

    if "work_dir" in paths:
        s.work_dir = Path(paths["work_dir"])
    if "data_dir" in paths:
        s.data_dir = Path(paths["data_dir"])

    s.siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY", "")
    s.siliconflow_base_url = os.getenv("SILICONFLOW_BASE_URL", s.siliconflow_base_url)
    s.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    s.pexels_api_key = os.getenv("PEXELS_API_KEY", "")
    s.pexels_enabled = os.getenv("PEXELS_ENABLED", "1") in ("1", "true", "True")
    s.generation_enabled = os.getenv("GENERATION_ENABLED", "1") in ("1", "true", "True")
    s.generation_first = os.getenv("GENERATION_FIRST", "0") in ("1", "true", "True")
    s.video_generation_enabled = os.getenv("VIDEO_GENERATION_ENABLED", "0") in ("1", "true", "True")
    s.image_model = os.getenv("IMAGE_MODEL", s.image_model)
    s.image_fallback_model = os.getenv("IMAGE_FALLBACK_MODEL", s.image_fallback_model)
    s.video_model = os.getenv("VIDEO_MODEL", s.video_model)
    s.generation_timeout = float(os.getenv("GENERATION_TIMEOUT", str(s.generation_timeout)))
    s.generation_retries = int(os.getenv("GENERATION_RETRIES", str(s.generation_retries)))
    s.video_poll_interval = float(os.getenv("VIDEO_POLL_INTERVAL", str(s.video_poll_interval)))
    s.video_poll_max = int(os.getenv("VIDEO_POLL_MAX", str(s.video_poll_max)))
    s.image_endpoint = os.getenv("IMAGE_ENDPOINT", s.image_endpoint)
    s.video_submit_endpoint = os.getenv("VIDEO_SUBMIT_ENDPOINT", s.video_submit_endpoint)
    s.video_status_endpoint = os.getenv("VIDEO_STATUS_ENDPOINT", s.video_status_endpoint)
    s.image_size = os.getenv("IMAGE_SIZE", s.image_size)
    s.scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "0") in ("1", "true", "True")
    s.scheduler_interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "60"))

    return s


def _load_settings() -> Settings:
    s = Settings()
    yaml_path = BASE_DIR / "config.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            _apply_yaml(s, yaml.safe_load(f) or {})
    s.ensure_dirs()
    s.asset_dir.mkdir(parents=True, exist_ok=True)
    s.music_dir.mkdir(parents=True, exist_ok=True)
    s.character_dir.mkdir(parents=True, exist_ok=True)
    return s


settings = _load_settings()
