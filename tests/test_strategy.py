"""Strategy tests against synthetic price data (no network access required)."""
import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader import config
from trader.portfolio import Portfolio
from trader.strategy import decide_and_execute

JST = ZoneInfo("Asia/Tokyo")


def _bars(closes, start=dt.datetime(2024, 1, 10, 9, 0, tzinfo=JST), volumes=None):
    idx = [start + dt.timedelta(minutes=30 * i) for i in range(len(closes))]
    df = pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": volumes if volumes is not None else [1000] * len(closes),
        },
        index=pd.DatetimeIndex(idx),
    )
    return df


def test_golden_cross_triggers_buy():
    # Mild oscillation (keeps RSI out of overbought territory) then a rise on
    # the final bar so the short MA crosses above the long MA right now, the
    # close breaks the prior range's high, and volume confirms the move.
    base = [100.0 + (-0.3 if i % 2 == 0 else 0.3) for i in range(config.MA_LONG)]
    closes = base + [101.5]
    volumes = [1000] * config.MA_LONG + [5000]  # final bar's volume spikes
    df = _bars(closes, volumes=volumes)
    portfolio = Portfolio(cash=1_000_000.0, initial_cash=1_000_000.0)
    now = dt.datetime(2024, 1, 10, 10, 0, tzinfo=JST)  # within morning session
    trades = decide_and_execute(portfolio, {"7203.T": df}, now, now.isoformat())
    assert len(trades) == 1
    assert trades[0]["side"] == "BUY"
    assert "7203.T" in portfolio.positions


def test_stop_loss_triggers_sell():
    df = _bars([100.0] * (config.MA_LONG + 1))
    now = dt.datetime(2024, 1, 10, 10, 0, tzinfo=JST)  # within morning session
    portfolio = Portfolio(cash=500_000.0, initial_cash=1_000_000.0)
    portfolio.positions["7203.T"] = __import__("trader.portfolio", fromlist=["Position"]).Position(
        qty=100, entry_price=100.0, entry_time=now.isoformat(), highwater=100.0
    )
    # Price falls below the stop-loss threshold.
    df.iloc[-1, df.columns.get_loc("close")] = 100.0 * (1 - config.STOP_LOSS_PCT - 0.01)
    trades = decide_and_execute(portfolio, {"7203.T": df}, now, now.isoformat())
    assert len(trades) == 1
    assert trades[0]["side"] == "SELL"
    assert trades[0]["reason"] == "stop_loss"
    assert "7203.T" not in portfolio.positions


def test_force_close_sells_everything():
    df = _bars([100.0] * (config.MA_LONG + 1))
    now = dt.datetime(2024, 1, 10, 15, 0, tzinfo=JST)  # force-close time
    portfolio = Portfolio(cash=500_000.0, initial_cash=1_000_000.0)
    portfolio.positions["7203.T"] = __import__("trader.portfolio", fromlist=["Position"]).Position(
        qty=100, entry_price=95.0, entry_time=now.isoformat(), highwater=100.0
    )
    trades = decide_and_execute(portfolio, {"7203.T": df}, now, now.isoformat())
    assert len(trades) == 1
    assert trades[0]["reason"] == "day_trade_close"
    assert portfolio.positions == {}


def test_market_closed_does_nothing():
    df = _bars([100.0] * (config.MA_LONG + 5))
    now = dt.datetime(2024, 1, 13, 10, 0, tzinfo=JST)  # a Saturday
    portfolio = Portfolio()
    trades = decide_and_execute(portfolio, {"7203.T": df}, now, now.isoformat())
    assert trades == []
