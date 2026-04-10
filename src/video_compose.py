from __future__ import annotations

import logging
import random
from pathlib import Path

from src.config import SubtitleConfig, VideoConfig
from src.models import SubtitleChunk

LOGGER = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def _moviepy_symbols():
    try:
        from moviepy.editor import AudioFileClip, ColorClip, CompositeVideoClip, TextClip, VideoFileClip  # moviepy 1.x
    except ModuleNotFoundError:
        from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, TextClip, VideoFileClip  # moviepy 2.x
    return AudioFileClip, ColorClip, CompositeVideoClip, TextClip, VideoFileClip


def _fit_to_vertical(clip, width: int, height: int):
    aspect_target = width / height
    aspect_source = clip.w / clip.h
    if aspect_source > aspect_target:
        resized = clip.resize(height=height)
        x1 = int((resized.w - width) / 2)
        return resized.crop(x1=x1, y1=0, x2=x1 + width, y2=height)
    resized = clip.resize(width=width)
    y1 = int((resized.h - height) / 2)
    return resized.crop(x1=0, y1=y1, x2=width, y2=y1 + height)


def _pick_background_segment(backgrounds_dir: Path, needed_seconds: float, video_file_clip):
    files = [p for p in backgrounds_dir.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS]
    if not files:
        raise FileNotFoundError(f"No background videos found in {backgrounds_dir}")
    chosen = random.choice(files)
    src = video_file_clip(str(chosen))
    if src.duration <= needed_seconds:
        LOGGER.warning("stage=compose short_background=%s duration=%.2f", chosen.name, src.duration)
        return src
    max_start = max(0.0, src.duration - needed_seconds)
    start = random.uniform(0, max_start)
    LOGGER.info("stage=compose background=%s start=%.2f", chosen.name, start)
    return src.subclip(start, start + needed_seconds)


def _hook_overlay(title: str, video_cfg: VideoConfig, duration: float, text_clip, color_clip, composite_video_clip):
    text = text_clip(
        txt=title,
        fontsize=68,
        color="white",
        font="Arial-Bold",
        method="caption",
        size=(video_cfg.width - 100, None),
        align="center",
    ).set_duration(min(duration, video_cfg.hook_seconds))

    bg = color_clip(size=(video_cfg.width - 40, text.h + 50), color=(0, 0, 0)).set_opacity(0.55).set_duration(
        text.duration
    )
    group = composite_video_clip([bg, text.set_position(("center", "center"))], size=bg.size)
    return group.set_position(("center", 150))


def _subtitle_clips(chunks: list[SubtitleChunk], cfg: SubtitleConfig, video_cfg: VideoConfig, text_clip) -> list:
    clips: list = []
    for chunk in chunks:
        clips.append(
            text_clip(
                txt=chunk.text,
                fontsize=cfg.font_size,
                color="white",
                stroke_color="black",
                stroke_width=2,
                font="Arial-Bold",
                method="caption",
                size=(video_cfg.width - 80, None),
                align="center",
            )
            .set_start(chunk.start)
            .set_end(chunk.end)
            .set_position(("center", video_cfg.height - cfg.bottom_margin))
        )
    return clips


def compose_video(
    title: str,
    narration_path: Path,
    subtitle_chunks: list[SubtitleChunk],
    backgrounds_dir: Path,
    output_path: Path,
    video_cfg: VideoConfig,
    subtitle_cfg: SubtitleConfig,
) -> None:
    AudioFileClip, ColorClip, CompositeVideoClip, TextClip, VideoFileClip = _moviepy_symbols()
    with AudioFileClip(str(narration_path)) as narration_audio:
        needed = float(narration_audio.duration)

    base = _pick_background_segment(backgrounds_dir, needed, VideoFileClip)
    fitted = _fit_to_vertical(base, video_cfg.width, video_cfg.height).set_duration(needed)
    if video_cfg.fade_in_seconds > 0:
        fitted = fitted.fadein(video_cfg.fade_in_seconds)
    if video_cfg.fade_out_seconds > 0:
        fitted = fitted.fadeout(video_cfg.fade_out_seconds)

    with AudioFileClip(str(narration_path)) as narration_audio_2:
        video_with_audio = fitted.set_audio(narration_audio_2)
        overlays = [
            video_with_audio,
            _hook_overlay(title, video_cfg, needed, TextClip, ColorClip, CompositeVideoClip),
            *_subtitle_clips(subtitle_chunks, subtitle_cfg, video_cfg, TextClip),
        ]
        final = CompositeVideoClip(overlays, size=(video_cfg.width, video_cfg.height)).set_duration(needed)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(
            str(output_path),
            fps=video_cfg.fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="medium",
        )

    try:
        base.close()
    except Exception:
        pass
