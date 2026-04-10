from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from faster_whisper import WhisperModel

from src.config import SubtitleConfig
from src.models import SubtitleChunk

LOGGER = logging.getLogger(__name__)


def _build_chunks(words: Iterable, words_per_chunk: int, max_chars_per_line: int) -> list[SubtitleChunk]:
    chunks: list[SubtitleChunk] = []
    bucket = []

    for word in words:
        if word.start is None or word.end is None:
            continue
        bucket.append(word)
        text = " ".join(w.word.strip() for w in bucket).strip()
        if len(bucket) >= words_per_chunk or len(text) >= max_chars_per_line:
            chunks.append(SubtitleChunk(start=float(bucket[0].start), end=float(bucket[-1].end), text=text))
            bucket = []

    if bucket:
        text = " ".join(w.word.strip() for w in bucket).strip()
        chunks.append(SubtitleChunk(start=float(bucket[0].start), end=float(bucket[-1].end), text=text))
    return chunks


def transcribe_to_chunks(audio_path: Path, cfg: SubtitleConfig) -> list[SubtitleChunk]:
    LOGGER.info("stage=subtitles_transcribe model=%s audio=%s", cfg.model_size, audio_path)
    model = WhisperModel(cfg.model_size, compute_type="int8")
    segments, _ = model.transcribe(
        str(audio_path),
        language=cfg.language,
        word_timestamps=True,
        vad_filter=True,
    )

    words = []
    for segment in segments:
        if not segment.words:
            continue
        words.extend(segment.words)

    chunks = _build_chunks(words, cfg.words_per_chunk, cfg.max_chars_per_line)
    LOGGER.info("stage=subtitles_transcribe chunks=%s", len(chunks))
    return chunks


def write_subtitles_json(chunks: list[SubtitleChunk], output_path: Path) -> None:
    payload = [{"start": c.start, "end": c.end, "text": c.text} for c in chunks]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
