"""Sanity check for the standalone trend-following experiment (no network)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader.trend_backtest import run


def _synthetic_fetch(symbols):
    idx = pd.bdate_range("2024-01-01", periods=90)
    out = {}
    for i, sym in enumerate(symbols):
        # flat, then a sustained rise (uptrend), then a sustained fall (downtrend)
        prices = [100.0 + i] * 35 + [100.0 + i + j * 0.8 for j in range(30)] + \
                 [100.0 + i + 24 - j * 0.8 for j in range(25)]
        out[sym] = pd.DataFrame(
            {"open": prices, "high": [p + 0.5 for p in prices], "low": [p - 0.5 for p in prices],
             "close": prices, "volume": [1000] * 90},
            index=idx,
        )
    return out


def test_run_returns_summary():
    summary = run(symbols=["AAA.T", "BBB.T"], fetch=_synthetic_fetch, output_dir=None)
    assert summary["symbols_scanned"] == 2
    assert summary["initial_cash"] > 0
    assert summary["ma_short_days"] == 10
    assert summary["ma_long_days"] == 30
    assert summary["period_start"] is not None


def test_run_writes_dashboard_output(tmp_path):
    out_dir = tmp_path / "trend_backtest"
    run(symbols=["AAA.T", "BBB.T"], fetch=_synthetic_fetch, output_dir=out_dir)
    assert (out_dir / "portfolio.json").exists()
    assert (out_dir / "trades.json").exists()
    assert (out_dir / "prices" / "index.json").exists()


def test_run_raises_on_no_data():
    try:
        run(symbols=["AAA.T"], fetch=lambda symbols: {}, output_dir=None)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
