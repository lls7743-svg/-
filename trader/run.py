"""Entry point: one trading cycle. Run every ~30 minutes during TSE hours via
the scheduled GitHub Actions workflow (see .github/workflows/trade.yml)."""
from __future__ import annotations

import datetime as dt
import json

from . import config
from .data import fetch_history, is_market_open, now_jst
from .portfolio import Portfolio, append_trades, append_equity_point, DATA_DIR
from .strategy import decide_and_execute

PRICES_DIR = DATA_DIR / "prices"


def _save_price_history(symbol: str, df) -> None:
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = df.index.max() - dt.timedelta(days=config.PRICE_HISTORY_KEEP_DAYS)
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
    path = PRICES_DIR / f"{symbol}.json"
    path.write_text(json.dumps({"symbol": symbol, "bars": bars}, ensure_ascii=False, indent=2))


def _update_prices_index(symbols: list[str]) -> None:
    path = PRICES_DIR / "index.json"
    existing = set(json.loads(path.read_text())) if path.exists() else set()
    existing.update(symbols)
    path.write_text(json.dumps(sorted(existing), ensure_ascii=False, indent=2))


def main() -> None:
    now = now_jst()
    now_iso = now.isoformat()
    portfolio = Portfolio.load()

    if not is_market_open(now):
        print(f"[{now_iso}] Market closed, skipping cycle.")
        return

    symbols = sorted(set(config.WATCHLIST) | set(portfolio.positions.keys()))
    market_data = {}
    for symbol in symbols:
        try:
            df = fetch_history(symbol)
        except Exception as exc:  # noqa: BLE001 - keep the cycle alive on a bad ticker
            print(f"[{now_iso}] Failed to fetch {symbol}: {exc}")
            continue
        if df.empty:
            continue
        market_data[symbol] = df
        _save_price_history(symbol, df)

    _update_prices_index(list(market_data.keys()))

    trades = decide_and_execute(portfolio, market_data, now, now_iso)
    portfolio.last_updated = now_iso
    portfolio.save()
    append_trades(trades)

    last_prices = {sym: float(df["close"].iloc[-1]) for sym, df in market_data.items()}
    append_equity_point(now_iso, portfolio.equity(last_prices))

    for t in trades:
        print(f"[{now_iso}] {t['side']} {t.get('qty')} {t['symbol']} @ {t['price']} "
              f"({t.get('reason', 'signal')})")
    if not trades:
        print(f"[{now_iso}] No trades this cycle. Cash={portfolio.cash:.0f} "
              f"Positions={list(portfolio.positions.keys())}")


if __name__ == "__main__":
    main()
