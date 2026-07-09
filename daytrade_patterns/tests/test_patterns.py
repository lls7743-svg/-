import pandas as pd
import pytest

from src.data import Session
from src import patterns as p


def make_session(rows, freq_minutes=5, start="2024-01-02 09:30", prev_close=None, ticker="TST"):
    idx = pd.date_range(start, periods=len(rows), freq=f"{freq_minutes}min")
    df = pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close", "volume"])
    return Session(ticker=ticker, date=pd.Timestamp(start).normalize(), bars=df, prev_close=prev_close)


def test_orb_breakout_long():
    rows = [
        [100.0, 101.0, 99.0, 100.5, 1000],   # 09:30 OR window
        [100.5, 101.0, 100.0, 100.8, 1000],  # 09:35 OR window
        [100.8, 101.2, 100.5, 101.0, 1000],  # 09:40 OR window (last bar < 09:45)
        [101.0, 102.0, 100.9, 101.5, 1500],  # 09:45 breakout close > OR high (101.2)
        [101.5, 102.5, 101.4, 102.0, 1500],
    ]
    session = make_session(rows)
    sig = p.orb_breakout(session, or_minutes=15, target_r_mult=2.0)
    assert sig is not None
    assert sig.direction == "long"
    assert sig.entry_price == pytest.approx(101.5)
    assert sig.stop_price == pytest.approx(99.0)  # OR low


def test_orb_breakout_none_when_no_breakout():
    rows = [
        [100.0, 101.0, 99.0, 100.5, 1000],
        [100.5, 101.0, 100.0, 100.8, 1000],
        [100.8, 101.2, 100.5, 101.0, 1000],
        [101.0, 101.1, 100.9, 101.0, 1000],  # stays inside OR range
    ]
    session = make_session(rows)
    assert p.orb_breakout(session, or_minutes=15) is None


def test_gap_and_go_long():
    rows = [
        [102.0, 102.8, 101.9, 102.5, 2000],  # gap up + green first bar
        [102.5, 103.0, 102.4, 102.9, 1500],  # breaks above first bar high (102.8)
    ]
    session = make_session(rows, prev_close=100.0)
    sig = p.gap_and_go(session, gap_threshold=0.01, target_r_mult=2.0)
    assert sig is not None
    assert sig.direction == "long"
    assert sig.stop_price == pytest.approx(101.9)


def test_gap_and_go_none_without_gap():
    rows = [
        [100.1, 100.5, 99.9, 100.3, 2000],
        [100.3, 100.8, 100.2, 100.6, 1500],
    ]
    session = make_session(rows, prev_close=100.0)
    assert p.gap_and_go(session, gap_threshold=0.01) is None


def test_ema_crossover_long():
    # Downtrend then sharp reversal so the fast EMA crosses above the slow EMA.
    prices = [110, 108, 106, 104, 102, 101, 105, 110, 114, 118]
    rows = [[c, c + 0.5, c - 0.5, c, 1000] for c in prices]
    session = make_session(rows)
    sig = p.ema_crossover(session, fast=2, slow=4, target_r_mult=2.0, stop_lookback=3)
    assert sig is not None
    assert sig.direction == "long"


def test_rsi2_mean_reversion_long():
    prices = [100, 99, 98, 97, 96, 95, 96.5]
    rows = [[c, c + 0.3, c - 0.3, c, 1000] for c in prices]
    session = make_session(rows)
    sig = p.rsi2_mean_reversion(session, period=2, oversold=10, overbought=90)
    assert sig is not None
    assert sig.direction == "long"


def test_bollinger_breakout_long():
    # A flat, tight range (squeeze) followed by a single sharp breakout bar.
    flat = [100.0] * 9
    breakout = [102.0]
    prices = flat + breakout
    rows = [[c, c + 0.2, c - 0.2, c, 1000] for c in prices]
    session = make_session(rows)
    sig = p.bollinger_breakout(session, window=5, num_std=1.0, squeeze_lookback=5, target_r_mult=2.0)
    assert sig is not None
    assert sig.direction == "long"


def test_all_patterns_registered():
    assert set(p.ALL_PATTERNS) == {
        "orb_breakout", "gap_and_go", "vwap_reversion",
        "ema_crossover", "rsi2_mean_reversion", "bollinger_breakout",
    }
