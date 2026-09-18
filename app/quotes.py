import asyncio
import math
from typing import Any

import yfinance as yf


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) else result


def build_quote(symbol: str, history: Any, last_price: float | None = None) -> dict[str, Any]:
    """Shape a yfinance history frame into a quote.

    The newest row can still be open (Yahoo leaves ``Close`` as NaN until the
    session settles), so the live price fills in for it and the previous close
    is taken from the newest row that actually has one.
    """
    quote: dict[str, Any] = {
        "symbol": symbol.upper(),
        "name": "",
        "currency": "",
        "session_date": None,
        "open": None,
        "close": None,
        "high": None,
        "low": None,
        "volume": None,
        "previous_close": None,
        "change": None,
        "change_pct": None,
        "close_is_live": False,
        "error": None,
    }

    if history is None or history.empty:
        quote["error"] = "no price data"
        return quote

    closes = [_safe_float(history.iloc[i].get("Close")) for i in range(len(history))]
    settled = [i for i, close in enumerate(closes) if close is not None]

    index = len(history) - 1
    if closes[index] is None and last_price is None:
        if not settled:
            quote["error"] = "no price data"
            return quote
        index = settled[-1]

    row = history.iloc[index]
    quote["session_date"] = history.index[index].date().isoformat()
    quote["open"] = _safe_float(row.get("Open"))
    quote["high"] = _safe_float(row.get("High"))
    quote["low"] = _safe_float(row.get("Low"))
    volume = _safe_float(row.get("Volume"))
    quote["volume"] = int(volume) if volume is not None else None

    quote["close"] = closes[index]
    if quote["close"] is None:
        quote["close"] = _safe_float(last_price)
        quote["close_is_live"] = quote["close"] is not None

    earlier_settled = [i for i in settled if i < index]
    if earlier_settled:
        quote["previous_close"] = closes[earlier_settled[-1]]

    if quote["close"] is not None and quote["previous_close"]:
        quote["change"] = quote["close"] - quote["previous_close"]
        quote["change_pct"] = quote["change"] / quote["previous_close"] * 100.0
    return quote


def _last_price(ticker: yf.Ticker) -> float | None:
    try:
        return _safe_float(ticker.fast_info.get("last_price"))
    except Exception:  # noqa: BLE001 - yfinance raises assorted network/parse errors
        return None


def _fetch_quote(symbol: str) -> dict[str, Any]:
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="5d", auto_adjust=False)
    quote = build_quote(symbol, history, _last_price(ticker))
    if quote["error"]:
        return quote

    try:
        info = ticker.get_info()
    except Exception:  # noqa: BLE001 - yfinance raises assorted network/parse errors
        info = {}
    quote["name"] = info.get("shortName") or info.get("longName") or ""
    quote["currency"] = info.get("currency") or ""
    if quote["close"] is None:
        quote["close"] = _safe_float(info.get("regularMarketPrice"))
        quote["close_is_live"] = quote["close"] is not None
        if quote["close"] is not None and quote["previous_close"]:
            quote["change"] = quote["close"] - quote["previous_close"]
            quote["change_pct"] = quote["change"] / quote["previous_close"] * 100.0
    return quote


async def get_quote(symbol: str) -> dict[str, Any]:
    return await asyncio.to_thread(_fetch_quote, symbol)


async def get_quotes(symbols: list[str]) -> list[dict[str, Any]]:
    if not symbols:
        return []
    results = await asyncio.gather(*(get_quote(s) for s in symbols), return_exceptions=True)
    quotes: list[dict[str, Any]] = []
    for symbol, result in zip(symbols, results):
        if isinstance(result, BaseException):
            quotes.append({"symbol": symbol.upper(), "error": str(result)})
        else:
            quotes.append(result)
    return quotes


def _resolve(symbol: str) -> dict[str, Any] | None:
    try:
        info = yf.Ticker(symbol).get_info()
    except Exception:  # noqa: BLE001
        return None
    name = info.get("shortName") or info.get("longName")
    if not name:
        return None
    return {"symbol": symbol.upper(), "name": name, "exchange": info.get("fullExchangeName", "")}


async def resolve_symbol(symbol: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_resolve, symbol)
