"""Donchian-channel breakout strategy (classic trend-following, the core
idea behind the famous "Turtle Trading" system). This is the OPPOSITE
behavioral bet from RSI mean-reversion: instead of buying dips and
expecting a snap-back, it buys strength and expects the move to continue.

  - Entry: price closes above the highest high of the prior `entry_period`
    candles - a fresh breakout to a new local high, taken as evidence a new
    move is starting.
  - Exit signal: price closes below the lowest low of the prior
    `exit_period` candles (a shorter lookback than entry - trend reversal).
    Actual exits are still governed primarily by RiskManager (stop-loss /
    trailing-stop / time-limit / crash-breaker), exactly as with the other
    strategy - this only adds an earlier "the trend broke" exit signal.

Meant to be tested on longer candles (4h/1d) where a fixed-percentage fee
matters less relative to the size of a real trend move, and where a
6-hour time-limit (tuned for 15m mean-reversion) would cut off a
multi-day trend before it develops.
"""

from __future__ import annotations

import pandas as pd

from .strategy import Signal, StrategyDecision


class DonchianBreakoutStrategy:
    def __init__(self, entry_period: int = 20, exit_period: int = 10):
        self.entry_period = entry_period
        self.exit_period = exit_period

    def min_candles_required(self) -> int:
        return max(self.entry_period, self.exit_period) + 1

    def decide(self, klines: pd.DataFrame, has_open_position: bool) -> StrategyDecision:
        """klines must have 'close' (and ideally 'high'/'low') columns, oldest -> newest."""
        if len(klines) < self.min_candles_required():
            price = float(klines["close"].iloc[-1]) if len(klines) else float("nan")
            return StrategyDecision(Signal.HOLD, "Not enough historical data yet", None, None, price)

        closes = klines["close"].astype(float)
        highs = klines["high"].astype(float) if "high" in klines.columns else closes
        lows = klines["low"].astype(float) if "low" in klines.columns else closes
        current_price = float(closes.iloc[-1])

        # Window looks at the PRIOR candles only (excludes the current one),
        # so the breakout is measured against where price already was.
        entry_highest = float(highs.iloc[-(self.entry_period + 1):-1].max())
        exit_lowest = float(lows.iloc[-(self.exit_period + 1):-1].min())

        if not has_open_position:
            if current_price > entry_highest:
                reason = f"Breakout: price {current_price:.2f} > {self.entry_period}-period high ({entry_highest:.2f})"
                return StrategyDecision(Signal.BUY, reason, None, None, current_price)
            return StrategyDecision(
                Signal.HOLD,
                f"No breakout (price={current_price:.2f}, {self.entry_period}-period high={entry_highest:.2f})",
                None, None, current_price,
            )
        else:
            if current_price < exit_lowest:
                reason = f"Trend reversal: price {current_price:.2f} < {self.exit_period}-period low ({exit_lowest:.2f})"
                return StrategyDecision(Signal.SELL, reason, None, None, current_price)
            return StrategyDecision(
                Signal.HOLD,
                "Holding open position, trend intact (stop-loss/trailing handled by RiskManager)",
                None, None, current_price,
            )
