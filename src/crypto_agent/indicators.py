"""Pure, testable technical indicator calculations (no network/API calls here)."""

import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=period, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    result = 100 - (100 / (1 + rs))
    # When avg_loss is 0 the price has only gone up -> RSI is 100.
    result = result.where(avg_loss != 0, 100)
    return result
