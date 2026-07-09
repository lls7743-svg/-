import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.screener import JST, ScreenResult, compute_change, screen, to_yahoo_symbol


def test_to_yahoo_symbol_appends_suffix():
    assert to_yahoo_symbol("7203") == "7203.T"


def test_to_yahoo_symbol_keeps_existing_suffix():
    assert to_yahoo_symbol("AAPL.US") == "AAPL.US"


def test_compute_change_uses_previous_days_close_when_today_is_partial():
    today = dt.datetime.now(JST).date()
    yesterday = today - dt.timedelta(days=1)
    daily = pd.DataFrame(
        {"Close": [1000.0, 950.0]},
        index=pd.to_datetime([yesterday, today]).tz_localize(JST),
    )
    intraday = pd.DataFrame(
        {"Close": [960.0, 940.0, 900.0]},
        index=pd.date_range(f"{today} 09:00", periods=3, freq="5min", tz=JST),
    )

    prev_close, current_price = compute_change(daily, intraday)

    assert prev_close == 1000.0
    assert current_price == 900.0


def test_screen_flags_drop_at_or_below_threshold(monkeypatch):
    today = dt.datetime.now(JST).date()
    yesterday = today - dt.timedelta(days=1)

    daily_a = pd.DataFrame(
        {"Close": [1000.0, 940.0]},
        index=pd.to_datetime([yesterday, today]).tz_localize(JST),
    )
    intraday_a = pd.DataFrame(
        {"Close": [950.0, 940.0]},
        index=pd.date_range(f"{today} 09:00", periods=2, freq="5min", tz=JST),
    )
    daily_b = pd.DataFrame(
        {"Close": [1000.0, 990.0]},
        index=pd.to_datetime([yesterday, today]).tz_localize(JST),
    )
    intraday_b = pd.DataFrame(
        {"Close": [995.0, 990.0]},
        index=pd.date_range(f"{today} 09:00", periods=2, freq="5min", tz=JST),
    )

    def fake_fetch_batch(symbols, period, interval):
        if interval == "1d":
            return {"AAA.T": daily_a, "BBB.T": daily_b}
        return {"AAA.T": intraday_a, "BBB.T": intraday_b}

    monkeypatch.setattr("src.screener.fetch_batch", fake_fetch_batch)

    results = screen([("AAA", "A社"), ("BBB", "B社")], drop_threshold=5.0)

    assert [r.symbol for r in results] == ["AAA.T"]
    assert isinstance(results[0], ScreenResult)
    assert results[0].pct_change <= -5.0
