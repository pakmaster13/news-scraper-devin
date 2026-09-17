import asyncio
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.config import RECAP_TIMEZONE, TOP_N
from app.db import list_watchlist, save_recap
from app.news import get_top_news
from app.quotes import get_quotes
from app.sources import collect_ticker_news


def _movers(quotes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    ranked = [q for q in quotes if q.get("change_pct") is not None]
    ranked.sort(key=lambda q: q["change_pct"], reverse=True)
    return {"gainers": ranked[:3], "losers": list(reversed(ranked[-3:]))}


async def build_recap(force_refresh: bool = True) -> dict[str, Any]:
    watchlist = list_watchlist()
    symbols = [row["symbol"] for row in watchlist]

    quotes_task = get_quotes(symbols)
    news_task = get_top_news(symbols, limit=TOP_N, force_refresh=force_refresh)
    async with httpx.AsyncClient() as client:
        ticker_news_task = asyncio.gather(
            *(collect_ticker_news(client, row["symbol"], row["name"]) for row in watchlist),
            return_exceptions=True,
        )
        quotes, (top_news, _), ticker_news = await asyncio.gather(
            quotes_task, news_task, ticker_news_task
        )

    for quote, headlines in zip(quotes, ticker_news):
        if isinstance(headlines, BaseException):
            quote["headlines"] = []
        else:
            quote["headlines"] = [a.to_dict() for a in headlines]

    local_now = datetime.now(ZoneInfo(RECAP_TIMEZONE))
    payload = {
        "recap_date": local_now.date().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": RECAP_TIMEZONE,
        "watchlist": quotes,
        "movers": _movers(quotes),
        "market_news": [a.to_dict() for a in top_news],
    }
    return payload


def render_text(recap: dict[str, Any]) -> str:
    lines = [f"Market Brief — {recap['recap_date']}", ""]
    if recap["watchlist"]:
        lines.append("Watchlist")
        for quote in recap["watchlist"]:
            if quote.get("error"):
                lines.append(f"  {quote['symbol']}: unavailable ({quote['error']})")
                continue
            if quote.get("open") is None or quote.get("close") is None:
                lines.append(f"  {quote['symbol']}: partial data")
                continue
            pct = quote.get("change_pct")
            move = f"{pct:+.2f}%" if pct is not None else "n/a"
            lines.append(
                f"  {quote['symbol']} ({quote.get('name') or 'n/a'}) {quote.get('session_date')}: "
                f"open {quote['open']:.2f} close {quote['close']:.2f} {move} "
                f"| range {quote['low']:.2f}-{quote['high']:.2f}"
            )
            for headline in quote.get("headlines", [])[:2]:
                lines.append(f"      - {headline['title']} ({headline['url']})")
        lines.append("")
    lines.append(f"Top {len(recap['market_news'])} market stories")
    for i, article in enumerate(recap["market_news"], start=1):
        lines.append(f"  {i}. [{article['source']}] {article['title']}")
        lines.append(f"     {article['url']}")
    return "\n".join(lines)


def render_html(recap: dict[str, Any]) -> str:
    rows = []
    for quote in recap["watchlist"]:
        if quote.get("error") or quote.get("close") is None:
            rows.append(
                f"<tr><td>{quote['symbol']}</td><td colspan='5'>data unavailable</td></tr>"
            )
            continue
        pct = quote.get("change_pct")
        color = "#128a4b" if (pct or 0) >= 0 else "#c0392b"
        move = f"{pct:+.2f}%" if pct is not None else "n/a"
        rows.append(
            f"<tr><td><b>{quote['symbol']}</b><br><small>{quote.get('name','')}</small></td>"
            f"<td>{quote['open']:.2f}</td><td>{quote['close']:.2f}</td>"
            f"<td style='color:{color}'>{move}</td>"
            f"<td>{quote['low']:.2f} – {quote['high']:.2f}</td>"
            f"<td>{(quote.get('volume') or 0):,}</td></tr>"
        )
    news = "".join(
        f"<li><a href='{a['url']}'>{a['title']}</a> <small>— {a['source']}</small></li>"
        for a in recap["market_news"]
    )
    table = (
        "<table cellpadding='8' cellspacing='0' border='0' style='border-collapse:collapse;width:100%'>"
        "<tr style='text-align:left;background:#f2f4f7'><th>Symbol</th><th>Open</th><th>Close</th>"
        "<th>Change</th><th>Day range</th><th>Volume</th></tr>" + "".join(rows) + "</table>"
        if rows
        else "<p>No symbols on the watchlist yet.</p>"
    )
    return (
        "<div style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:720px\">"
        f"<h2>Market Brief — {recap['recap_date']}</h2>"
        "<h3>Watchlist</h3>"
        f"{table}"
        f"<h3>Top {len(recap['market_news'])} market stories</h3><ol>{news}</ol>"
        f"<p style='color:#667085;font-size:12px'>Generated {recap['generated_at']} "
        f"({recap['timezone']})</p></div>"
    )


async def generate_and_store(deliver: bool = True) -> dict[str, Any]:
    from app.notify import deliver_recap  # local import avoids circular dependency

    recap = await build_recap()
    delivery = await deliver_recap(recap) if deliver else {"skipped": True}
    recap["delivery"] = delivery
    save_recap(recap["recap_date"], recap["generated_at"], recap, delivery)
    return recap
