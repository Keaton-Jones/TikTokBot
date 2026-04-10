from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RedditConfig:
    client_id: str
    client_secret: str
    user_agent: str
    subreddit: str
    listing: str
    time_filter: str
    fetch_limit: int
    min_chars: int
    max_chars: int
    allow_nsfw: bool


@dataclass(frozen=True)
class TtsConfig:
    voice: str
    rate: str
    volume: str


@dataclass(frozen=True)
class SubtitleConfig:
    model_size: str
    language: str
    words_per_chunk: int
    max_chars_per_line: int
    font_size: int
    bottom_margin: int


@dataclass(frozen=True)
class VideoConfig:
    width: int
    height: int
    fps: int
    hook_seconds: float
    fade_in_seconds: float
    fade_out_seconds: float


@dataclass(frozen=True)
class PathsConfig:
    backgrounds_dir: Path
    output_dir: Path
    temp_dir: Path


@dataclass(frozen=True)
class AppConfig:
    reddit: RedditConfig
    tts: TtsConfig
    subtitles: SubtitleConfig
    video: VideoConfig
    paths: PathsConfig


def _required(section: dict, key: str, section_name: str):
    if key not in section:
        raise ValueError(f"Missing required key '{section_name}.{key}' in config.")
    return section[key]


def load_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    reddit_raw = _required(raw, "reddit", "root")
    tts_raw = _required(raw, "tts", "root")
    subtitles_raw = _required(raw, "subtitles", "root")
    video_raw = _required(raw, "video", "root")
    paths_raw = _required(raw, "paths", "root")

    cfg = AppConfig(
        reddit=RedditConfig(
            client_id=str(_required(reddit_raw, "client_id", "reddit")),
            client_secret=str(_required(reddit_raw, "client_secret", "reddit")),
            user_agent=str(_required(reddit_raw, "user_agent", "reddit")),
            subreddit=str(_required(reddit_raw, "subreddit", "reddit")),
            listing=str(_required(reddit_raw, "listing", "reddit")).lower(),
            time_filter=str(_required(reddit_raw, "time_filter", "reddit")).lower(),
            fetch_limit=int(_required(reddit_raw, "fetch_limit", "reddit")),
            min_chars=int(_required(reddit_raw, "min_chars", "reddit")),
            max_chars=int(_required(reddit_raw, "max_chars", "reddit")),
            allow_nsfw=bool(_required(reddit_raw, "allow_nsfw", "reddit")),
        ),
        tts=TtsConfig(
            voice=str(_required(tts_raw, "voice", "tts")),
            rate=str(_required(tts_raw, "rate", "tts")),
            volume=str(_required(tts_raw, "volume", "tts")),
        ),
        subtitles=SubtitleConfig(
            model_size=str(_required(subtitles_raw, "model_size", "subtitles")),
            language=str(_required(subtitles_raw, "language", "subtitles")),
            words_per_chunk=int(_required(subtitles_raw, "words_per_chunk", "subtitles")),
            max_chars_per_line=int(_required(subtitles_raw, "max_chars_per_line", "subtitles")),
            font_size=int(_required(subtitles_raw, "font_size", "subtitles")),
            bottom_margin=int(_required(subtitles_raw, "bottom_margin", "subtitles")),
        ),
        video=VideoConfig(
            width=int(_required(video_raw, "width", "video")),
            height=int(_required(video_raw, "height", "video")),
            fps=int(_required(video_raw, "fps", "video")),
            hook_seconds=float(_required(video_raw, "hook_seconds", "video")),
            fade_in_seconds=float(_required(video_raw, "fade_in_seconds", "video")),
            fade_out_seconds=float(_required(video_raw, "fade_out_seconds", "video")),
        ),
        paths=PathsConfig(
            backgrounds_dir=Path(str(_required(paths_raw, "backgrounds_dir", "paths"))),
            output_dir=Path(str(_required(paths_raw, "output_dir", "paths"))),
            temp_dir=Path(str(_required(paths_raw, "temp_dir", "paths"))),
        ),
    )

    if cfg.reddit.listing not in {"top", "hot", "new"}:
        raise ValueError("reddit.listing must be one of: top, hot, new")
    if cfg.reddit.min_chars >= cfg.reddit.max_chars:
        raise ValueError("reddit.min_chars must be lower than reddit.max_chars")
    if cfg.subtitles.words_per_chunk < 1:
        raise ValueError("subtitles.words_per_chunk must be >= 1")
    if cfg.video.width <= 0 or cfg.video.height <= 0:
        raise ValueError("video width/height must be positive")
    if cfg.video.fps <= 0:
        raise ValueError("video.fps must be positive")

    return cfg
