"""One-off test of a trend-following hypothesis: buy when a short moving
average crosses above a longer one (an uptrend is starting -- "buy when it's
trending up"), sell when it crosses back below (the uptrend is ending --
"sell when it turns down"). Daily bars, 6 months. Kept separate from the
intraday day-trading engine and the other one-off experiments (breakout_backtest.py)
so none of them get tangled together.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd

from . import config
from .chart_data import save_backtest_snapshot
from .indicators import sma, golden_cross, dead_cross
from .portfolio import Portfolio, DATA_DIR

MA_SHORT_DAYS = 10
MA_LONG_DAYS = 30
PERIOD = "6mo"
INTERVAL = "1d"

OUTPUT_DIR = DATA_DIR / "trend_backtest"


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


def run(
    symbols: list[str] | None = None,
    fetch: Callable[[list[str]], dict] = fetch_daily,
    output_dir: Path | None = OUTPUT_DIR,
) -> dict:
    symbols = symbols if symbols is not None else config.WATCHLIST
    all_data = fetch(symbols)
    if not all_data:
        raise RuntimeError("No market data returned -- check network access / tickers")

    timestamps = sorted(set().union(*(df.index for df in all_data.values())))
    portfolio = Portfolio()
    trade_log: list[dict] = []
    equity_curve: list[dict] = []

    for t in timestamps:
        # --- exits: trend turned down ---
        for symbol in list(portfolio.positions.keys()):
            df = all_data.get(symbol)
            if df is None or t not in df.index:
                continue
            hist = df.loc[:t]
            if len(hist) < MA_LONG_DAYS + 1:
                continue
            ma_short = sma(hist["close"], MA_SHORT_DAYS)
            ma_long = sma(hist["close"], MA_LONG_DAYS)
            price = float(hist["close"].iloc[-1])
            if dead_cross(ma_short, ma_long):
                trade_log.append(portfolio.sell(symbol, price, t.isoformat(), "trend_down"))

        last_prices = {
            s: float(d.loc[:t]["close"].iloc[-1]) for s, d in all_data.items() if t in d.index
        }

        # --- entries: trend turned up ---
        if len(portfolio.positions) < config.MAX_POSITIONS:
            candidates = []
            for symbol in symbols:
                if symbol in portfolio.positions:
                    continue
                df = all_data.get(symbol)
                if df is None or t not in df.index:
                    continue
                hist = df.loc[:t]
                if len(hist) < MA_LONG_DAYS + 1:
                    continue
                ma_short = sma(hist["close"], MA_SHORT_DAYS)
                ma_long = sma(hist["close"], MA_LONG_DAYS)
                if golden_cross(ma_short, ma_long):
                    price = float(hist["close"].iloc[-1])
                    strength = (ma_short.iloc[-1] - ma_long.iloc[-1]) / ma_long.iloc[-1]
                    candidates.append((strength, symbol, price))
            candidates.sort(key=lambda c: c[0], reverse=True)

            for _strength, symbol, price in candidates:
                if len(portfolio.positions) >= config.MAX_POSITIONS:
                    break
                equity = portfolio.equity(last_prices)
                budget = equity * config.POSITION_SIZE_FRACTION
                qty = int(budget // price // config.SHARE_LOT_SIZE) * config.SHARE_LOT_SIZE
                if qty <= 0 or qty * price > portfolio.cash:
                    continue
                trade_log.append(portfolio.buy(symbol, qty, price, t.isoformat(), reason="trend_up"))

        equity_curve.append({"t": t.isoformat(), "equity": portfolio.equity(last_prices)})

    closed = [tr for tr in trade_log if tr["side"] == "SELL"]
    wins = [tr for tr in closed if tr["pnl"] > 0]
    last_prices = {s: float(d["close"].iloc[-1]) for s, d in all_data.items()}
    final_equity = portfolio.equity(last_prices)

    summary = {
        "period_start": timestamps[0].isoformat() if timestamps else None,
        "period_end": timestamps[-1].isoformat() if timestamps else None,
        "symbols_scanned": len(symbols),
        "ma_short_days": MA_SHORT_DAYS,
        "ma_long_days": MA_LONG_DAYS,
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
