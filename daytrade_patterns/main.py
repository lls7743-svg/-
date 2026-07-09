#!/usr/bin/env python3
"""Backtest a set of day-trading patterns across tickers and rank them.

This tool needs live market data (via yfinance), so it is meant to be
run on your own machine with internet access — not inside a sandboxed
Claude Code session.

Example:
    pip install -r requirements.txt
    python main.py --tickers AAPL,MSFT,SPY,QQQ,TSLA --period 60d --interval 5m
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from src.backtest import compute_stats, simulate
from src.data import load_sessions
from src.patterns import ALL_PATTERNS


def run(tickers: list[str], period: str, interval: str, pattern_names: list[str],
         risk_pct: float, slippage_bps: float, commission_bps: float,
         force_refresh: bool):
    all_trades = []
    for ticker in tickers:
        print(f"Loading {ticker} ({period}, {interval})...", file=sys.stderr)
        try:
            sessions = load_sessions(ticker, period=period, interval=interval,
                                      force_refresh=force_refresh)
        except Exception as exc:
            print(f"  skipped {ticker}: {exc}", file=sys.stderr)
            continue

        for name in pattern_names:
            detector = ALL_PATTERNS[name]
            for session in sessions:
                try:
                    signal = detector(session)
                except Exception as exc:
                    print(f"  {name} failed on {ticker} {session.date.date()}: {exc}", file=sys.stderr)
                    continue
                if signal is None:
                    continue
                trade = simulate(session, signal, slippage_bps=slippage_bps,
                                  commission_bps=commission_bps)
                if trade is not None:
                    all_trades.append(trade)

    return all_trades


def build_report(trades, risk_pct: float) -> pd.DataFrame:
    rows = []
    by_pattern = {}
    for t in trades:
        by_pattern.setdefault(t.pattern, []).append(t)

    for pattern, plist in by_pattern.items():
        stats = compute_stats(plist, risk_pct_per_trade=risk_pct)
        stats["pattern"] = pattern
        rows.append(stats)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    cols = ["pattern", "n_trades", "win_rate", "profit_factor", "expectancy_r",
            "total_return_pct", "max_drawdown_pct", "sharpe"]
    df = df[cols].sort_values("expectancy_r", ascending=False).reset_index(drop=True)
    return df


def format_report(df: pd.DataFrame) -> str:
    if df.empty:
        return "No trades were generated — check tickers/period/interval and try again."
    lines = []
    lines.append(f"{'pattern':<22}{'trades':>8}{'win%':>8}{'PF':>8}{'exp(R)':>9}"
                  f"{'ret%':>9}{'maxDD%':>9}{'Sharpe':>9}")
    for _, r in df.iterrows():
        lines.append(
            f"{r['pattern']:<22}{r['n_trades']:>8}{r['win_rate']*100:>7.1f}%"
            f"{r['profit_factor']:>8.2f}{r['expectancy_r']:>9.3f}"
            f"{r['total_return_pct']:>8.2f}%{r['max_drawdown_pct']:>8.2f}%{r['sharpe']:>9.2f}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickers", default="AAPL,MSFT,SPY,QQQ,TSLA",
                         help="Comma-separated tickers (default: %(default)s)")
    parser.add_argument("--period", default="60d", help="yfinance period, e.g. 7d/60d (default: %(default)s)")
    parser.add_argument("--interval", default="5m", help="Bar size, e.g. 1m/5m/15m (default: %(default)s)")
    parser.add_argument("--patterns", default="all",
                         help=f"Comma-separated pattern names or 'all'. Choices: {', '.join(ALL_PATTERNS)}")
    parser.add_argument("--risk-pct", type=float, default=0.01,
                         help="Fraction of equity risked per trade for the equity curve (default: %(default)s)")
    parser.add_argument("--slippage-bps", type=float, default=5.0, help="Slippage in bps per fill (default: %(default)s)")
    parser.add_argument("--commission-bps", type=float, default=1.0, help="Commission in bps per fill (default: %(default)s)")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore cache and re-download data")
    parser.add_argument("--trades-out", default=None, help="Optional CSV path to dump every simulated trade")
    parser.add_argument("--report-out", default=None, help="Optional path to save the ranking table as CSV")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    pattern_names = list(ALL_PATTERNS) if args.patterns == "all" else \
        [p.strip() for p in args.patterns.split(",") if p.strip()]
    for p in pattern_names:
        if p not in ALL_PATTERNS:
            parser.error(f"unknown pattern '{p}'. Choices: {', '.join(ALL_PATTERNS)}")

    trades = run(tickers, args.period, args.interval, pattern_names,
                 args.risk_pct, args.slippage_bps, args.commission_bps, args.force_refresh)

    print(f"\nSimulated {len(trades)} trades across {len(tickers)} tickers "
          f"and {len(pattern_names)} patterns.\n")

    report = build_report(trades, args.risk_pct)
    print(format_report(report))

    if not report.empty:
        best = report.iloc[0]
        print(f"\nBest by expectancy: {best['pattern']} "
              f"(expectancy={best['expectancy_r']:.3f}R, win_rate={best['win_rate']*100:.1f}%, "
              f"n={best['n_trades']})")
        print("Note: rank by expectancy/profit-factor, not win-rate alone — a strategy "
              "with a lower win rate but bigger average winners can still be more profitable.")

    if args.trades_out and trades:
        pd.DataFrame([t.__dict__ for t in trades]).to_csv(args.trades_out, index=False)
        print(f"\nWrote {len(trades)} trades to {args.trades_out}")

    if args.report_out and not report.empty:
        report.to_csv(args.report_out, index=False)
        print(f"Wrote ranking table to {args.report_out}")


if __name__ == "__main__":
    main()
