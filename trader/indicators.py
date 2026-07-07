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
