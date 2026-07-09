"""Day-trading pattern signal generators.

Each pattern function looks at a single trading session (one ticker,
one day) and returns at most one `Signal` — day traders typically cap
themselves to one setup per instrument per day, and capping every
pattern the same way keeps the comparison across patterns fair (same
number of opportunities, not just whichever pattern fires most often).

A Signal is a proposed entry; `backtest.simulate` decides how it plays
out (stop / target / end-of-day exit).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .data import Session
from .indicators import ema, rsi, vwap, bollinger_bands


@dataclass
class Signal:
    pattern: str
    direction: str  # "long" | "short"
    entry_time: pd.Timestamp
    entry_price: float
    stop_price: float
    target_price: float


def _target(entry: float, stop: float, direction: str, r_mult: float) -> float:
    risk = abs(entry - stop)
    return entry + r_mult * risk if direction == "long" else entry - r_mult * risk


def orb_breakout(session: Session, or_minutes: int = 15, target_r_mult: float = 2.0) -> Signal | None:
    bars = session.bars
    start = bars.index[0]
    or_window = bars[bars.index < start + pd.Timedelta(minutes=or_minutes)]
    rest = bars[bars.index >= start + pd.Timedelta(minutes=or_minutes)]
    if or_window.empty or rest.empty:
        return None

    or_high = or_window["high"].max()
    or_low = or_window["low"].min()
    if or_high <= or_low:
        return None

    for ts, row in rest.iterrows():
        if row["close"] > or_high:
            entry = row["close"]
            stop = or_low
            return Signal("orb_breakout", "long", ts, entry, stop,
                           _target(entry, stop, "long", target_r_mult))
        if row["close"] < or_low:
            entry = row["close"]
            stop = or_high
            return Signal("orb_breakout", "short", ts, entry, stop,
                           _target(entry, stop, "short", target_r_mult))
    return None


def gap_and_go(session: Session, gap_threshold: float = 0.01, target_r_mult: float = 2.0) -> Signal | None:
    bars = session.bars
    if session.prev_close is None or len(bars) < 2:
        return None

    first = bars.iloc[0]
    gap_pct = (first["open"] - session.prev_close) / session.prev_close

    if gap_pct >= gap_threshold and first["close"] > first["open"]:
        direction, level, stop = "long", first["high"], first["low"]
    elif gap_pct <= -gap_threshold and first["close"] < first["open"]:
        direction, level, stop = "short", first["low"], first["high"]
    else:
        return None

    for ts, row in bars.iloc[1:].iterrows():
        if direction == "long" and row["close"] > level:
            entry = row["close"]
            return Signal("gap_and_go", "long", ts, entry, stop,
                           _target(entry, stop, "long", target_r_mult))
        if direction == "short" and row["close"] < level:
            entry = row["close"]
            return Signal("gap_and_go", "short", ts, entry, stop,
                           _target(entry, stop, "short", target_r_mult))
    return None


def vwap_reversion(session: Session, warmup_bars: int = 6, swing_lookback: int = 5,
                    target_r_mult: float = 1.5) -> Signal | None:
    bars = session.bars
    if len(bars) < warmup_bars + swing_lookback + 2:
        return None

    v = vwap(bars)
    close = bars["close"]

    for i in range(warmup_bars, len(bars) - 1):
        ts = bars.index[i]
        if pd.isna(v.iloc[i]) or pd.isna(v.iloc[i - 1]):
            continue
        was_above = close.iloc[i - 1] < v.iloc[i - 1]
        now_above = close.iloc[i] > v.iloc[i]
        was_below = close.iloc[i - 1] > v.iloc[i - 1]
        now_below = close.iloc[i] < v.iloc[i]

        if was_above and now_above:
            entry = close.iloc[i]
            stop = bars["low"].iloc[max(0, i - swing_lookback):i + 1].min()
            if stop < entry:
                return Signal("vwap_reversion", "long", ts, entry, stop,
                              _target(entry, stop, "long", target_r_mult))
        if was_below and now_below:
            entry = close.iloc[i]
            stop = bars["high"].iloc[max(0, i - swing_lookback):i + 1].max()
            if stop > entry:
                return Signal("vwap_reversion", "short", ts, entry, stop,
                              _target(entry, stop, "short", target_r_mult))
    return None


def ema_crossover(session: Session, fast: int = 9, slow: int = 20,
                   target_r_mult: float = 2.0, stop_lookback: int = 5) -> Signal | None:
    bars = session.bars
    if len(bars) < slow + 2:
        return None

    fast_ema = ema(bars["close"], fast)
    slow_ema = ema(bars["close"], slow)

    for i in range(slow, len(bars)):
        ts = bars.index[i]
        crossed_up = fast_ema.iloc[i - 1] <= slow_ema.iloc[i - 1] and fast_ema.iloc[i] > slow_ema.iloc[i]
        crossed_dn = fast_ema.iloc[i - 1] >= slow_ema.iloc[i - 1] and fast_ema.iloc[i] < slow_ema.iloc[i]
        if crossed_up:
            entry = bars["close"].iloc[i]
            stop = bars["low"].iloc[max(0, i - stop_lookback):i + 1].min()
            if stop < entry:
                return Signal("ema_crossover", "long", ts, entry, stop,
                              _target(entry, stop, "long", target_r_mult))
        if crossed_dn:
            entry = bars["close"].iloc[i]
            stop = bars["high"].iloc[max(0, i - stop_lookback):i + 1].max()
            if stop > entry:
                return Signal("ema_crossover", "short", ts, entry, stop,
                              _target(entry, stop, "short", target_r_mult))
    return None


def rsi2_mean_reversion(session: Session, period: int = 2, oversold: float = 10.0,
                         overbought: float = 90.0, target_r_mult: float = 1.5,
                         stop_lookback: int = 3) -> Signal | None:
    bars = session.bars
    if len(bars) < period + 5:
        return None

    r = rsi(bars["close"], period)

    for i in range(period + 2, len(bars) - 1):
        if pd.isna(r.iloc[i]):
            continue
        ts = bars.index[i + 1]
        if r.iloc[i] <= oversold:
            entry = bars["close"].iloc[i + 1]
            stop = bars["low"].iloc[max(0, i - stop_lookback):i + 1].min()
            if stop < entry:
                return Signal("rsi2_mean_reversion", "long", ts, entry, stop,
                              _target(entry, stop, "long", target_r_mult))
        if r.iloc[i] >= overbought:
            entry = bars["close"].iloc[i + 1]
            stop = bars["high"].iloc[max(0, i - stop_lookback):i + 1].max()
            if stop > entry:
                return Signal("rsi2_mean_reversion", "short", ts, entry, stop,
                              _target(entry, stop, "short", target_r_mult))
    return None


def bollinger_breakout(session: Session, window: int = 20, num_std: float = 2.0,
                        squeeze_lookback: int = 50, target_r_mult: float = 2.0) -> Signal | None:
    bars = session.bars
    if len(bars) < window + 5:
        return None

    lower, mid, upper = bollinger_bands(bars["close"], window, num_std)
    bandwidth = (upper - lower) / mid

    for i in range(window, len(bars)):
        if pd.isna(upper.iloc[i]) or pd.isna(lower.iloc[i]) or i == 0:
            continue
        ts = bars.index[i]
        # Compare the bar *before* the breakout to its own trailing history,
        # so the breakout bar's own expansion doesn't mask the prior squeeze.
        prior_bw = bandwidth.iloc[i - 1]
        history = bandwidth.iloc[max(0, i - 1 - squeeze_lookback):i - 1]
        if pd.isna(prior_bw) or history.empty or history.isna().all():
            continue
        was_squeezed = prior_bw <= history.median()

        close = bars["close"].iloc[i]
        if close > upper.iloc[i] and was_squeezed:
            entry = close
            stop = lower.iloc[i]
            return Signal("bollinger_breakout", "long", ts, entry, stop,
                          _target(entry, stop, "long", target_r_mult))
        if close < lower.iloc[i] and was_squeezed:
            entry = close
            stop = upper.iloc[i]
            return Signal("bollinger_breakout", "short", ts, entry, stop,
                          _target(entry, stop, "short", target_r_mult))
    return None


ALL_PATTERNS = {
    "orb_breakout": orb_breakout,
    "gap_and_go": gap_and_go,
    "vwap_reversion": vwap_reversion,
    "ema_crossover": ema_crossover,
    "rsi2_mean_reversion": rsi2_mean_reversion,
    "bollinger_breakout": bollinger_breakout,
}
