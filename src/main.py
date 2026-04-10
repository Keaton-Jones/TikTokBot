from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from src.config import AppConfig, load_config
from src.models import RenderArtifacts

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Reddit-to-video MVP output.")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--once", action="store_true", help="Run exactly one render pass.")
    mode_group.add_argument(
        "--sanity-check",
        action="store_true",
        help="Validate config and local assets without fetching Reddit or rendering video.",
    )
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="Path to config yaml.")
    return parser.parse_args()


def _safe_slug(text: str, max_len: int = 40) -> str:
    keep = "".join(ch if ch.isalnum() else "-" for ch in text.lower()).strip("-")
    while "--" in keep:
        keep = keep.replace("--", "-")
    return keep[:max_len] or "post"


def _build_run_paths(cfg: AppConfig, title: str) -> RenderArtifacts:
    now = datetime.now()
    date_dir = cfg.paths.output_dir / now.strftime("%Y-%m-%d")
    slug = _safe_slug(title)
    stem = f"{now.strftime('%H%M%S')}-{slug}"
    temp_dir = cfg.paths.temp_dir / now.strftime("%Y-%m-%d")
    return RenderArtifacts(
        narration_path=temp_dir / f"{stem}.mp3",
        subtitles_path=temp_dir / f"{stem}.subtitles.json",
        output_video_path=date_dir / f"{stem}.mp4",
        metadata_path=date_dir / f"{stem}.metadata.json",
    )


def run_once(cfg: AppConfig) -> Path:
    from src.reddit_client import fetch_best_post
    from src.subtitles import transcribe_to_chunks, write_subtitles_json
    from src.tts_edge import generate_narration
    from src.video_compose import compose_video

    logger = logging.getLogger("pipeline")
    logger.info("stage=start run_mode=once")

    post = fetch_best_post(cfg.reddit)
    artifacts = _build_run_paths(cfg, post.title)
    narration_text = post.full_text

    duration = generate_narration(narration_text, cfg.tts, artifacts.narration_path)
    subtitle_chunks = transcribe_to_chunks(artifacts.narration_path, cfg.subtitles)
    write_subtitles_json(subtitle_chunks, artifacts.subtitles_path)

    compose_video(
        title=post.title,
        narration_path=artifacts.narration_path,
        subtitle_chunks=subtitle_chunks,
        backgrounds_dir=cfg.paths.backgrounds_dir,
        output_path=artifacts.output_video_path,
        video_cfg=cfg.video,
        subtitle_cfg=cfg.subtitles,
    )

    artifacts.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "source": {
            "post_id": post.post_id,
            "permalink": post.permalink,
            "title": post.title,
            "subreddit": cfg.reddit.subreddit,
            "score": post.score,
        },
        "render": {
            "duration_seconds": duration,
            "voice": cfg.tts.voice,
            "video_width": cfg.video.width,
            "video_height": cfg.video.height,
            "fps": cfg.video.fps,
            "subtitle_chunks": len(subtitle_chunks),
        },
        "files": {
            "video": str(artifacts.output_video_path),
            "narration": str(artifacts.narration_path),
            "subtitles": str(artifacts.subtitles_path),
        },
    }
    artifacts.metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    size_mb = artifacts.output_video_path.stat().st_size / (1024 * 1024)
    logger.info(
        "stage=finish video=%s size_mb=%.2f duration_sec=%.2f",
        artifacts.output_video_path,
        size_mb,
        duration,
    )
    return artifacts.output_video_path


def run_sanity_check(cfg: AppConfig) -> bool:
    logger = logging.getLogger("pipeline")
    logger.info("stage=sanity_check start")

    backgrounds_dir = cfg.paths.backgrounds_dir
    output_dir = cfg.paths.output_dir
    temp_dir = cfg.paths.temp_dir

    for path in (output_dir, temp_dir):
        path.mkdir(parents=True, exist_ok=True)

    checks: list[tuple[str, bool, str]] = []
    checks.append(("config_loaded", True, "Config parsed successfully"))
    reddit_client_id_ok = bool(cfg.reddit.client_id.strip()) and "YOUR_REDDIT_CLIENT_ID" not in cfg.reddit.client_id
    reddit_client_secret_ok = bool(cfg.reddit.client_secret.strip()) and "YOUR_REDDIT_CLIENT_SECRET" not in cfg.reddit.client_secret
    reddit_user_agent_ok = bool(cfg.reddit.user_agent.strip()) and "YOUR_USERNAME" not in cfg.reddit.user_agent
    checks.append(("reddit_client_id_set", reddit_client_id_ok, "Set reddit.client_id in config.yaml"))
    checks.append(("reddit_client_secret_set", reddit_client_secret_ok, "Set reddit.client_secret in config.yaml"))
    checks.append(("reddit_user_agent_set", reddit_user_agent_ok, "Set reddit.user_agent in config.yaml"))
    checks.append(("backgrounds_dir_exists", backgrounds_dir.exists(), str(backgrounds_dir)))
    checks.append(("backgrounds_dir_is_dir", backgrounds_dir.is_dir(), str(backgrounds_dir)))

    background_files = []
    if backgrounds_dir.exists() and backgrounds_dir.is_dir():
        background_files = [p for p in backgrounds_dir.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS]

    checks.append(
        (
            "background_videos_found",
            len(background_files) > 0,
            f"Count={len(background_files)} accepted_ext={sorted(VIDEO_EXTENSIONS)}",
        )
    )
    checks.append(("output_dir_writable", output_dir.exists() and output_dir.is_dir(), str(output_dir)))
    checks.append(("temp_dir_writable", temp_dir.exists() and temp_dir.is_dir(), str(temp_dir)))

    all_ok = True
    for name, passed, detail in checks:
        if passed:
            logger.info("stage=sanity_check check=%s status=pass detail=%s", name, detail)
        else:
            logger.error("stage=sanity_check check=%s status=fail detail=%s", name, detail)
            all_ok = False

    if all_ok:
        logger.info("stage=sanity_check result=pass")
    else:
        logger.error("stage=sanity_check result=fail")
    return all_ok


def main() -> int:
    setup_logging()
    args = parse_args()
    try:
        from src.reddit_client import InvalidRedditCredentialsError, NoValidRedditPostError

        cfg = load_config(args.config)
        if args.sanity_check:
            return 0 if run_sanity_check(cfg) else 3
        run_once(cfg)
        return 0
    except InvalidRedditCredentialsError as exc:
        logging.getLogger("pipeline").error("stage=exit reason=invalid_reddit_credentials detail=%s", exc)
        return 11
    except NoValidRedditPostError as exc:
        logging.getLogger("pipeline").warning("stage=exit reason=no_valid_post detail=%s", exc)
        return 10
    except Exception:
        logging.getLogger("pipeline").exception("stage=error unhandled_exception")
        return 1


if __name__ == "__main__":
    sys.exit(main())
