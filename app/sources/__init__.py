import asyncio
from urllib.parse import quote_plus

import httpx

from app.sources.aastocks import collect_aastocks
from app.sources.base import Article
from app.sources.rss import collect_rss

BLOOMBERG_FEEDS = [
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://feeds.bloomberg.com/economics/news.rss",
]
CNBC_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
]
YAHOO_FEEDS = [
    "https://finance.yahoo.com/news/rssindex",
]

# Reuters blocks direct crawling (Akamai 401), so its headlines come from the
# publisher-syndicated Google News feed restricted to reuters.com.
REUTERS_FEEDS = [
    "https://news.google.com/rss/search?q="
    + quote_plus("stock market OR wall street OR stocks when:2d site:reuters.com")
    + "&hl=en-US&gl=US&ceid=US:en",
]

SOURCE_NAMES = ["Bloomberg", "Reuters", "CNBC", "Yahoo Finance", "AAStocks"]


def ticker_news_feeds(symbol: str, name: str = "") -> list[str]:
    """Yahoo's per-ticker feed first; Google News covers it when Yahoo rate-limits."""
    query = f'"{name}" stock when:3d' if name else f"{symbol} stock when:3d"
    return [
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote_plus(symbol)}&region=US&lang=en-US",
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-US&gl=US&ceid=US:en",
    ]


async def collect_all(client: httpx.AsyncClient) -> list[Article]:
    results = await asyncio.gather(
        collect_rss(client, "Bloomberg", BLOOMBERG_FEEDS),
        collect_rss(client, "Reuters", REUTERS_FEEDS),
        collect_rss(client, "CNBC", CNBC_FEEDS),
        collect_rss(client, "Yahoo Finance", YAHOO_FEEDS),
        collect_aastocks(client),
        return_exceptions=True,
    )
    articles: list[Article] = []
    for result in results:
        if isinstance(result, BaseException):
            continue
        articles.extend(result)
    return articles


async def collect_ticker_news(
    client: httpx.AsyncClient, symbol: str, name: str = "", limit: int = 3
) -> list[Article]:
    for feed_url in ticker_news_feeds(symbol, name):
        source = None if "news.google.com" in feed_url else "Yahoo Finance"
        articles = await collect_rss(client, source, [feed_url])
        if not articles:
            continue
        articles.sort(
            key=lambda a: a.published_at.timestamp() if a.published_at else 0, reverse=True
        )
        for article in articles:
            article.tickers = [symbol]
        return articles[:limit]
    return []
