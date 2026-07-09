import pandas as pd
import pytest

from src.backtest import Trade, compute_stats, simulate
from src.data import Session
from src.patterns import Signal


def make_session(rows, start="2024-01-02 09:30", freq_minutes=5):
    idx = pd.date_range(start, periods=len(rows), freq=f"{freq_minutes}min")
    df = pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close", "volume"])
    return Session(ticker="TST", date=pd.Timestamp(start).normalize(), bars=df, prev_close=None)


def test_simulate_long_hits_target():
    rows = [
        [100, 101, 99, 100, 1000],   # entry bar
        [100, 100.5, 99.8, 100.2, 1000],
        [100.2, 106, 100.1, 105, 1000],  # spikes to target
        [105, 105.5, 104.5, 105.2, 1000],
    ]
    session = make_session(rows)
    sig = Signal("test", "long", session.bars.index[0], entry_price=100.0,
                 stop_price=98.0, target_price=105.0)
    trade = simulate(session, sig, slippage_bps=0, commission_bps=0)
    assert trade.exit_reason == "target"
    assert trade.r_multiple == pytest.approx(2.5, rel=1e-6)


def test_simulate_long_hits_stop():
    rows = [
        [100, 101, 99, 100, 1000],
        [100, 100.2, 97, 97.5, 1000],  # drops through stop
        [97.5, 98, 97, 97.8, 1000],
    ]
    session = make_session(rows)
    sig = Signal("test", "long", session.bars.index[0], entry_price=100.0,
                 stop_price=98.0, target_price=105.0)
    trade = simulate(session, sig, slippage_bps=0, commission_bps=0)
    assert trade.exit_reason == "stop"
    assert trade.r_multiple == pytest.approx(-1.0, rel=1e-6)


def test_simulate_long_eod_flat():
    rows = [
        [100, 101, 99, 100, 1000],
        [100, 100.5, 99.6, 100.1, 1000],
        [100.1, 100.6, 99.9, 100.3, 1000],  # never hits stop or target
    ]
    session = make_session(rows)
    sig = Signal("test", "long", session.bars.index[0], entry_price=100.0,
                 stop_price=98.0, target_price=110.0)
    trade = simulate(session, sig, slippage_bps=0, commission_bps=0)
    assert trade.exit_reason == "eod"
    assert trade.exit_price == pytest.approx(100.3)


def test_simulate_applies_costs_against_trader():
    rows = [
        [100, 101, 99, 100, 1000],
        [100.1, 100.6, 99.9, 100.3, 1000],
    ]
    session = make_session(rows)
    sig = Signal("test", "long", session.bars.index[0], entry_price=100.0,
                 stop_price=98.0, target_price=110.0)
    free = simulate(session, sig, slippage_bps=0, commission_bps=0)
    costly = simulate(session, sig, slippage_bps=10, commission_bps=5)
    assert costly.pnl_pct < free.pnl_pct


def _trade(r_multiple):
    return Trade(ticker="T", pattern="p", date=pd.Timestamp("2024-01-02"),
                 direction="long", entry_time=pd.Timestamp("2024-01-02 09:30"),
                 entry_price=100, exit_time=pd.Timestamp("2024-01-02 10:00"),
                 exit_price=100 + r_multiple, exit_reason="eod",
                 r_multiple=r_multiple, pnl_pct=r_multiple / 100)


def test_compute_stats_basic():
    trades = [_trade(2.0), _trade(-1.0), _trade(1.5), _trade(-1.0)]
    stats = compute_stats(trades, risk_pct_per_trade=0.01)
    assert stats["n_trades"] == 4
    assert stats["win_rate"] == pytest.approx(0.5)
    assert stats["expectancy_r"] == pytest.approx(0.375)
    assert stats["profit_factor"] == pytest.approx(3.5 / 2.0)
    assert stats["total_return_pct"] > 0


def test_compute_stats_empty():
    stats = compute_stats([])
    assert stats["n_trades"] == 0
    assert stats["win_rate"] != stats["win_rate"]  # NaN
