"""Entry point: one trading cycle. Run every ~30 minutes during TSE hours via
the scheduled GitHub Actions workflow (see .github/workflows/trade.yml)."""
from __future__ import annotations

from . import config
from .chart_data import save_price_history, update_prices_index
from .data import fetch_history_batch, is_market_open, now_jst
from .portfolio import Portfolio, append_trades, append_equity_point, DATA_DIR
from .strategy import decide_and_execute

PRICES_DIR = DATA_DIR / "prices"


def main() -> None:
    now = now_jst()
    now_iso = now.isoformat()
    portfolio = Portfolio.load()

    if not is_market_open(now):
        print(f"[{now_iso}] Market closed, skipping cycle.")
        return

    symbols = sorted(set(config.WATCHLIST) | set(portfolio.positions.keys()))
    try:
        market_data = fetch_history_batch(symbols)
    except Exception as exc:  # noqa: BLE001 - keep the cycle alive on a bad batch fetch
        print(f"[{now_iso}] Failed to fetch market data: {exc}")
        market_data = {}

    trades = decide_and_execute(portfolio, market_data, now, now_iso)
    portfolio.last_updated = now_iso
    portfolio.save()
    append_trades(trades)

    # Only persist chart data for symbols the dashboard actually needs (open
    # positions + anything traded this cycle) -- scanning ~150 candidates
    # every cycle shouldn't mean writing ~150 JSON files every cycle.
    relevant_symbols = set(portfolio.positions.keys()) | {t["symbol"] for t in trades}
    for symbol in relevant_symbols:
        df = market_data.get(symbol)
        if df is not None and not df.empty:
            save_price_history(PRICES_DIR, symbol, df)
    update_prices_index(PRICES_DIR, list(relevant_symbols))

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
