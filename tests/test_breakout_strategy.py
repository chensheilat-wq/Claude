import pandas as pd

from src.crypto_agent.breakout_strategy import DonchianBreakoutStrategy
from src.crypto_agent.strategy import Signal


def make_klines(closes: list[float]) -> pd.DataFrame:
    # high/low equal to close for simplicity in these tests
    return pd.DataFrame({"close": closes, "high": closes, "low": closes})


def test_no_buy_without_a_breakout():
    closes = [100.0] * 25  # flat - never makes a new high
    strategy = DonchianBreakoutStrategy(entry_period=20, exit_period=10)
    decision = strategy.decide(make_klines(closes), has_open_position=False)
    assert decision.signal != Signal.BUY


def test_buy_on_fresh_breakout_above_prior_high():
    closes = [100.0] * 20 + [105.0]  # last candle breaks above the flat 100 range
    strategy = DonchianBreakoutStrategy(entry_period=20, exit_period=10)
    decision = strategy.decide(make_klines(closes), has_open_position=False)
    assert decision.signal == Signal.BUY


def test_sell_on_breakdown_below_recent_low_while_holding():
    closes = [100.0] * 20 + [90.0]  # sharp drop below the recent low (need >= 21 candles for min_candles_required)
    strategy = DonchianBreakoutStrategy(entry_period=20, exit_period=10)
    decision = strategy.decide(make_klines(closes), has_open_position=True)
    assert decision.signal == Signal.SELL


def test_hold_while_trend_intact():
    closes = [100.0 + i for i in range(25)]  # steadily rising, never breaks down
    strategy = DonchianBreakoutStrategy(entry_period=20, exit_period=10)
    decision = strategy.decide(make_klines(closes), has_open_position=True)
    assert decision.signal == Signal.HOLD


def test_not_enough_data_returns_hold():
    strategy = DonchianBreakoutStrategy(entry_period=20, exit_period=10)
    decision = strategy.decide(make_klines([100.0] * 5), has_open_position=False)
    assert decision.signal == Signal.HOLD
