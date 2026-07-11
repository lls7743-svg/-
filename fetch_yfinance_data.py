"""Fetch stock data from Yahoo Finance via yfinance and save it as CSV."""
import argparse

import yfinance as yf


def fetch_history(ticker: str, period: str, interval: str):
    return yf.Ticker(ticker).history(period=period, interval=interval)


def main():
    parser = argparse.ArgumentParser(description="Fetch stock data via yfinance")
    parser.add_argument("tickers", nargs="+", help="Ticker symbols, e.g. AAPL 7203.T")
    parser.add_argument("--period", default="1mo", help="e.g. 1d, 5d, 1mo, 1y, max")
    parser.add_argument("--interval", default="1d", help="e.g. 1m, 1h, 1d, 1wk")
    parser.add_argument("--outdir", default=".", help="Directory to save CSV files")
    args = parser.parse_args()

    for ticker in args.tickers:
        df = fetch_history(ticker, args.period, args.interval)
        if df.empty:
            print(f"[{ticker}] no data returned")
            continue
        out_path = f"{args.outdir}/{ticker.replace('.', '_')}.csv"
        df.to_csv(out_path)
        print(f"[{ticker}] saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()
