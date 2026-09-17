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


def _fetch_quote(symbol: str) -> dict[str, Any]:
    ticker = yf.Ticker(symbol)
    history = ticker.history(period="5d", auto_adjust=False)
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
        "error": None,
    }

    if history.empty:
        quote["error"] = "no price data"
        return quote

    latest = history.iloc[-1]
    quote["session_date"] = history.index[-1].date().isoformat()
    quote["open"] = _safe_float(latest.get("Open"))
    quote["close"] = _safe_float(latest.get("Close"))
    quote["high"] = _safe_float(latest.get("High"))
    quote["low"] = _safe_float(latest.get("Low"))
    volume = _safe_float(latest.get("Volume"))
    quote["volume"] = int(volume) if volume is not None else None
    if len(history) > 1:
        quote["previous_close"] = _safe_float(history.iloc[-2].get("Close"))

    try:
        info = ticker.get_info()
    except Exception:  # noqa: BLE001 - yfinance raises assorted network/parse errors
        info = {}
    quote["name"] = info.get("shortName") or info.get("longName") or ""
    quote["currency"] = info.get("currency") or ""

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
