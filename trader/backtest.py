"""Backtest the live strategy against recent historical data.

Replays the exact same trader.strategy logic bar-by-bar over historical
prices, so the result reflects the real rules (not a re-implementation that
could drift from what actually runs live). This is capped at roughly the
last 60 days because that is the longest 30-minute intraday history Yahoo
Finance exposes -- treat the output as a rough sanity check of the strategy's
recent behavior, not a long-run track record. Past performance here does not
predict future results, and this does not model slippage, spreads, or the
possibility that a signal's price wasn't actually fillable.

Besides the printed summary, this writes the same trades/portfolio/price
JSON shape the live dashboard reads (under data/backtest/) so the backtested
trades can be viewed as buy/sell markers on real charts, the same way live
trades are: open index.html?data=backtest.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from . import config
from .chart_data import save_backtest_snapshot
from .data import fetch_history_batch
from .portfolio import Portfolio, DATA_DIR
from .strategy import decide_and_execute

BACKTEST_DIR = DATA_DIR / "backtest"


def run_backtest(
    symbols: list[str] | None = None,
    fetch: Callable[[list[str]], dict] = fetch_history_batch,
    output_dir: Path | None = BACKTEST_DIR,
) -> dict:
    symbols = symbols if symbols is not None else config.WATCHLIST
    all_data = fetch(symbols)
    if not all_data:
        raise RuntimeError("No market data returned -- check network access / tickers")

    # Replay bar-by-bar across the union of every symbol's timestamps, only
    # ever showing the strategy data up to and including "now" at each step
    # so later bars can't leak into earlier decisions.
    timestamps = sorted(set().union(*(df.index for df in all_data.values())))

    portfolio = Portfolio()
    trade_log: list[dict] = []
    equity_curve: list[dict] = []

    for t in timestamps:
        market_data = {}
        for symbol, df in all_data.items():
            sliced = df.loc[:t]
            if len(sliced) >= config.MA_LONG + 1:
                market_data[symbol] = sliced
        now = t.to_pydatetime()
        trades = decide_and_execute(portfolio, market_data, now, now.isoformat())
        trade_log.extend(trades)
        last_prices = {s: float(d["close"].iloc[-1]) for s, d in market_data.items()}
        equity_curve.append({"t": now.isoformat(), "equity": portfolio.equity(last_prices)})

    closed = [tr for tr in trade_log if tr["side"] == "SELL"]
    wins = [tr for tr in closed if tr["pnl"] > 0]
    final_equity = equity_curve[-1]["equity"] if equity_curve else portfolio.initial_cash

    summary = {
        "period_start": timestamps[0].isoformat() if timestamps else None,
        "period_end": timestamps[-1].isoformat() if timestamps else None,
        "symbols_scanned": len(symbols),
        "initial_cash": portfolio.initial_cash,
        "final_equity": round(final_equity, 2),
        "return_pct": round((final_equity - portfolio.initial_cash) / portfolio.initial_cash * 100, 2),
        "num_round_trips": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "total_realized_pnl": round(sum(tr["pnl"] for tr in closed), 2),
        "still_open_positions": len(portfolio.positions),
    }

    if output_dir is not None:
        save_backtest_snapshot(output_dir, portfolio, trade_log, equity_curve, all_data, summary)
    return summary


def main() -> None:
    print(json.dumps(run_backtest(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
