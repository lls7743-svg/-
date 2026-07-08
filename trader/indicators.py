"""Small technical-indicator helpers built on pandas Series."""
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))


def golden_cross(ma_short: pd.Series, ma_long: pd.Series) -> bool:
    """True if ma_short crossed above ma_long on the most recent bar."""
    if len(ma_short) < 2 or ma_short.iloc[-2:].isna().any() or ma_long.iloc[-2:].isna().any():
        return False
    return ma_short.iloc[-2] <= ma_long.iloc[-2] and ma_short.iloc[-1] > ma_long.iloc[-1]


def dead_cross(ma_short: pd.Series, ma_long: pd.Series) -> bool:
    """True if ma_short crossed below ma_long on the most recent bar."""
    if len(ma_short) < 2 or ma_short.iloc[-2:].isna().any() or ma_long.iloc[-2:].isna().any():
        return False
    return ma_short.iloc[-2] >= ma_long.iloc[-2] and ma_short.iloc[-1] < ma_long.iloc[-1]


def is_bullish_engulfing(df: pd.DataFrame) -> bool:
    """Last candle is a bullish body that fully engulfs the prior bearish body."""
    if len(df) < 2:
        return False
    prev, cur = df.iloc[-2], df.iloc[-1]
    prev_bearish = prev.close < prev.open
    cur_bullish = cur.close > cur.open
    engulfs = cur.open <= prev.close and cur.close >= prev.open
    return bool(prev_bearish and cur_bullish and engulfs)


def is_bearish_engulfing(df: pd.DataFrame) -> bool:
    """Last candle is a bearish body that fully engulfs the prior bullish body."""
    if len(df) < 2:
        return False
    prev, cur = df.iloc[-2], df.iloc[-1]
    prev_bullish = prev.close > prev.open
    cur_bearish = cur.close < cur.open
    engulfs = cur.open >= prev.close and cur.close <= prev.open
    return bool(prev_bullish and cur_bearish and engulfs)


def is_hammer(df: pd.DataFrame) -> bool:
    """Small body near the top of the range with a long lower wick (reversal-up cue)."""
    if df.empty:
        return False
    bar = df.iloc[-1]
    body = abs(bar.close - bar.open)
    lower_wick = min(bar.open, bar.close) - bar.low
    upper_wick = bar.high - max(bar.open, bar.close)
    rng = bar.high - bar.low
    if rng <= 0:
        return False
    return bool(lower_wick >= body * 2 and upper_wick <= body * 0.5 and body / rng < 0.4)


def is_shooting_star(df: pd.DataFrame) -> bool:
    """Small body near the bottom of the range with a long upper wick (reversal-down cue)."""
    if df.empty:
        return False
    bar = df.iloc[-1]
    body = abs(bar.close - bar.open)
    lower_wick = min(bar.open, bar.close) - bar.low
    upper_wick = bar.high - max(bar.open, bar.close)
    rng = bar.high - bar.low
    if rng <= 0:
        return False
    return bool(upper_wick >= body * 2 and lower_wick <= body * 0.5 and body / rng < 0.4)


def breaks_recent_high(df: pd.DataFrame, window: int) -> bool:
    """True if the last close is above the highest high of the preceding `window` bars."""
    if len(df) < window + 1:
        return False
    prior_high = df["high"].iloc[-window - 1 : -1].max()
    return bool(df["close"].iloc[-1] > prior_high)


def volume_confirms(df: pd.DataFrame, window: int, multiplier: float) -> bool:
    """True if the last bar's volume is a multiplier above its preceding average."""
    if len(df) < window + 1:
        return False
    avg_vol = df["volume"].iloc[-window - 1 : -1].mean()
    if avg_vol <= 0:
        return False
    return bool(df["volume"].iloc[-1] >= avg_vol * multiplier)
