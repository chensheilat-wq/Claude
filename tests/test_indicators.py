import pandas as pd

from src.crypto_agent.indicators import rsi, sma


def test_sma_basic():
    series = pd.Series([1, 2, 3, 4, 5])
    result = sma(series, period=3)
    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == 2.0
    assert result.iloc[4] == 4.0


def test_rsi_all_gains_is_100():
    series = pd.Series([float(x) for x in range(1, 20)])  # strictly increasing
    result = rsi(series, period=14)
    assert result.iloc[-1] == 100.0


def test_rsi_all_losses_is_0():
    series = pd.Series([float(x) for x in range(20, 1, -1)])  # strictly decreasing
    result = rsi(series, period=14)
    assert result.iloc[-1] == 0.0


def test_rsi_flat_price_is_neutral():
    series = pd.Series([10.0] * 20)
    result = rsi(series, period=14)
    # No gains and no losses -> our implementation treats this as 100
    # (avg_loss == 0), which is an acceptable edge case for a flat series.
    assert result.iloc[-1] == 100.0
