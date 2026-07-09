"""Sanity check for the standalone dip-bounce experiment (no network)."""
import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader.dip_bounce_backtest import run

JST = ZoneInfo("Asia/Tokyo")


def _tse_bars_for_day(date):
    times = [(9, 0), (9, 15), (9, 30), (9, 45), (10, 0), (10, 15), (10, 30),
             (11, 0), (11, 15), (12, 30), (13, 0), (14, 45), (15, 0)]
    return [dt.datetime(date.year, date.month, date.day, h, m, tzinfo=JST) for h, m in times]


def _synthetic_fetch(symbols):
    idx = _tse_bars_for_day(dt.date(2024, 1, 10))
    # Opens at 1000, drops >5% by 9:30 (buy trigger), bounces to +1% from the
    # dip by 9:45 (take-profit trigger), then flat for the rest of the day.
    closes = [1000, 990, 930, 943, 943, 943, 943, 943, 943, 943, 943, 943, 943]
    out = {}
    for sym in symbols:
        out[sym] = pd.DataFrame(
            {"open": closes, "high": [c + 1 for c in closes], "low": [c - 1 for c in closes],
             "close": closes, "volume": [1000] * len(closes)},
            index=pd.DatetimeIndex(idx),
        )
    return out


def test_run_returns_summary():
    summary = run(symbols=["AAA.T"], fetch=_synthetic_fetch, output_dir=None)
    assert summary["symbols_scanned"] == 1
    assert summary["drop_pct_threshold"] == 0.05
    assert summary["take_profit_pct"] == 0.01
    assert summary["period_start"] is not None


def test_dip_triggers_buy_and_take_profit_exits():
    summary = run(symbols=["AAA.T"], fetch=_synthetic_fetch, output_dir=None)
    assert summary["num_round_trips"] == 1
    assert summary["win_rate_pct"] == 100.0


def test_run_writes_dashboard_output(tmp_path):
    out_dir = tmp_path / "dip_bounce_backtest"
    run(symbols=["AAA.T"], fetch=_synthetic_fetch, output_dir=out_dir)
    assert (out_dir / "trades.json").exists()
    assert (out_dir / "prices" / "index.json").exists()


def test_run_raises_on_no_data():
    try:
        run(symbols=["AAA.T"], fetch=lambda symbols: {}, output_dir=None)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
