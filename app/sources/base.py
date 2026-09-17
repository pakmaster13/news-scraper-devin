import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import HTTP_TIMEOUT, USER_AGENT

_WS = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    summary: str = ""
    tickers: list[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "tickers": self.tickers,
            "score": round(self.score, 3),
        }


def clean_text(value: str | None, limit: int = 320) -> str:
    if not value:
        return ""
    text = _WS.sub(" ", _TAGS.sub(" ", value)).strip()
    return text[: limit - 1] + "\u2026" if len(text) > limit else text


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is None:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def fetch(client: httpx.AsyncClient, url: str) -> httpx.Response:
    return await client.get(
        url,
        timeout=HTTP_TIMEOUT,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
