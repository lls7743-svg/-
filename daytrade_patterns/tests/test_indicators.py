import pandas as pd

from src import indicators as ind


def test_ema_converges_to_constant():
    s = pd.Series([100.0] * 30)
    e = ind.ema(s, 10)
    assert abs(e.iloc[-1] - 100.0) < 1e-6


def test_rsi_bounds():
    s = pd.Series([100, 101, 99, 102, 98, 103, 97, 104, 96, 105, 95, 106])
    r = ind.rsi(s, period=3)
    valid = r.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_all_gains_is_100():
    s = pd.Series([100, 101, 102, 103, 104, 105])
    r = ind.rsi(s, period=2)
    assert r.iloc[-1] == 100.0


def test_vwap_between_low_and_high():
    df = pd.DataFrame({
        "open": [100, 101, 102],
        "high": [101, 102, 103],
        "low": [99, 100, 101],
        "close": [100.5, 101.5, 102.5],
        "volume": [1000, 2000, 1500],
    })
    v = ind.vwap(df)
    assert (v >= df["low"].min()).all()
    assert (v <= df["high"].max()).all()


def test_bollinger_bands_ordering():
    s = pd.Series([100 + (i % 5) for i in range(30)], dtype=float)
    lower, mid, upper = ind.bollinger_bands(s, window=10, num_std=2.0)
    valid = mid.dropna().index
    assert (lower[valid] <= mid[valid]).all()
    assert (mid[valid] <= upper[valid]).all()


def test_atr_non_negative():
    df = pd.DataFrame({
        "open": [100, 101, 99, 102],
        "high": [102, 103, 101, 104],
        "low": [99, 100, 98, 101],
        "close": [101, 99, 100, 103],
    })
    a = ind.atr(df, period=2)
    assert (a.dropna() >= 0).all()
