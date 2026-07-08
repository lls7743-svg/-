"""One-off test of a single hypothesis: buy when price makes a new N-day
high, sell on a new M-day low or a stop-loss. Uses daily bars over 6 months
(Yahoo Finance's intraday history caps out at 60 days, too short for a
6-month window) -- this makes it a swing/position-style test, not the
intraday day-trading engine in trader/strategy.py, and it deliberately does
not share code with it so the two don't get tangled.
"""
from __future__ import annotations

import json
from typing import Callable

import pandas as pd

from . import config
from .portfolio import Portfolio

ENTRY_WINDOW_DAYS = 20   # buy when close breaks the highest high of the prior N days
EXIT_WINDOW_DAYS = 10    # sell when close breaks the lowest low of the prior N days
STOP_LOSS_PCT = 0.05
PERIOD = "6mo"
INTERVAL = "1d"


def fetch_daily(symbols: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    raw = yf.download(
        tickers=symbols, period=PERIOD, interval=INTERVAL,
        group_by="ticker", auto_adjust=False, threads=True, progress=False,
    )
    out = {}
    for symbol in symbols:
        try:
            df = raw if len(symbols) == 1 else raw[symbol]
        except KeyError:
            continue
        df = df.dropna(how="all").rename(columns=str.lower)
        if not df.empty:
            out[symbol] = df[["open", "high", "low", "close", "volume"]]
    return out


def run(symbols: list[str] | None = None, fetch: Callable[[list[str]], dict] = fetch_daily) -> dict:
    symbols = symbols if symbols is not None else config.WATCHLIST
    all_data = fetch(symbols)
    if not all_data:
        raise RuntimeError("No market data returned -- check network access / tickers")

    timestamps = sorted(set().union(*(df.index for df in all_data.values())))
    portfolio = Portfolio()
    trade_log: list[dict] = []

    for t in timestamps:
        # --- exits ---
        for symbol in list(portfolio.positions.keys()):
            df = all_data.get(symbol)
            if df is None or t not in df.index:
                continue
            hist = df.loc[:t]
            if len(hist) < EXIT_WINDOW_DAYS + 1:
                continue
            price = float(hist["close"].iloc[-1])
            pos = portfolio.positions[symbol]
            exit_low = hist["low"].iloc[-EXIT_WINDOW_DAYS - 1 : -1].min()
            reason = None
            if price <= pos.entry_price * (1 - STOP_LOSS_PCT):
                reason = "stop_loss"
            elif price < exit_low:
                reason = "new_low_exit"
            if reason:
                trade_log.append(portfolio.sell(symbol, price, t.isoformat(), reason))

        # --- entries ---
        if len(portfolio.positions) < config.MAX_POSITIONS:
            candidates = []
            for symbol in symbols:
                if symbol in portfolio.positions:
                    continue
                df = all_data.get(symbol)
                if df is None or t not in df.index:
                    continue
                hist = df.loc[:t]
                if len(hist) < ENTRY_WINDOW_DAYS + 1:
                    continue
                price = float(hist["close"].iloc[-1])
                prior_high = hist["high"].iloc[-ENTRY_WINDOW_DAYS - 1 : -1].max()
                if price > prior_high:
                    strength = (price - prior_high) / prior_high
                    candidates.append((strength, symbol, price))
            candidates.sort(key=lambda c: c[0], reverse=True)

            last_prices = {
                s: float(d.loc[:t]["close"].iloc[-1]) for s, d in all_data.items() if t in d.index
            }
            for _strength, symbol, price in candidates:
                if len(portfolio.positions) >= config.MAX_POSITIONS:
                    break
                equity = portfolio.equity(last_prices)
                budget = equity * config.POSITION_SIZE_FRACTION
                qty = int(budget // price // config.SHARE_LOT_SIZE) * config.SHARE_LOT_SIZE
                if qty <= 0 or qty * price > portfolio.cash:
                    continue
                trade_log.append(portfolio.buy(symbol, qty, price, t.isoformat(), reason="new_high_breakout"))

    closed = [tr for tr in trade_log if tr["side"] == "SELL"]
    wins = [tr for tr in closed if tr["pnl"] > 0]
    last_prices = {s: float(d["close"].iloc[-1]) for s, d in all_data.items()}
    final_equity = portfolio.equity(last_prices)

    return {
        "period_start": timestamps[0].isoformat() if timestamps else None,
        "period_end": timestamps[-1].isoformat() if timestamps else None,
        "symbols_scanned": len(symbols),
        "entry_window_days": ENTRY_WINDOW_DAYS,
        "exit_window_days": EXIT_WINDOW_DAYS,
        "stop_loss_pct": STOP_LOSS_PCT,
        "initial_cash": portfolio.initial_cash,
        "final_equity": round(final_equity, 2),
        "return_pct": round((final_equity - portfolio.initial_cash) / portfolio.initial_cash * 100, 2),
        "num_round_trips": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "total_realized_pnl": round(sum(tr["pnl"] for tr in closed), 2),
        "still_open_positions": len(portfolio.positions),
    }


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
