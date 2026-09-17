import re

import feedparser
import httpx

from app.sources.base import Article, clean_text, fetch, parse_date

# Google News appends " - Publisher" to every syndicated headline.
_PUBLISHER_SUFFIX = re.compile(r"\s+-\s+([^-]{2,40})\s*$")


def _split_publisher(title: str) -> tuple[str, str | None]:
    match = _PUBLISHER_SUFFIX.search(title)
    if not match:
        return title, None
    return title[: match.start()].strip(), match.group(1).strip()


async def collect_rss(
    client: httpx.AsyncClient, source: str | None, feed_urls: list[str]
) -> list[Article]:
    """Collect entries from RSS feeds.

    When ``source`` is None the publisher is taken from the Google News title suffix.
    """
    articles: list[Article] = []
    for url in feed_urls:
        is_google_news = "news.google.com" in url
        try:
            response = await fetch(client, url)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.InvalidURL):
            continue
        parsed = feedparser.parse(response.text)
        for entry in parsed.entries:
            link = entry.get("link") or ""
            title = clean_text(entry.get("title"), limit=240)
            if not link or not title:
                continue
            publisher = None
            if is_google_news:
                title, publisher = _split_publisher(title)
            articles.append(
                Article(
                    title=title,
                    url=link,
                    source=source or publisher or "Google News",
                    published_at=parse_date(entry.get("published") or entry.get("updated")),
                    summary=clean_text(entry.get("summary") or entry.get("description")),
                )
            )
    return articles
