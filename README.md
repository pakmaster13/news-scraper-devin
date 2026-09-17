# Market Brief

Aggregates the top 10 stock-market stories from Bloomberg, Reuters, CNBC, Yahoo Finance and
AAStocks, and emails/posts a morning recap of your watchlist (open, close, day range, notable
headlines).

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # optional: email / webhook delivery
set -a && . ./.env && set +a
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000.

## How sources are collected

| Source | Method |
| --- | --- |
| Bloomberg | official markets/economics RSS feeds |
| Reuters | Google News publisher feed restricted to `site:reuters.com` (reuters.com returns 401 to crawlers) |
| CNBC | markets/finance RSS feeds |
| Yahoo Finance | news RSS + per-ticker headline feeds |
| AAStocks | HTML scrape of the popular/latest news pages |

Stories are scored by recency, source weight, market-keyword relevance and watchlist-ticker
mentions, then de-duplicated by title similarity down to the top 10.

## Morning recap

APScheduler runs the recap every weekday at `RECAP_HOUR:RECAP_MINUTE` in `RECAP_TIMEZONE`, stores
it in SQLite, shows it on the dashboard and delivers it to any configured channel (SMTP email and
webhook). "Generate now" / "Generate & send" trigger it on demand.

## API

| Endpoint | Description |
| --- | --- |
| `GET /api/news?limit=10&refresh=true` | ranked market stories |
| `GET /api/watchlist` | watchlist with latest quotes |
| `POST /api/watchlist` `{"symbol":"AAPL"}` | add a symbol (validated via Yahoo Finance) |
| `DELETE /api/watchlist/{symbol}` | remove a symbol |
| `POST /api/recap/run?deliver=true` | build, store and deliver a recap |
| `GET /api/recap` | latest stored recap |
| `GET /api/recap/preview.html` | rendered email body |
