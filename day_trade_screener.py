#!/usr/bin/env python3
"""Day trade screener: ranks a watchlist of US equities by liquidity,
momentum, and volatility signals pulled from Yahoo Finance via yfinance."""
import argparse
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf

DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMD", "TSLA", "AMZN", "GOOGL", "META", "NFLX",
    "AVGO", "CRM", "ADBE", "INTC", "MU", "QCOM", "PYPL", "SQ", "SHOP",
    "COIN", "PLTR", "SOFI", "RIVN", "LCID", "F", "GM", "BAC", "JPM",
    "XOM", "CVX", "SPY", "QQQ", "IWM", "SMCI", "MARA", "RIOT", "UPST",
    "DKNG", "ROKU", "SNAP", "UBER", "ABNB",
]


@dataclass
class ScreenResult:
    ticker: str
    price: float
    pct_change: float
    rel_volume: float
    rsi: float
    above_sma20: bool


def compute_rsi(closes: pd.Series, period: int = 14) -> float:
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean().iloc[-1]
    avg_loss = loss.rolling(period).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def screen_ticker(ticker: str, history: pd.DataFrame) -> ScreenResult | None:
    if history.empty or len(history) < 21:
        return None

    closes = history["Close"].dropna()
    volumes = history["Volume"].dropna()
    if len(closes) < 21 or len(volumes) < 21:
        return None

    price = closes.iloc[-1]
    prev_close = closes.iloc[-2]
    pct_change = (price - prev_close) / prev_close * 100

    avg_volume_20 = volumes.iloc[-21:-1].mean()
    today_volume = volumes.iloc[-1]
    rel_volume = today_volume / avg_volume_20 if avg_volume_20 else 0.0

    rsi = compute_rsi(closes)
    sma20 = closes.iloc[-20:].mean()

    return ScreenResult(
        ticker=ticker,
        price=round(price, 2),
        pct_change=round(pct_change, 2),
        rel_volume=round(rel_volume, 2),
        rsi=round(rsi, 1),
        above_sma20=price > sma20,
    )


def run_screen(
    tickers: list[str],
    min_price: float,
    max_price: float,
    min_rel_volume: float,
    min_abs_pct_change: float,
    top_n: int,
) -> list[ScreenResult]:
    print(f"Fetching data for {len(tickers)} tickers...", file=sys.stderr)
    data = yf.download(
        tickers, period="2mo", interval="1d", group_by="ticker",
        auto_adjust=True, progress=False, threads=True,
    )

    results = []
    for ticker in tickers:
        try:
            history = data[ticker] if len(tickers) > 1 else data
        except KeyError:
            continue
        result = screen_ticker(ticker, history)
        if result is None:
            continue
        if not (min_price <= result.price <= max_price):
            continue
        if result.rel_volume < min_rel_volume:
            continue
        if abs(result.pct_change) < min_abs_pct_change:
            continue
        results.append(result)

    results.sort(key=lambda r: (r.rel_volume, abs(r.pct_change)), reverse=True)
    return results[:top_n]


def print_results(results: list[ScreenResult]) -> None:
    if not results:
        print("No tickers matched the screen criteria.")
        return

    header = f"{'Ticker':<8}{'Price':>10}{'% Chg':>10}{'RelVol':>10}{'RSI':>8}{'>SMA20':>8}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r.ticker:<8}{r.price:>10.2f}{r.pct_change:>10.2f}"
            f"{r.rel_volume:>10.2f}{r.rsi:>8.1f}{str(r.above_sma20):>8}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tickers", nargs="+", default=DEFAULT_WATCHLIST,
        help="Tickers to screen (default: built-in liquid-cap watchlist)",
    )
    parser.add_argument(
        "--tickers-file", type=str, default=None,
        help="Path to a text file with one ticker per line",
    )
    parser.add_argument("--min-price", type=float, default=1.0)
    parser.add_argument("--max-price", type=float, default=500.0)
    parser.add_argument(
        "--min-rel-volume", type=float, default=1.0,
        help="Minimum today's-volume / 20-day-average-volume ratio",
    )
    parser.add_argument(
        "--min-pct-change", type=float, default=0.0,
        help="Minimum absolute daily percent change to include",
    )
    parser.add_argument("--top", type=int, default=20, help="Max rows to show")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tickers = args.tickers
    if args.tickers_file:
        with open(args.tickers_file) as f:
            tickers = [line.strip().upper() for line in f if line.strip()]

    results = run_screen(
        tickers=tickers,
        min_price=args.min_price,
        max_price=args.max_price,
        min_rel_volume=args.min_rel_volume,
        min_abs_pct_change=args.min_pct_change,
        top_n=args.top,
    )
    print_results(results)


if __name__ == "__main__":
    main()
