"""Rule-based decision engine: entry/exit signals for the day-trading simulator.

Exit timing (take-profit / stop-loss) is intentionally dynamic rather than a
fixed price target: a hard stop-loss guards against large losses, while a
trailing stop "arms" once a position is in profit and lets winners run until
the price pulls back from its post-entry high. All open positions are also
force-closed near the market close to keep the day-trade discipline.
"""
from __future__ import annotations

import pandas as pd

from . import config
from .data import is_force_close_time, is_past_entry_cutoff, is_market_open
from .indicators import (
    sma,
    rsi,
    golden_cross,
    dead_cross,
    is_bullish_engulfing,
    is_bearish_engulfing,
    is_hammer,
    is_shooting_star,
    breaks_recent_high,
    volume_confirms,
)
from .portfolio import Portfolio


def _indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    return {
        "close": close,
        "ma_short": sma(close, config.MA_SHORT),
        "ma_long": sma(close, config.MA_LONG),
        "rsi": rsi(close, config.RSI_PERIOD),
    }


def decide_and_execute(portfolio: Portfolio, market_data: dict, now, now_iso: str) -> list:
    """Mutates `portfolio` in place; returns a list of trade records for this cycle."""
    trades: list = []

    if not is_market_open(now):
        return trades

    force_close = is_force_close_time(now)
    past_entry_cutoff = is_past_entry_cutoff(now)

    # --- Manage existing positions (exits) ---
    for symbol in list(portfolio.positions.keys()):
        df = market_data.get(symbol)
        if df is None or df.empty:
            continue
        ind = _indicators(df)
        price = float(ind["close"].iloc[-1])
        pos = portfolio.positions[symbol]
        pos.highwater = max(pos.highwater, price)

        reason = None
        if force_close:
            reason = "day_trade_close"
        elif price <= pos.entry_price * (1 - config.STOP_LOSS_PCT):
            reason = "stop_loss"
        elif pos.highwater >= pos.entry_price * (1 + config.TAKE_PROFIT_ARM_PCT) and (
            price <= pos.highwater * (1 - config.TRAILING_STOP_PCT)
        ):
            reason = "trailing_take_profit"
        elif is_bearish_engulfing(df) or is_shooting_star(df):
            reason = "bearish_reversal_pattern"
        elif dead_cross(ind["ma_short"], ind["ma_long"]):
            reason = "dead_cross"

        if reason:
            trades.append(portfolio.sell(symbol, price, now_iso, reason))

    # --- Look for new entries: scan the whole watchlist, rank all golden-cross
    # candidates by breakout strength, and buy the strongest ones first rather
    # than just the first match in list order. ---
    if not force_close and not past_entry_cutoff:
        last_prices = {
            sym: float(market_data[sym]["close"].iloc[-1])
            for sym in market_data
            if not market_data[sym].empty
        }
        candidates = []
        for symbol in config.WATCHLIST:
            if symbol in portfolio.positions:
                continue
            df = market_data.get(symbol)
            if df is None or len(df) < config.MA_LONG + 1:
                continue
            ind = _indicators(df)
            if not golden_cross(ind["ma_short"], ind["ma_long"]):
                continue
            if ind["rsi"].iloc[-1] >= config.RSI_OVERBOUGHT:
                continue

            pattern_confirmed = (
                is_bullish_engulfing(df)
                or is_hammer(df)
                or breaks_recent_high(df, config.BREAKOUT_WINDOW)
            )
            if config.REQUIRE_PATTERN_CONFIRMATION and not pattern_confirmed:
                continue
            if config.REQUIRE_VOLUME_CONFIRMATION and not volume_confirms(
                df, config.BREAKOUT_WINDOW, config.VOLUME_CONFIRM_MULTIPLIER
            ):
                continue

            price = float(ind["close"].iloc[-1])
            ma_long = float(ind["ma_long"].iloc[-1])
            strength = (price - ma_long) / ma_long  # how far above its trend the breakout is
            if pattern_confirmed:
                strength += config.PATTERN_SCORE_BONUS
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
            trades.append(portfolio.buy(symbol, qty, price, now_iso))

    return trades
