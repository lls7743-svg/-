"""Market data access (Yahoo Finance via yfinance) and JST market-hours helpers."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd

from . import config

JST = ZoneInfo("Asia/Tokyo")


def now_jst() -> dt.datetime:
    return dt.datetime.now(tz=JST)


def _parse_time(s: str) -> dt.time:
    h, m = s.split(":")
    return dt.time(int(h), int(m))


def is_market_open(now: dt.datetime | None = None) -> bool:
    """Approximate TSE session check (does not account for JPX holidays)."""
    now = now or now_jst()
    if now.weekday() >= 5:  # Sat/Sun
        return False
    t = now.time()
    morning = _parse_time(config.MARKET_OPEN) <= t < _parse_time(config.MARKET_MORNING_CLOSE)
    afternoon = _parse_time(config.MARKET_AFTERNOON_OPEN) <= t < _parse_time(config.MARKET_CLOSE)
    return morning or afternoon


def is_force_close_time(now: dt.datetime | None = None) -> bool:
    now = now or now_jst()
    if now.weekday() >= 5:
        return False
    return now.time() >= _parse_time(config.FORCE_CLOSE_TIME)


def is_past_entry_cutoff(now: dt.datetime | None = None) -> bool:
    now = now or now_jst()
    return now.time() >= _parse_time(config.ENTRY_CUTOFF_TIME)


def fetch_history(symbol: str) -> pd.DataFrame:
    """Fetch recent intraday OHLCV for a symbol, indexed by JST datetime."""
    import yfinance as yf

    df = yf.Ticker(symbol).history(
        period=config.LOOKBACK_PERIOD,
        interval=config.INTERVAL,
        auto_adjust=False,
    )
    return _clean(df)


def fetch_history_batch(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Fetch recent intraday OHLCV for many symbols in one batched, threaded call."""
    import yfinance as yf

    if not symbols:
        return {}
    raw = yf.download(
        tickers=symbols,
        period=config.LOOKBACK_PERIOD,
        interval=config.INTERVAL,
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )
    result = {}
    for symbol in symbols:
        try:
            df = raw if len(symbols) == 1 else raw[symbol]
        except KeyError:
            continue
        df = _clean(df.dropna(how="all"))
        if not df.empty:
            result[symbol] = df
    return result


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.tz_convert(JST) if df.index.tz is not None else df.tz_localize(JST)
    df = df.rename(columns=str.lower)
    return df[["open", "high", "low", "close", "volume"]]
