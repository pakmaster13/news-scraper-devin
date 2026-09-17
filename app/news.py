import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.config import MAX_PER_SOURCE, NEWS_CACHE_SECONDS, TOP_N
from app.sources import collect_all
from app.sources.base import Article

SOURCE_WEIGHT = {
    "Bloomberg": 1.0,
    "Reuters": 1.0,
    "CNBC": 0.9,
    "Yahoo Finance": 0.8,
    "AAStocks": 0.8,
}

MARKET_KEYWORDS = {
    "stock": 3.0,
    "stocks": 3.0,
    "shares": 2.0,
    "market": 2.0,
    "markets": 2.5,
    "wall street": 3.0,
    "s&p": 3.0,
    "nasdaq": 3.0,
    "dow": 2.5,
    "hsi": 2.0,
    "hang seng": 2.0,
    "index": 1.5,
    "rally": 2.0,
    "selloff": 2.0,
    "sell-off": 2.0,
    "earnings": 2.5,
    "guidance": 1.5,
    "ipo": 1.5,
    "fed": 2.5,
    "federal reserve": 2.5,
    "rate": 1.5,
    "inflation": 2.0,
    "yields": 2.0,
    "treasury": 1.5,
    "investors": 1.5,
    "trading": 1.5,
    "bull": 1.0,
    "bear": 1.0,
    "downgrade": 1.5,
    "upgrade": 1.5,
    "surge": 1.0,
    "plunge": 1.5,
    "tumble": 1.5,
}

NOISE_KEYWORDS = ("horoscope", "recipe", "how to watch", "deal of the day", "coupon")

# Feeds that only ever carry market coverage, so a story needs no keyword evidence.
MARKET_ONLY_SOURCES = {"Bloomberg", "AAStocks", "Reuters"}

WATCHLIST_BOOST = 8.0

_TICKER_HINT = re.compile(r"\(([A-Z]{1,5})(?:\.[A-Z]{1,2})?\)")
_CACHE: dict[str, Any] = {"at": 0.0, "articles": []}


def _recency_points(article: Article, now: datetime) -> float:
    if article.published_at is None:
        return 4.0
    hours = max((now - article.published_at).total_seconds() / 3600.0, 0.0)
    if hours <= 2:
        return 10.0
    if hours <= 6:
        return 8.0
    if hours <= 12:
        return 6.0
    if hours <= 24:
        return 4.0
    if hours <= 48:
        return 2.0
    return 0.0


def _keyword_points(text: str) -> float:
    return sum(weight for term, weight in MARKET_KEYWORDS.items() if term in text)


def score_article(article: Article, now: datetime, watchlist: list[str]) -> float:
    text = f"{article.title} {article.summary}".lower()
    if any(noise in text for noise in NOISE_KEYWORDS):
        return -1.0
    keyword_points = _keyword_points(text)
    hits = [s for s in watchlist if s.lower() in text or f"({s.upper()})" in article.title]
    if not keyword_points and not hits and article.source not in MARKET_ONLY_SOURCES:
        return -1.0

    score = _recency_points(article, now)
    score += min(keyword_points, 12.0)
    score *= SOURCE_WEIGHT.get(article.source, 0.7)
    if hits:
        article.tickers = sorted(set(article.tickers) | set(hits))
        score += WATCHLIST_BOOST * len(hits)
    return score


def _is_duplicate(title: str, kept: list[str]) -> bool:
    normalized = re.sub(r"[^a-z0-9 ]", "", title.lower())
    for existing in kept:
        if SequenceMatcher(None, normalized, existing).ratio() > 0.82:
            return True
    return False


def rank(articles: list[Article], watchlist: list[str], limit: int = TOP_N) -> list[Article]:
    now = datetime.now(timezone.utc)
    seen_urls: set[str] = set()
    scored: list[Article] = []
    for article in articles:
        if article.url in seen_urls:
            continue
        seen_urls.add(article.url)
        article.score = score_article(article, now, watchlist)
        if article.score <= 0:
            continue
        if not article.tickers:
            article.tickers = _TICKER_HINT.findall(article.title)
        scored.append(article)

    scored.sort(key=lambda a: a.score, reverse=True)
    top: list[Article] = []
    kept_titles: list[str] = []
    per_source: dict[str, int] = {}
    overflow: list[Article] = []

    for article in scored:
        if _is_duplicate(article.title, kept_titles):
            continue
        normalized = re.sub(r"[^a-z0-9 ]", "", article.title.lower())
        if per_source.get(article.source, 0) >= MAX_PER_SOURCE:
            overflow.append(article)
            continue
        top.append(article)
        kept_titles.append(normalized)
        per_source[article.source] = per_source.get(article.source, 0) + 1
        if len(top) >= limit:
            return top

    # Backfill with the best remaining stories when diversity capping left room.
    for article in overflow:
        if len(top) >= limit:
            break
        top.append(article)
    return top


async def get_top_news(
    watchlist: list[str], limit: int = TOP_N, force_refresh: bool = False
) -> tuple[list[Article], datetime]:
    now = time.time()
    if force_refresh or now - _CACHE["at"] > NEWS_CACHE_SECONDS or not _CACHE["articles"]:
        async with httpx.AsyncClient() as client:
            _CACHE["articles"] = await collect_all(client)
            _CACHE["at"] = now
    fetched_at = datetime.fromtimestamp(_CACHE["at"], tz=timezone.utc)
    return rank(list(_CACHE["articles"]), watchlist, limit), fetched_at
