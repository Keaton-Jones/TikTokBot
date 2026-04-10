from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import edge_tts
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import TtsConfig

LOGGER = logging.getLogger(__name__)


def _audio_file_clip_cls():
    try:
        from moviepy.editor import AudioFileClip  # moviepy 1.x
    except ModuleNotFoundError:
        from moviepy import AudioFileClip  # moviepy 2.x
    return AudioFileClip


def sanitize_narration_text(text: str) -> str:
    collapsed = " ".join(text.replace("\n", " ").split())
    return collapsed.strip()


async def _generate_audio_async(text: str, cfg: TtsConfig, output_path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=cfg.voice, rate=cfg.rate, volume=cfg.volume)
    await communicate.save(str(output_path))


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def generate_narration(text: str, cfg: TtsConfig, output_path: Path) -> float:
    safe_text = sanitize_narration_text(text)
    if not safe_text:
        raise ValueError("Narration text is empty after sanitization.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("stage=tts_generate voice=%s output=%s", cfg.voice, output_path)
    asyncio.run(_generate_audio_async(safe_text, cfg, output_path))

    AudioFileClip = _audio_file_clip_cls()
    with AudioFileClip(str(output_path)) as audio:
        duration = float(audio.duration)
    LOGGER.info("stage=tts_generate duration_sec=%.2f", duration)
    return duration
