"""Trade simulation and performance statistics.

Simulation rules (typical retail day-trading assumptions):
  - One trade per session per pattern (see patterns.py).
  - Stop-loss and take-profit are checked bar-by-bar after entry; if a
    single bar's range contains both levels, the stop is assumed to
    fill first (conservative / worst-case assumption).
  - Any position still open at the last bar of the session is flattened
    at that bar's close (day traders don't hold overnight).
  - Slippage and commission are modelled as basis-point costs applied
    to both the entry and the exit fill.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import Session
from .patterns import Signal


@dataclass
class Trade:
    ticker: str
    pattern: str
    date: pd.Timestamp
    direction: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str  # "stop" | "target" | "eod"
    r_multiple: float
    pnl_pct: float  # net of costs, as a fraction (0.01 = 1%)


def _apply_slippage(price: float, direction: str, side: str, slippage_bps: float) -> float:
    """side: 'entry' or 'exit'. Slippage always works against the trader."""
    factor = slippage_bps / 10_000.0
    if (direction == "long" and side == "entry") or (direction == "short" and side == "exit"):
        return price * (1 + factor)
    return price * (1 - factor)


def simulate(session: Session, signal: Signal, slippage_bps: float = 5.0,
             commission_bps: float = 1.0) -> Trade | None:
    bars = session.bars
    future = bars[bars.index > signal.entry_time]
    if future.empty:
        # Entry was on the last bar; flatten immediately at same price.
        future = bars.iloc[[-1]]

    planned_risk = abs(signal.entry_price - signal.stop_price)
    if planned_risk == 0:
        return None

    fill_entry = _apply_slippage(signal.entry_price, signal.direction, "entry", slippage_bps)

    exit_price = None
    exit_time = None
    exit_reason = None

    for ts, row in future.iterrows():
        if signal.direction == "long":
            if row["low"] <= signal.stop_price:
                exit_price, exit_time, exit_reason = signal.stop_price, ts, "stop"
                break
            if row["high"] >= signal.target_price:
                exit_price, exit_time, exit_reason = signal.target_price, ts, "target"
                break
        else:
            if row["high"] >= signal.stop_price:
                exit_price, exit_time, exit_reason = signal.stop_price, ts, "stop"
                break
            if row["low"] <= signal.target_price:
                exit_price, exit_time, exit_reason = signal.target_price, ts, "target"
                break

    if exit_price is None:
        last = bars.iloc[-1]
        exit_price, exit_time, exit_reason = last["close"], bars.index[-1], "eod"

    fill_exit = _apply_slippage(exit_price, signal.direction, "exit", slippage_bps)

    if signal.direction == "long":
        raw_return = (fill_exit - fill_entry) / fill_entry
        r_multiple = (exit_price - signal.entry_price) / planned_risk
    else:
        raw_return = (fill_entry - fill_exit) / fill_entry
        r_multiple = (signal.entry_price - exit_price) / planned_risk

    commission_cost = 2 * (commission_bps / 10_000.0)
    pnl_pct = raw_return - commission_cost

    return Trade(
        ticker=session.ticker,
        pattern=signal.pattern,
        date=session.date,
        direction=signal.direction,
        entry_time=signal.entry_time,
        entry_price=signal.entry_price,
        exit_time=exit_time,
        exit_price=exit_price,
        exit_reason=exit_reason,
        r_multiple=r_multiple,
        pnl_pct=pnl_pct,
    )


def compute_stats(trades: list[Trade], risk_pct_per_trade: float = 0.01) -> dict:
    if not trades:
        return {
            "n_trades": 0, "win_rate": float("nan"), "avg_r": float("nan"),
            "profit_factor": float("nan"), "expectancy_r": float("nan"),
            "total_return_pct": float("nan"), "max_drawdown_pct": float("nan"),
            "sharpe": float("nan"),
        }

    r_multiples = np.array([t.r_multiple for t in trades])
    wins = r_multiples[r_multiples > 0]
    losses = r_multiples[r_multiples <= 0]

    win_rate = len(wins) / len(r_multiples)
    gross_win = wins.sum() if len(wins) else 0.0
    gross_loss = abs(losses.sum()) if len(losses) else 0.0
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf")
    expectancy_r = r_multiples.mean()

    # Equity curve assuming a fixed fraction of equity is risked per trade.
    equity = [1.0]
    for r in r_multiples:
        equity.append(equity[-1] * (1 + risk_pct_per_trade * r))
    equity = np.array(equity)
    total_return_pct = (equity[-1] - 1.0) * 100

    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max
    max_drawdown_pct = drawdown.min() * 100

    trade_returns = risk_pct_per_trade * r_multiples
    if trade_returns.std(ddof=0) > 0:
        dates = sorted({t.date for t in trades})
        span_days = max((dates[-1] - dates[0]).days, 1)
        trades_per_year = len(trades) / span_days * 365
        sharpe = (trade_returns.mean() / trade_returns.std(ddof=0)) * math.sqrt(trades_per_year)
    else:
        sharpe = float("nan")

    return {
        "n_trades": len(trades),
        "win_rate": win_rate,
        "avg_r": expectancy_r,
        "profit_factor": profit_factor,
        "expectancy_r": expectancy_r,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe": sharpe,
    }
