"""Simulator configuration: watchlist, capital, and strategy parameters."""

# Broad, liquid Japan large-cap universe (Yahoo Finance ".T" suffix). This is a
# hand-compiled approximation of the Nikkei 225-style blue-chip basket, not the
# official, periodically-revised index membership list -- good enough for a
# simulator's stock-picking pool, but don't treat it as authoritative.
# Scanned in full every cycle so the strategy can pick its favorites rather
# than being limited to a handful of fixed names.
WATCHLIST = list(dict.fromkeys([
    # Autos & transport equipment
    "7203.T", "7267.T", "7201.T", "7269.T", "7270.T", "7211.T", "7261.T",
    "7202.T", "7259.T", "6902.T", "7276.T",
    # Machinery
    "6301.T", "6113.T", "6141.T", "6273.T", "6367.T", "6103.T", "7011.T",
    "7013.T", "7012.T", "6448.T", "6479.T",
    # Electronics & precision
    "6758.T", "6501.T", "6503.T", "6752.T", "6702.T", "6701.T",
    "6971.T", "6976.T", "6857.T", "8035.T", "6723.T", "6963.T", "6762.T",
    "6841.T", "7735.T", "6920.T", "6594.T", "6645.T", "6869.T", "6952.T",
    "4901.T", "7751.T", "7733.T",
    # Telecom & internet
    "9432.T", "9433.T", "9434.T", "9984.T", "4689.T", "4755.T",
    # Banks, insurance & securities
    "8306.T", "8316.T", "8411.T", "8308.T", "8354.T", "8331.T", "8309.T",
    "8604.T", "8628.T", "8697.T", "8766.T", "8750.T", "8725.T", "8630.T",
    "8591.T", "8593.T",
    # Trading houses
    "8058.T", "8031.T", "8001.T", "8002.T", "2768.T",
    # Retail
    "9983.T", "3382.T", "8267.T", "3092.T", "9843.T", "3086.T", "8252.T",
    "3099.T",
    # Pharma & healthcare
    "4502.T", "4503.T", "4568.T", "4519.T", "4523.T", "4507.T", "4151.T",
    "4543.T",
    # Chemicals & materials
    "4063.T", "4188.T", "4005.T", "4021.T", "3407.T", "5401.T", "5406.T",
    "5411.T", "5713.T", "5801.T", "5802.T", "5803.T", "4183.T", "4061.T",
    "4208.T", "3402.T", "3861.T", "3405.T",
    # Food & beverage
    "2502.T", "2503.T", "2801.T", "2802.T", "2269.T", "2914.T", "2871.T",
    "2201.T", "2811.T",
    # Construction & real estate
    "1801.T", "1802.T", "1803.T", "1808.T", "8801.T", "8802.T", "8830.T",
    "1928.T", "1925.T",
    # Transport & infrastructure
    "9020.T", "9021.T", "9022.T", "9202.T", "9201.T", "9531.T", "9501.T",
    "9502.T", "9503.T", "9142.T", "9005.T", "9007.T", "9008.T", "9009.T",
    "9064.T", "9147.T",
    # Entertainment & consumer
    "4661.T", "7974.T", "9697.T", "7832.T", "9735.T", "4324.T", "9602.T",
    "4676.T",
    # Consumer goods & other large caps
    "8113.T", "4452.T", "7912.T", "7911.T", "5020.T", "5019.T", "6178.T",
    "7182.T", "7181.T", "6146.T", "6098.T",
]))

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

# Chart-pattern confirmation, layered on top of the MA-cross/RSI base signal so
# entries need a candlestick reversal cue or a breakout of the recent range --
# not just a crossover -- plus volume backing it up.
REQUIRE_PATTERN_CONFIRMATION = True
REQUIRE_VOLUME_CONFIRMATION = True
BREAKOUT_WINDOW = 20              # bars used for recent-high breakout and average volume
VOLUME_CONFIRM_MULTIPLIER = 1.5   # entry bar's volume vs. the preceding window's average
PATTERN_SCORE_BONUS = 0.02        # ranking bonus when a candlestick/breakout pattern also confirms

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
