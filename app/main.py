import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request

from app import config, db
from app.news import get_top_news
from app.quotes import get_quotes, resolve_symbol
from app.recap import generate_and_store, render_html, render_text
from app.scheduler import next_run_time, shutdown_scheduler, start_scheduler
from app.sources import SOURCE_NAMES

logging.basicConfig(level=logging.INFO)
templates = Jinja2Templates(directory=str(config.BASE_DIR / "app" / "templates"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Market Brief", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "app" / "static")), name="static")


class WatchlistItem(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"sources": SOURCE_NAMES})


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "sources": SOURCE_NAMES,
        "next_recap": next_run_time(),
        "email_configured": config.email_configured(),
        "webhook_configured": config.webhook_configured(),
    }


@app.get("/api/news")
async def news(
    limit: int = Query(config.TOP_N, ge=1, le=50), refresh: bool = False
) -> dict[str, Any]:
    symbols = [row["symbol"] for row in db.list_watchlist()]
    articles, fetched_at = await get_top_news(symbols, limit=limit, force_refresh=refresh)
    return {
        "fetched_at": fetched_at.isoformat(),
        "count": len(articles),
        "articles": [a.to_dict() for a in articles],
    }


@app.get("/api/watchlist")
async def watchlist() -> dict[str, Any]:
    rows = db.list_watchlist()
    quotes = await get_quotes([row["symbol"] for row in rows])
    names = {row["symbol"]: row["name"] for row in rows}
    for quote in quotes:
        quote["name"] = quote.get("name") or names.get(quote["symbol"], "")
    return {"count": len(quotes), "items": quotes}


@app.post("/api/watchlist", status_code=201)
async def add_symbol(item: WatchlistItem) -> dict[str, Any]:
    symbol = item.symbol.strip().upper()
    resolved = await resolve_symbol(symbol)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    db.add_to_watchlist(symbol, resolved["name"], datetime.now(timezone.utc).isoformat())
    return resolved


@app.delete("/api/watchlist/{symbol}")
async def delete_symbol(symbol: str) -> dict[str, Any]:
    if not db.remove_from_watchlist(symbol.strip().upper()):
        raise HTTPException(status_code=404, detail=f"{symbol} is not on the watchlist")
    return {"removed": symbol.strip().upper()}


@app.get("/api/recap")
async def latest_recap(date: str | None = None) -> dict[str, Any]:
    recap = db.get_recap(date)
    if recap is None:
        raise HTTPException(status_code=404, detail="No recap generated yet")
    return recap


@app.get("/api/recap/dates")
async def recap_dates() -> dict[str, Any]:
    return {"dates": db.list_recap_dates()}


@app.post("/api/recap/run")
async def run_recap(deliver: bool = True) -> dict[str, Any]:
    return await generate_and_store(deliver=deliver)


@app.get("/api/recap/preview.html", response_class=HTMLResponse)
async def recap_preview(date: str | None = None) -> HTMLResponse:
    recap = db.get_recap(date)
    if recap is None:
        raise HTTPException(status_code=404, detail="No recap generated yet")
    return HTMLResponse(render_html(recap))


@app.get("/api/recap/preview.txt")
async def recap_preview_text(date: str | None = None) -> dict[str, Any]:
    recap = db.get_recap(date)
    if recap is None:
        raise HTTPException(status_code=404, detail="No recap generated yet")
    return {"text": render_text(recap)}
