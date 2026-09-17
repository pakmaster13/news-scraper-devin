from datetime import datetime, timedelta, timezone

from app.news import rank
from app.sources.base import Article
from app.sources.rss import _split_publisher


def make(title: str, source: str, hours_old: float = 1.0, url: str | None = None) -> Article:
    return Article(
        title=title,
        url=url or f"https://example.com/{abs(hash(title))}",
        source=source,
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_old),
    )


def test_rank_prefers_recent_market_stories():
    articles = [
        make("Nasdaq and S&P 500 rally as Fed holds rates", "Reuters", hours_old=1),
        make("A quiet day in local gardening", "CNBC", hours_old=1),
        make("Stocks slip as Treasury yields climb", "Bloomberg", hours_old=40),
    ]
    ranked = rank(articles, watchlist=[], limit=10)
    assert ranked[0].title.startswith("Nasdaq and S&P 500")
    assert all("gardening" not in a.title for a in ranked)


def test_rank_boosts_watchlist_mentions():
    articles = [
        make("Markets edge higher as investors weigh Fed path", "Reuters", hours_old=1),
        make("AAPL shares jump on record iPhone demand", "CNBC", hours_old=1),
    ]
    ranked = rank(articles, watchlist=["AAPL"], limit=10)
    assert ranked[0].title.startswith("AAPL")
    assert "AAPL" in ranked[0].tickers


def test_rank_deduplicates_similar_titles():
    articles = [
        make("Stocks rally as Fed signals rate cuts ahead", "Reuters", url="https://a.test/1"),
        make("Stocks rally as Fed signals rate cuts ahead!", "CNBC", url="https://b.test/2"),
    ]
    assert len(rank(articles, watchlist=[], limit=10)) == 1


def test_rank_caps_stories_per_source():
    articles = [
        make(f"Stock market story number {i} on earnings and yields", "Bloomberg", hours_old=1)
        for i in range(6)
    ]
    articles += [make("Wall Street stocks climb on strong earnings", "CNBC", hours_old=1)]
    ranked = rank(articles, watchlist=[], limit=4)
    assert sum(a.source == "Bloomberg" for a in ranked) <= 3
    assert any(a.source == "CNBC" for a in ranked)


def test_split_publisher_strips_google_news_suffix():
    assert _split_publisher("Stocks rally on Fed news - Reuters") == (
        "Stocks rally on Fed news",
        "Reuters",
    )
    assert _split_publisher("Stocks rally on Fed news") == ("Stocks rally on Fed news", None)
