# Reddit-to-Video MVP (Render Only)

This project generates a TikTok-ready vertical MP4 from a Reddit post.

## What it does

- Fetches one valid post from a configured subreddit
- Generates narration using Edge-TTS
- Creates timed subtitles from Whisper transcription
- Selects a random segment from background footage
- Exports final MP4 + metadata JSON for manual TikTok upload

## Setup

1. Install Python 3.10+.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Copy and edit config:
   - `copy config.example.yaml config.yaml` (Windows PowerShell)
4. Put several background videos into:
   - `assets/backgrounds/`

## Run once

- `python -m src.main --once --config config.yaml`

Output is written to `output/YYYY-MM-DD/`.

## Sanity check

- `python -m src.main --sanity-check --config config.yaml`

This validates config parsing, required directories, and presence of background video files without using Reddit/TTS/Whisper rendering stages.

## Notes

- `faster-whisper` may download model weights on first run.
- `moviepy` requires FFmpeg available in your environment.
- This MVP does not upload to TikTok automatically.
