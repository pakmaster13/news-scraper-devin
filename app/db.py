import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recaps (
    recap_date TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    delivery TEXT NOT NULL DEFAULT '{}'
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


def list_watchlist() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT symbol, name, added_at FROM watchlist ORDER BY symbol").fetchall()
    return [dict(r) for r in rows]


def add_to_watchlist(symbol: str, name: str, added_at: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO watchlist (symbol, name, added_at) VALUES (?, ?, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET name = excluded.name",
            (symbol, name, added_at),
        )


def remove_from_watchlist(symbol: str) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
    return cur.rowcount > 0


def save_recap(recap_date: str, generated_at: str, payload: dict[str, Any], delivery: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO recaps (recap_date, generated_at, payload, delivery) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(recap_date) DO UPDATE SET generated_at = excluded.generated_at, "
            "payload = excluded.payload, delivery = excluded.delivery",
            (recap_date, generated_at, json.dumps(payload), json.dumps(delivery)),
        )


def get_recap(recap_date: str | None = None) -> dict[str, Any] | None:
    with connect() as conn:
        if recap_date:
            row = conn.execute("SELECT * FROM recaps WHERE recap_date = ?", (recap_date,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM recaps ORDER BY recap_date DESC LIMIT 1").fetchone()
    if row is None:
        return None
    payload = json.loads(row["payload"])
    payload["delivery"] = json.loads(row["delivery"])
    return payload


def list_recap_dates(limit: int = 30) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT recap_date FROM recaps ORDER BY recap_date DESC LIMIT ?", (limit,)
        ).fetchall()
    return [r["recap_date"] for r in rows]
