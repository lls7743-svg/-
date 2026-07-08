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


def save_backtest_snapshot(output_dir: Path, portfolio, trade_log: list[dict], equity_curve: list[dict],
                            all_data: dict, summary: dict) -> None:
    """Write the same trades/portfolio/equity/price JSON shape the live
    dashboard reads, so any backtest's trades can be viewed as buy/sell
    markers on real charts via index.html?data=<output_dir name>."""
    from dataclasses import asdict

    output_dir.mkdir(parents=True, exist_ok=True)
    prices_dir = output_dir / "prices"

    payload = {
        "cash": portfolio.cash,
        "initial_cash": portfolio.initial_cash,
        "realized_pnl": portfolio.realized_pnl,
        "positions": {sym: asdict(pos) for sym, pos in portfolio.positions.items()},
        "last_updated": equity_curve[-1]["t"] if equity_curve else None,
    }
    (output_dir / "portfolio.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    (output_dir / "trades.json").write_text(json.dumps(trade_log, ensure_ascii=False, indent=2))
    (output_dir / "equity.json").write_text(json.dumps(equity_curve, ensure_ascii=False, indent=2))
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    # Only chart the symbols that actually traded (or ended up held) -- no
    # need for chart JSON on every scanned name.
    relevant_symbols = set(portfolio.positions.keys()) | {t["symbol"] for t in trade_log}
    for symbol in relevant_symbols:
        df = all_data.get(symbol)
        if df is not None and not df.empty:
            save_price_history(prices_dir, symbol, df, keep_days=None)
    update_prices_index(prices_dir, list(relevant_symbols))
