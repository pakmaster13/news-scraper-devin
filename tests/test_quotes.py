import pandas as pd

from app.quotes import build_quote


def frame(rows: list[dict[str, float | None]]) -> pd.DataFrame:
    dates = pd.to_datetime([f"2026-09-{15 + i}" for i in range(len(rows))])
    return pd.DataFrame(rows, index=dates)


SETTLED = [
    {"Open": 330.0, "High": 332.0, "Low": 329.0, "Close": 331.0, "Volume": 1000},
    {"Open": 332.0, "High": 335.0, "Low": 331.0, "Close": 334.0, "Volume": 2000},
]


def test_build_quote_uses_latest_settled_session():
    quote = build_quote("AAPL", frame(SETTLED))
    assert quote["session_date"] == "2026-09-16"
    assert quote["close"] == 334.0
    assert quote["previous_close"] == 331.0
    assert round(quote["change_pct"], 3) == round(3.0 / 331.0 * 100, 3)
    assert quote["close_is_live"] is False


def test_build_quote_fills_unsettled_close_with_live_price():
    rows = SETTLED + [{"Open": 336.0, "High": 339.0, "Low": 335.0, "Close": None, "Volume": 500}]
    quote = build_quote("AAPL", frame(rows), last_price=338.0)
    assert quote["session_date"] == "2026-09-17"
    assert quote["close"] == 338.0
    assert quote["close_is_live"] is True
    assert quote["previous_close"] == 334.0
    assert quote["change"] == 4.0


def test_build_quote_falls_back_to_previous_session_without_live_price():
    rows = SETTLED + [{"Open": 336.0, "High": 339.0, "Low": 335.0, "Close": None, "Volume": 500}]
    quote = build_quote("AAPL", frame(rows), last_price=None)
    assert quote["session_date"] == "2026-09-16"
    assert quote["close"] == 334.0
    assert quote["previous_close"] == 331.0
    assert quote["close_is_live"] is False


def test_build_quote_reports_missing_data():
    assert build_quote("AAPL", frame([]))["error"] == "no price data"
    unsettled = [{"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": None, "Volume": 0}]
    assert build_quote("AAPL", frame(unsettled))["error"] == "no price data"
