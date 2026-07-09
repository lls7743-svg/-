"""Pre-market drop screener for Japanese stocks.

Intended to run daily between 09:00 and 09:15 JST (Tokyo Stock Exchange
open). For every ticker in the watchlist, compares the latest available
5-minute price against the previous trading day's close. Tickers that
dropped by at least --threshold percent (default 5%) are reported, and a
5-minute intraday candlestick chart plus a 30-day daily candlestick chart
are saved for each of them.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

import mplfinance as mpf
import pandas as pd
import yfinance as yf

JST = ZoneInfo("Asia/Tokyo")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TICKERS_FILE = ROOT / "config" / "tickers.csv"
DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_DROP_THRESHOLD = 5.0

logger = logging.getLogger("screener")


@dataclasses.dataclass
class ScreenResult:
    symbol: str
    name: str
    prev_close: float
    current_price: float
    pct_change: float


def load_tickers(path: Path = DEFAULT_TICKERS_FILE) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8") as f:
        return [(row["code"].strip(), row["name"].strip()) for row in csv.DictReader(f)]


def to_yahoo_symbol(code: str) -> str:
    """Japanese 4-digit codes need the .T suffix for Yahoo Finance."""
    return code if "." in code else f"{code}.T"


def fetch_batch(symbols: list[str], period: str, interval: str) -> dict[str, pd.DataFrame]:
    """Download OHLCV data for many symbols in one request."""
    raw = yf.download(
        tickers=" ".join(symbols),
        period=period,
        interval=interval,
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )

    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        if len(symbols) == 1:
            df = raw
        else:
            try:
                df = raw[symbol]
            except KeyError:
                continue
        df = df.dropna(how="all")
        if not df.empty:
            result[symbol] = df
    return result


def compute_change(daily: pd.DataFrame, intraday: pd.DataFrame) -> tuple[float, float] | None:
    """Return (prev_close, current_price), or None if there isn't enough data."""
    daily = daily.sort_index()
    intraday = intraday.sort_index()

    today = dt.datetime.now(JST).date()
    last_daily_date = daily.index[-1].date()
    if last_daily_date == today and len(daily) >= 2:
        prev_close = daily["Close"].iloc[-2]
    else:
        prev_close = daily["Close"].iloc[-1]

    current_prices = intraday["Close"].dropna()
    if current_prices.empty or pd.isna(prev_close) or prev_close == 0:
        return None

    return float(prev_close), float(current_prices.iloc[-1])


def screen(
    tickers: list[tuple[str, str]], drop_threshold: float = DEFAULT_DROP_THRESHOLD
) -> list[ScreenResult]:
    symbols = [to_yahoo_symbol(code) for code, _ in tickers]
    name_by_symbol = {to_yahoo_symbol(code): name for code, name in tickers}

    logger.info("Fetching daily data for %d tickers...", len(symbols))
    daily_data = fetch_batch(symbols, period="5d", interval="1d")
    logger.info("Fetching 5-minute intraday data for %d tickers...", len(symbols))
    intraday_data = fetch_batch(symbols, period="1d", interval="5m")

    results = []
    for symbol in symbols:
        daily = daily_data.get(symbol)
        intraday = intraday_data.get(symbol)
        if daily is None or intraday is None or daily.empty or intraday.empty:
            continue

        change = compute_change(daily, intraday)
        if change is None:
            continue
        prev_close, current_price = change
        pct_change = (current_price - prev_close) / prev_close * 100

        if pct_change <= -abs(drop_threshold):
            results.append(
                ScreenResult(
                    symbol=symbol,
                    name=name_by_symbol.get(symbol, symbol),
                    prev_close=prev_close,
                    current_price=current_price,
                    pct_change=pct_change,
                )
            )

    results.sort(key=lambda r: r.pct_change)
    return results


def save_charts(symbol: str, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    intraday = yf.download(symbol, period="1d", interval="5m", auto_adjust=False, progress=False)
    intraday_path = out_dir / f"{symbol}_5m.png"
    mpf.plot(
        intraday,
        type="candle",
        style="yahoo",
        title=f"{symbol} - 5min",
        volume=True,
        savefig=dict(fname=str(intraday_path), dpi=150, bbox_inches="tight"),
    )

    daily = yf.download(symbol, period="45d", interval="1d", auto_adjust=False, progress=False)
    daily = daily.tail(30)
    daily_path = out_dir / f"{symbol}_daily30.png"
    mpf.plot(
        daily,
        type="candle",
        style="yahoo",
        title=f"{symbol} - daily (30d)",
        volume=True,
        savefig=dict(fname=str(daily_path), dpi=150, bbox_inches="tight"),
    )

    return intraday_path, daily_path


def write_report(results: list[ScreenResult], out_dir: Path, threshold: float) -> Path:
    date_str = dt.datetime.now(JST).strftime("%Y-%m-%d")
    report_path = out_dir / "report.md"

    lines = [f"# 前日比下落銘柄スクリーニング結果 ({date_str} 09:00-09:15 JST, 閾値 {threshold:.1f}%)", ""]
    if not results:
        lines.append("該当銘柄はありませんでした。")
    else:
        lines.append("| 証券コード | 銘柄名 | 前日終値 | 現在値 | 前日比 |")
        lines.append("|---|---|---:|---:|---:|")
        for r in results:
            lines.append(
                f"| {r.symbol} | {r.name} | {r.prev_close:,.1f} | "
                f"{r.current_price:,.1f} | {r.pct_change:+.2f}% |"
            )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_DROP_THRESHOLD,
        help="Drop percentage threshold (default: 5.0)",
    )
    parser.add_argument("--tickers-file", type=Path, default=DEFAULT_TICKERS_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--no-charts", action="store_true", help="Skip chart generation (screening only)"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    tickers = load_tickers(args.tickers_file)
    results = screen(tickers, drop_threshold=args.threshold)

    date_dir = args.output_dir / dt.datetime.now(JST).strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    for r in results:
        logger.info("Match: %s (%s) %.2f%%", r.symbol, r.name, r.pct_change)
        if not args.no_charts:
            try:
                save_charts(r.symbol, date_dir)
            except Exception:
                logger.exception("Failed to save charts for %s", r.symbol)

    report_path = write_report(results, date_dir, args.threshold)
    logger.info("Report written to %s", report_path)

    if not results:
        logger.info("No stocks matched the %.1f%% drop threshold.", args.threshold)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
