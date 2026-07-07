"""Simulator configuration: watchlist, capital, and strategy parameters."""

# Tokyo Stock Exchange tickers (Yahoo Finance ".T" suffix), large-cap / liquid names
WATCHLIST = [
    "7203.T",  # Toyota Motor
    "6758.T",  # Sony Group
    "9984.T",  # SoftBank Group
    "8306.T",  # Mitsubishi UFJ Financial Group
    "6501.T",  # Hitachi
    "9432.T",  # NTT
    "6098.T",  # Recruit Holdings
    "4063.T",  # Shin-Etsu Chemical
]

INITIAL_CASH = 1_000_000.0  # JPY

MAX_POSITIONS = 4
POSITION_SIZE_FRACTION = 0.20  # fraction of total equity allocated per new position
SHARE_LOT_SIZE = 100  # JP stocks trade in units of 100 shares

# Indicator windows
MA_SHORT = 5
MA_LONG = 25
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0

# Risk / exit rules ("timing" is decided dynamically, not a fixed target)
STOP_LOSS_PCT = 0.03          # hard stop-loss: -3% from entry
TAKE_PROFIT_ARM_PCT = 0.02    # once price is +2% from entry, arm the trailing stop
TRAILING_STOP_PCT = 0.02      # once armed, sell if price drops 2% from its post-entry high

# Data
INTERVAL = "30m"
LOOKBACK_PERIOD = "60d"
PRICE_HISTORY_KEEP_DAYS = 20  # rolling window kept in data/prices/<symbol>.json

# Market hours (JST) - approximate, does not account for JPX holidays
MARKET_OPEN = "09:00"
MARKET_MORNING_CLOSE = "11:30"
MARKET_AFTERNOON_OPEN = "12:30"
MARKET_CLOSE = "15:30"
# Day-trading discipline: force-close all positions at/after this time, and stop
# opening new positions after this time so there is room to exit before the close.
FORCE_CLOSE_TIME = "15:00"
ENTRY_CUTOFF_TIME = "14:30"
