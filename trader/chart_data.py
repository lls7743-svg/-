"""Shared helpers for writing dashboard-consumable price/trade JSON."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import config


def save_price_history(prices_dir: Path, symbol: str, df, keep_days: int | None = config.PRICE_HISTORY_KEEP_DAYS) -> None:
    prices_dir.mkdir(parents=True, exist_ok=True)
    if keep_days is None:
        trimmed = df
    else:
        cutoff = df.index.max() - dt.timedelta(days=keep_days)
        trimmed = df[df.index >= cutoff]
    bars = [
        {
            "t": ts.isoformat(),
            "o": round(float(row.open), 2),
            "h": round(float(row.high), 2),
            "l": round(float(row.low), 2),
            "c": round(float(row.close), 2),
        }
        for ts, row in trimmed.iterrows()
    ]
    path = prices_dir / f"{symbol}.json"
    path.write_text(json.dumps({"symbol": symbol, "bars": bars}, ensure_ascii=False, indent=2))


def update_prices_index(prices_dir: Path, symbols: list[str]) -> None:
    prices_dir.mkdir(parents=True, exist_ok=True)
    path = prices_dir / "index.json"
    existing = set(json.loads(path.read_text())) if path.exists() else set()
    existing.update(symbols)
    path.write_text(json.dumps(sorted(existing), ensure_ascii=False, indent=2))
