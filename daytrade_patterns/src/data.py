"""Intraday OHLCV data loading with local CSV caching.

Requires network access and the `yfinance` package, which is why this
project is meant to be run on your own machine rather than in a
sandboxed environment. Data is cached to `data_cache/` so repeated
runs (e.g. while tuning pattern parameters) don't re-hit the network.

yfinance intraday limits (as enforced by the provider, not this code):
  - interval="1m"            -> last ~7 days only
  - interval in 2m/5m/15m/30m/60m/90m -> last ~60 days only
Plan your --period accordingly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_cache")


@dataclass
class Session:
    """One trading day's intraday bars for a single ticker."""

    ticker: str
    date: pd.Timestamp
    bars: pd.DataFrame  # columns: open, high, low, close, volume ; tz-aware index
    prev_close: float | None


def _cache_path(ticker: str, period: str, interval: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = f"{ticker}_{period}_{interval}.csv".replace("/", "-")
    return os.path.join(CACHE_DIR, safe)


def fetch_intraday(ticker: str, period: str = "60d", interval: str = "5m",
                    use_cache: bool = True, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch intraday bars for a ticker, normalized to lowercase OHLCV columns.

    Returns a DataFrame indexed by tz-aware timestamp (exchange local time).
    """
    path = _cache_path(ticker, period, interval)
    if use_cache and not force_refresh and os.path.exists(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "yfinance is required to fetch data. Install with: pip install -r requirements.txt"
        ) from exc

    raw = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    if raw.empty:
        raise RuntimeError(f"No data returned for {ticker} (period={period}, interval={interval})")

    df = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
    df.index.name = "timestamp"

    if use_cache:
        df.to_csv(path)
    return df


def split_sessions(df: pd.DataFrame, ticker: str) -> list[Session]:
    """Split a multi-day intraday DataFrame into one Session per trading day."""
    sessions: list[Session] = []
    prev_close = None
    for date, day_df in df.groupby(df.index.date):
        day_df = day_df.sort_index()
        if len(day_df) < 5:
            continue
        sessions.append(
            Session(
                ticker=ticker,
                date=pd.Timestamp(date),
                bars=day_df,
                prev_close=prev_close,
            )
        )
        prev_close = float(day_df["close"].iloc[-1])
    return sessions


def load_sessions(ticker: str, period: str = "60d", interval: str = "5m",
                   use_cache: bool = True, force_refresh: bool = False) -> list[Session]:
    df = fetch_intraday(ticker, period=period, interval=interval,
                         use_cache=use_cache, force_refresh=force_refresh)
    return split_sessions(df, ticker)
