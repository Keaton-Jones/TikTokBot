from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RedditPost:
    post_id: str
    title: str
    body: str
    permalink: str
    score: int
    is_nsfw: bool

    @property
    def full_text(self) -> str:
        return f"{self.title.strip()}\n\n{self.body.strip()}".strip()

    @property
    def char_count(self) -> int:
        return len(self.full_text)


@dataclass(frozen=True)
class SubtitleChunk:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class RenderArtifacts:
    narration_path: Path
    subtitles_path: Path
    output_video_path: Path
    metadata_path: Path
