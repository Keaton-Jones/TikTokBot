from __future__ import annotations

import logging
from typing import Iterable

import praw
from prawcore.exceptions import ResponseException
from praw.models import Submission
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import RedditConfig
from src.models import RedditPost

LOGGER = logging.getLogger(__name__)


class NoValidRedditPostError(RuntimeError):
    """Raised when no suitable Reddit post is available."""


class InvalidRedditCredentialsError(RuntimeError):
    """Raised when Reddit API credentials are invalid."""


def _is_valid_post(post: Submission, cfg: RedditConfig) -> bool:
    if post.stickied:
        return False
    if post.removed_by_category is not None:
        return False
    if not post.selftext or post.selftext.strip() in {"[deleted]", "[removed]"}:
        return False
    if post.over_18 and not cfg.allow_nsfw:
        return False

    text = f"{post.title.strip()} {post.selftext.strip()}".strip()
    length = len(text)
    if length < cfg.min_chars or length > cfg.max_chars:
        return False
    return True


def _to_model(post: Submission) -> RedditPost:
    return RedditPost(
        post_id=post.id,
        title=post.title.strip(),
        body=post.selftext.strip(),
        permalink=f"https://www.reddit.com{post.permalink}",
        score=int(post.score or 0),
        is_nsfw=bool(post.over_18),
    )


def _iter_listing(subreddit, cfg: RedditConfig) -> Iterable[Submission]:
    if cfg.listing == "top":
        return subreddit.top(time_filter=cfg.time_filter, limit=cfg.fetch_limit)
    if cfg.listing == "new":
        return subreddit.new(limit=cfg.fetch_limit)
    return subreddit.hot(limit=cfg.fetch_limit)


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def fetch_best_post(cfg: RedditConfig) -> RedditPost:
    LOGGER.info(
        "stage=reddit_fetch subreddit=%s listing=%s limit=%s",
        cfg.subreddit,
        cfg.listing,
        cfg.fetch_limit,
    )
    reddit = praw.Reddit(
        client_id=cfg.client_id,
        client_secret=cfg.client_secret,
        user_agent=cfg.user_agent,
    )
    subreddit = reddit.subreddit(cfg.subreddit)
    try:
        candidates = [post for post in _iter_listing(subreddit, cfg) if _is_valid_post(post, cfg)]
    except ResponseException as exc:
        if exc.response is not None and exc.response.status_code == 401:
            raise InvalidRedditCredentialsError(
                "Reddit API returned 401 Unauthorized. Check reddit.client_id, reddit.client_secret, "
                "and reddit.user_agent in config.yaml."
            ) from exc
        raise
    if not candidates:
        raise NoValidRedditPostError(
            f"No valid posts found in r/{cfg.subreddit}. Adjust filter bounds or fetch_limit."
        )

    # Deterministic pick: highest score, then lexicographic id for stable tie-break.
    best = sorted(candidates, key=lambda p: (-int(p.score or 0), p.id))[0]
    model = _to_model(best)
    LOGGER.info("stage=reddit_fetch selected_post_id=%s score=%s", model.post_id, model.score)
    return model
