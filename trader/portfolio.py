"""Virtual portfolio state: cash, open positions, and persistence to JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from . import config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PORTFOLIO_PATH = DATA_DIR / "portfolio.json"
TRADES_PATH = DATA_DIR / "trades.json"
EQUITY_PATH = DATA_DIR / "equity.json"


@dataclass
class Position:
    qty: int
    entry_price: float
    entry_time: str
    highwater: float


@dataclass
class Portfolio:
    cash: float = config.INITIAL_CASH
    initial_cash: float = config.INITIAL_CASH
    realized_pnl: float = 0.0
    positions: dict = field(default_factory=dict)  # symbol -> Position
    last_updated: str | None = None

    @classmethod
    def load(cls) -> "Portfolio":
        if not PORTFOLIO_PATH.exists():
            return cls()
        raw = json.loads(PORTFOLIO_PATH.read_text())
        positions = {sym: Position(**p) for sym, p in raw.get("positions", {}).items()}
        return cls(
            cash=raw.get("cash", config.INITIAL_CASH),
            initial_cash=raw.get("initial_cash", config.INITIAL_CASH),
            realized_pnl=raw.get("realized_pnl", 0.0),
            positions=positions,
            last_updated=raw.get("last_updated"),
        )

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "cash": self.cash,
            "initial_cash": self.initial_cash,
            "realized_pnl": self.realized_pnl,
            "positions": {sym: asdict(p) for sym, p in self.positions.items()},
            "last_updated": self.last_updated,
        }
        PORTFOLIO_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def equity(self, last_prices: dict) -> float:
        market_value = sum(
            pos.qty * last_prices.get(sym, pos.entry_price)
            for sym, pos in self.positions.items()
        )
        return self.cash + market_value

    def buy(self, symbol: str, qty: int, price: float, time_iso: str, reason: str = "golden_cross") -> dict:
        cost = qty * price
        self.cash -= cost
        self.positions[symbol] = Position(
            qty=qty, entry_price=price, entry_time=time_iso, highwater=price
        )
        return {
            "time": time_iso,
            "symbol": symbol,
            "side": "BUY",
            "qty": qty,
            "price": price,
            "cash_after": self.cash,
            "pnl": None,
            "reason": reason,
        }

    def sell(self, symbol: str, price: float, time_iso: str, reason: str) -> dict:
        pos = self.positions.pop(symbol)
        proceeds = pos.qty * price
        pnl = (price - pos.entry_price) * pos.qty
        self.cash += proceeds
        self.realized_pnl += pnl
        return {
            "time": time_iso,
            "symbol": symbol,
            "side": "SELL",
            "qty": pos.qty,
            "price": price,
            "cash_after": self.cash,
            "pnl": pnl,
            "reason": reason,
            "entry_price": pos.entry_price,
        }


def append_trades(new_trades: list) -> None:
    if not new_trades:
        return
    existing = []
    if TRADES_PATH.exists():
        existing = json.loads(TRADES_PATH.read_text())
    existing.extend(new_trades)
    TRADES_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2))


def append_equity_point(time_iso: str, equity: float) -> None:
    existing = []
    if EQUITY_PATH.exists():
        existing = json.loads(EQUITY_PATH.read_text())
    existing.append({"t": time_iso, "equity": equity})
    EQUITY_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
