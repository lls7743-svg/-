"""Backtest loop sanity check against synthetic data (no network required)."""
import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader.backtest import run_backtest

JST = ZoneInfo("Asia/Tokyo")


def _synthetic_fetch(symbols):
    idx = [dt.datetime(2024, 1, 8, 9, 0, tzinfo=JST) + dt.timedelta(minutes=30 * i) for i in range(40)]
    out = {}
    for i, sym in enumerate(symbols):
        prices = [100.0 + i + (0.5 * j if j > 25 else 0) for j in range(40)]
        out[sym] = pd.DataFrame(
            {"open": prices, "high": prices, "low": prices, "close": prices, "volume": 1000},
            index=pd.DatetimeIndex(idx),
        )
    return out


def test_run_backtest_returns_summary():
    summary = run_backtest(symbols=["AAA.T", "BBB.T"], fetch=_synthetic_fetch)
    assert summary["symbols_scanned"] == 2
    assert summary["initial_cash"] > 0
    assert summary["final_equity"] > 0
    assert summary["period_start"] is not None
    assert summary["period_end"] is not None


def test_run_backtest_raises_on_no_data():
    try:
        run_backtest(symbols=["AAA.T"], fetch=lambda symbols: {})
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
