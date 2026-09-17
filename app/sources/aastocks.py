import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.sources.base import Article, clean_text, fetch

BASE_URL = "http://www.aastocks.com"
PAGES = [
    "http://www.aastocks.com/en/stocks/news/aafn/popular-news",
    "http://www.aastocks.com/en/stocks/news/aafn/latest-news",
]
_LINK = re.compile(r"/en/stocks/news/aafn-con/")
_HK_CODE = re.compile(r"\b(\d{5})\.HK\b")


async def collect_aastocks(client: httpx.AsyncClient) -> list[Article]:
    articles: list[Article] = []
    seen: set[str] = set()
    for page in PAGES:
        try:
            response = await fetch(client, page)
            response.raise_for_status()
        except httpx.HTTPError:
            continue
        soup = BeautifulSoup(response.text, "lxml")
        for anchor in soup.find_all("a", href=_LINK):
            title = clean_text(anchor.get_text(" ", strip=True), limit=240)
            href = anchor.get("href") or ""
            if len(title) < 15 or not href:
                continue
            url = urljoin(BASE_URL, href)
            if url in seen:
                continue
            seen.add(url)
            articles.append(
                Article(
                    title=title,
                    url=url,
                    source="AAStocks",
                    tickers=_HK_CODE.findall(title),
                )
            )
    return articles
