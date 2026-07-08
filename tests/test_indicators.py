"""Unit tests for the candlestick/breakout/volume pattern helpers."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader.indicators import (
    is_bullish_engulfing,
    is_bearish_engulfing,
    is_hammer,
    is_shooting_star,
    breaks_recent_high,
    volume_confirms,
)


def _df(rows):
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])


def test_bullish_engulfing_detected():
    df = _df([
        {"open": 102, "high": 103, "low": 99, "close": 100, "volume": 1000},  # bearish
        {"open": 99, "high": 104, "low": 98, "close": 103, "volume": 1000},   # engulfs it
    ])
    assert is_bullish_engulfing(df)
    assert not is_bearish_engulfing(df)


def test_bearish_engulfing_detected():
    df = _df([
        {"open": 100, "high": 103, "low": 99, "close": 102, "volume": 1000},  # bullish
        {"open": 103, "high": 104, "low": 97, "close": 98, "volume": 1000},   # engulfs it
    ])
    assert is_bearish_engulfing(df)
    assert not is_bullish_engulfing(df)


def test_hammer_detected():
    df = _df([{"open": 100, "high": 100.6, "low": 90, "close": 100.5, "volume": 1000}])
    assert is_hammer(df)
    assert not is_shooting_star(df)


def test_shooting_star_detected():
    df = _df([{"open": 100, "high": 110, "low": 99.75, "close": 99.8, "volume": 1000}])
    assert is_shooting_star(df)
    assert not is_hammer(df)


def test_breaks_recent_high():
    rows = [{"open": 100, "high": 100, "low": 100, "close": 100, "volume": 1000} for _ in range(20)]
    rows.append({"open": 100, "high": 105, "low": 100, "close": 105, "volume": 1000})
    df = _df(rows)
    assert breaks_recent_high(df, window=20)
    assert not breaks_recent_high(df, window=25)  # not enough history for this window


def test_volume_confirms():
    rows = [{"open": 100, "high": 100, "low": 100, "close": 100, "volume": 1000} for _ in range(20)]
    rows.append({"open": 100, "high": 100, "low": 100, "close": 100, "volume": 3000})
    df = _df(rows)
    assert volume_confirms(df, window=20, multiplier=1.5)
    assert not volume_confirms(df, window=20, multiplier=5.0)
