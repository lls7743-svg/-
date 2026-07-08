"""Sanity check for the standalone new-high-breakout experiment (no network)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader.breakout_backtest import run


def _synthetic_fetch(symbols):
    idx = pd.bdate_range("2024-01-01", periods=60)
    out = {}
    for i, sym in enumerate(symbols):
        prices = [100.0 + i] * 25 + [100.0 + i + j * 0.5 for j in range(35)]  # breakout partway through
        out[sym] = pd.DataFrame(
            {"open": prices, "high": [p + 0.5 for p in prices], "low": [p - 0.5 for p in prices],
             "close": prices, "volume": [1000] * 60},
            index=idx,
        )
    return out


def test_run_returns_summary():
    # output_dir=None: don't touch the real repo's data/ directory from a test.
    summary = run(symbols=["AAA.T", "BBB.T"], fetch=_synthetic_fetch, output_dir=None)
    assert summary["symbols_scanned"] == 2
    assert summary["initial_cash"] > 0
    assert summary["entry_window_days"] == 20
    assert summary["period_start"] is not None


def test_run_writes_dashboard_output(tmp_path):
    out_dir = tmp_path / "breakout_backtest"
    run(symbols=["AAA.T", "BBB.T"], fetch=_synthetic_fetch, output_dir=out_dir)
    assert (out_dir / "portfolio.json").exists()
    assert (out_dir / "trades.json").exists()
    assert (out_dir / "equity.json").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "prices" / "index.json").exists()


def test_run_raises_on_no_data():
    try:
        run(symbols=["AAA.T"], fetch=lambda symbols: {}, output_dir=None)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
