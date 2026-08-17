"""Trading strategy: RSI mean-reversion filtered by a longer-term SMA trend.

This is deliberately a simple, explainable strategy rather than a black box:

  - Trend filter: only look for BUY setups while price is at or near the SMA
    or above it - within `trend_tolerance_pct` below it counts as "trend still
    intact" (i.e. don't try to "catch a falling knife" in a real downtrend,
    but don't reject a real dip just because it dipped a hair under the
    average). Live diagnosis against 90 days of BTCUSDT data showed a strict
    "price > SMA" filter (tolerance=0) rejected every single oversold reading,
    even with a short SMA(20) - every RSI<30 candle in that window happened
    a percent or two under the average, not above it. A small tolerance is
    what actually lets real setups through.
  - Entry: RSI drops below `rsi_oversold` (asset is short-term oversold).
  - Exit: handled separately by RiskManager (stop-loss / take-profit), plus
    RSI rising above `rsi_overbought` as a momentum-exhaustion signal.

It is intentionally conservative. It will NOT trade constantly - on purpose,
since frequent trading mostly just bleeds the account through fees.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from .indicators import rsi, sma


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class StrategyDecision:
    signal: Signal
    reason: str
    rsi_value: float | None
    sma_value: float | None
    price: float


class RsiTrendStrategy:
    def __init__(
        self,
        rsi_period: int = 14,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        sma_period: int = 20,
        trend_tolerance_pct: float = 0.02,
    ):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.sma_period = sma_period
        self.trend_tolerance_pct = trend_tolerance_pct

    def min_candles_required(self) -> int:
        return max(self.rsi_period, self.sma_period) + 1

    def decide(self, klines: pd.DataFrame, has_open_position: bool) -> StrategyDecision:
        """klines must have a 'close' column ordered oldest -> newest."""
        if len(klines) < self.min_candles_required():
            price = float(klines["close"].iloc[-1]) if len(klines) else float("nan")
            return StrategyDecision(Signal.HOLD, "Not enough historical data yet", None, None, price)

        closes = klines["close"].astype(float)
        rsi_series = rsi(closes, self.rsi_period)
        sma_series = sma(closes, self.sma_period)

        current_price = float(closes.iloc[-1])
        current_rsi = float(rsi_series.iloc[-1])
        current_sma = float(sma_series.iloc[-1])

        if pd.isna(current_rsi) or pd.isna(current_sma):
            return StrategyDecision(Signal.HOLD, "Indicators not yet available", None, None, current_price)

        if not has_open_position:
            trend_floor = current_sma * (1 - self.trend_tolerance_pct)
            if current_price > trend_floor and current_rsi < self.rsi_oversold:
                reason = (
                    f"Price {current_price:.2f} within {self.trend_tolerance_pct:.1%} of SMA{self.sma_period} "
                    f"({current_sma:.2f}) and RSI {current_rsi:.1f} < {self.rsi_oversold} "
                    "(short-term oversold, trend still intact)"
                )
                return StrategyDecision(Signal.BUY, reason, current_rsi, current_sma, current_price)
            return StrategyDecision(
                Signal.HOLD,
                f"No entry setup (price={current_price:.2f}, sma={current_sma:.2f}, rsi={current_rsi:.1f})",
                current_rsi,
                current_sma,
                current_price,
            )
        else:
            if current_rsi > self.rsi_overbought:
                reason = f"RSI {current_rsi:.1f} > {self.rsi_overbought} (momentum exhausted)"
                return StrategyDecision(Signal.SELL, reason, current_rsi, current_sma, current_price)
            return StrategyDecision(
                Signal.HOLD,
                "Holding open position, no exit signal yet (stop-loss/take-profit handled by RiskManager)",
                current_rsi,
                current_sma,
                current_price,
            )
