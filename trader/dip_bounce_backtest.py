"""One-off test of a mean-reversion hypothesis: buy a stock that has already
dropped 5%+ from today's opening price within the first ~90 minutes of the
session, and take profit quickly at +1%. Uses the same 15-minute intraday
bars as the live engine (config.INTERVAL), capped at Yahoo Finance's 60-day
intraday history limit -- a shorter window than the 6-month daily-bar
experiments (breakout_backtest.py, trend_backtest.py) because this
hypothesis is about same-day open behavior, which only exists in intraday
data. Kept separate from the live engine and the other experiments.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Callable

from . import config
from .chart_data import save_backtest_snapshot
from .data import fetch_history_batch, is_force_close_time
from .portfolio import Portfolio, DATA_DIR

DROP_PCT = 0.05                      # buy once price is down >=5% from today's open
TAKE_PROFIT_PCT = 0.01               # sell at +1% from entry
ENTRY_WINDOW_END = dt.time(10, 30)   # only look for the dip within the first ~90 min

OUTPUT_DIR = DATA_DIR / "dip_bounce_backtest"


def run(
    symbols: list[str] | None = None,
    fetch: Callable[[list[str]], dict] = fetch_history_batch,
    output_dir: Path | None = OUTPUT_DIR,
) -> dict:
    symbols = symbols if symbols is not None else config.WATCHLIST
    all_data = fetch(symbols)
    if not all_data:
        raise RuntimeError("No market data returned -- check network access / tickers")

    # Each symbol's opening price per calendar day (first bar of that date).
    day_opens = {symbol: df.groupby(df.index.date)["open"].first() for symbol, df in all_data.items()}
    entered_today: dict[str, object] = {}  # symbol -> date already tried, so we don't re-enter same day

    timestamps = sorted(set().union(*(df.index for df in all_data.values())))
    portfolio = Portfolio()
    trade_log: list[dict] = []
    equity_curve: list[dict] = []

    for t in timestamps:
        today = t.date()
        now = t.to_pydatetime()

        # --- exits ---
        for symbol in list(portfolio.positions.keys()):
            df = all_data.get(symbol)
            if df is None or t not in df.index:
                continue
            price = float(df.loc[t, "close"])
            pos = portfolio.positions[symbol]
            reason = None
            if is_force_close_time(now):
                reason = "day_trade_close"
            elif price >= pos.entry_price * (1 + TAKE_PROFIT_PCT):
                reason = "take_profit_1pct"
            if reason:
                trade_log.append(portfolio.sell(symbol, price, t.isoformat(), reason))

        last_prices = {s: float(d.loc[t, "close"]) for s, d in all_data.items() if t in d.index}

        # --- entries: only within the early-session window, once per symbol per day ---
        if t.time() <= ENTRY_WINDOW_END and len(portfolio.positions) < config.MAX_POSITIONS:
            candidates = []
            for symbol in symbols:
                if symbol in portfolio.positions or entered_today.get(symbol) == today:
                    continue
                df = all_data.get(symbol)
                if df is None or t not in df.index:
                    continue
                opens = day_opens.get(symbol)
                if opens is None or today not in opens.index:
                    continue
                day_open = float(opens.loc[today])
                if day_open <= 0:
                    continue
                price = float(df.loc[t, "close"])
                drop = (day_open - price) / day_open
                if drop >= DROP_PCT:
                    candidates.append((drop, symbol, price))
            candidates.sort(key=lambda c: c[0], reverse=True)

            for _drop, symbol, price in candidates:
                if len(portfolio.positions) >= config.MAX_POSITIONS:
                    break
                entered_today[symbol] = today
                equity = portfolio.equity(last_prices)
                budget = equity * config.POSITION_SIZE_FRACTION
                qty = int(budget // price // config.SHARE_LOT_SIZE) * config.SHARE_LOT_SIZE
                if qty <= 0 or qty * price > portfolio.cash:
                    continue
                trade_log.append(portfolio.buy(symbol, qty, price, t.isoformat(), reason="dip_5pct"))

        equity_curve.append({"t": t.isoformat(), "equity": portfolio.equity(last_prices)})

    closed = [tr for tr in trade_log if tr["side"] == "SELL"]
    wins = [tr for tr in closed if tr["pnl"] > 0]
    last_prices = {s: float(d["close"].iloc[-1]) for s, d in all_data.items()}
    final_equity = portfolio.equity(last_prices)

    summary = {
        "period_start": timestamps[0].isoformat() if timestamps else None,
        "period_end": timestamps[-1].isoformat() if timestamps else None,
        "symbols_scanned": len(symbols),
        "drop_pct_threshold": DROP_PCT,
        "take_profit_pct": TAKE_PROFIT_PCT,
        "entry_window_end_jst": ENTRY_WINDOW_END.isoformat(),
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
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
