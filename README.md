# Day Trade Screener

Screens a watchlist of US equities for day-trading candidates using
[yfinance](https://github.com/ranaroussi/yfinance) data: price, daily
% change, relative volume (today vs. 20-day average), RSI(14), and
position relative to the 20-day SMA.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python day_trade_screener.py
```

Options:

```
--tickers TICKER [TICKER ...]   Tickers to screen (default: built-in watchlist)
--tickers-file PATH             Read tickers from a file, one per line
--min-price FLOAT               Minimum price (default: 1.0)
--max-price FLOAT               Maximum price (default: 500.0)
--min-rel-volume FLOAT          Minimum today's volume / 20-day avg volume (default: 1.0)
--min-pct-change FLOAT          Minimum absolute daily % change to include (default: 0.0)
--top INT                       Max rows to display (default: 20)
```

Example — high relative-volume movers under $50:

```bash
python day_trade_screener.py --max-price 50 --min-rel-volume 2 --min-pct-change 3
```

## Notes

Data comes from Yahoo Finance via `yfinance`; it requires outbound network
access to `query1.finance.yahoo.com` / `query2.finance.yahoo.com`. Screening
results are informational only and not investment advice.
