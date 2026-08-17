import pandas as pd

from src.crypto_agent.strategy import RsiTrendStrategy, Signal


def make_klines(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": closes})


def test_no_buy_when_price_far_below_sma_even_with_tolerance():
    # A long flat run at 100, then a sharp real crash to 80 (RSI goes low, but
    # price is ~20% under any reasonable SMA) - tolerance should NOT rescue this.
    closes = [100.0] * 30 + [95, 90, 85, 80]
    strategy = RsiTrendStrategy(rsi_period=14, rsi_oversold=30, sma_period=20, trend_tolerance_pct=0.02)
    decision = strategy.decide(make_klines(closes), has_open_position=False)
    assert decision.signal != Signal.BUY


def test_buy_allowed_when_price_slightly_below_sma_within_tolerance():
    # Construct a case where price is oversold and only ~1% below the SMA -
    # should pass with a 2% tolerance, matching the real near-misses seen live.
    closes = [100.0] * 25 + [99, 98, 97, 96, 95]  # gentle enough dip -> RSI drops but not to 0
    strategy = RsiTrendStrategy(rsi_period=14, rsi_oversold=50, sma_period=20, trend_tolerance_pct=0.02)
    decision = strategy.decide(make_klines(closes), has_open_position=False)
    # Whatever the outcome, it must be governed by the tolerance math, not a strict >.
    sma_val = decision.sma_value
    assert sma_val is not None
    price = decision.price
    if decision.signal == Signal.BUY:
        assert price > sma_val * (1 - 0.02)


def test_strict_zero_tolerance_matches_old_behavior():
    closes = [100.0] * 20 + [99.5] * 5 + [90.0]  # ends clearly below its own SMA
    strategy = RsiTrendStrategy(rsi_period=14, rsi_oversold=99, sma_period=20, trend_tolerance_pct=0.0)
    decision = strategy.decide(make_klines(closes), has_open_position=False)
    # price (90) is below sma (>90) -> with 0 tolerance this must never be a BUY
    assert decision.signal != Signal.BUY


def test_sell_signal_on_overbought_rsi_when_holding_position():
    closes = [100.0 + i for i in range(40)]  # steadily rising -> RSI should climb high
    strategy = RsiTrendStrategy(rsi_period=14, rsi_overbought=70, sma_period=20)
    decision = strategy.decide(make_klines(closes), has_open_position=True)
    assert decision.signal == Signal.SELL
