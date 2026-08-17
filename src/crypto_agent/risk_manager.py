"""Risk management: position sizing, exit rules, and a daily kill-switch.

This module knows nothing about Binance or the strategy - it is pure bookkeeping
and math, which makes it easy to unit test and to trust. The Trader is required
to consult it before every trade.

Exit rules, checked in this priority order (highest priority first):

  1. Crash circuit-breaker - if price drops `crash_drop_pct` or more within the
     last `crash_window_minutes`, sell immediately. This exists specifically for
     sudden market crashes, where waiting for the normal stop-loss distance
     could mean a much worse fill.
  2. Hard stop-loss - if price is down `stop_loss_pct` or more from the entry
     price, sell. This is the capital-protection floor for every single trade.
  3. Trailing stop - once a position has gained at least
     `trailing_activation_pct` from entry, a trailing stop activates: if price
     then pulls back `trailing_distance_pct` from its peak since entry, sell.
     This lets winners run further than a fixed take-profit would, while still
     locking in gains on a reversal.
  4. Time-limit exit - if a position has been open for more than
     `max_hold_hours` without hitting any of the above, sell at market. This
     prevents capital from sitting idle in a position that is going nowhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class RiskManager:
    max_position_pct: float
    stop_loss_pct: float
    trailing_activation_pct: float
    trailing_distance_pct: float
    max_hold_hours: float
    crash_drop_pct: float
    crash_window_minutes: float
    max_daily_loss_pct: float
    max_trades_per_day: int

    _day: date | None = field(default=None, init=False, repr=False)
    _trades_today: int = field(default=0, init=False, repr=False)
    _daily_pnl: float = field(default=0.0, init=False, repr=False)
    _daily_start_balance: float | None = field(default=None, init=False, repr=False)
    _kill_switch_triggered: bool = field(default=False, init=False, repr=False)

    def _roll_day_if_needed(self, now: datetime, current_balance: float) -> None:
        today = now.date()
        if self._day != today:
            self._day = today
            self._trades_today = 0
            self._daily_pnl = 0.0
            self._daily_start_balance = current_balance
            self._kill_switch_triggered = False

    def can_open_trade(self, now: datetime, current_balance: float) -> tuple[bool, str]:
        """Call this before opening any new position."""
        self._roll_day_if_needed(now, current_balance)
        if self._kill_switch_triggered:
            return False, "Daily loss limit reached - trading paused until tomorrow (kill-switch)"
        if self._trades_today >= self.max_trades_per_day:
            return False, f"Max trades per day reached ({self.max_trades_per_day})"
        return True, "OK"

    def position_size(self, available_balance: float) -> float:
        """Amount of quote currency to risk on the next trade."""
        return max(0.0, available_balance * self.max_position_pct)

    def check_exit(
        self,
        entry_price: float,
        current_price: float,
        peak_price: float,
        opened_at: datetime,
        now: datetime,
        price_before_crash_window: float | None = None,
    ) -> tuple[bool, str | None]:
        """Returns (should_exit, reason). See module docstring for rule priority."""
        if entry_price <= 0:
            return False, None

        # 1. Crash circuit-breaker - overrides everything else.
        if price_before_crash_window is not None and price_before_crash_window > 0:
            crash_change = (current_price - price_before_crash_window) / price_before_crash_window
            if crash_change <= -self.crash_drop_pct:
                return True, (
                    f"CRASH circuit-breaker: price dropped {crash_change:.2%} "
                    f"within ~{self.crash_window_minutes:.0f} min - selling immediately"
                )

        # 2. Hard stop-loss.
        change_from_entry = (current_price - entry_price) / entry_price
        if change_from_entry <= -self.stop_loss_pct:
            return True, f"stop-loss hit ({change_from_entry:.2%} from entry)"

        # 3. Trailing stop, once activated by enough profit from entry.
        peak_price = max(peak_price, entry_price, current_price)
        profit_at_peak = (peak_price - entry_price) / entry_price
        if profit_at_peak >= self.trailing_activation_pct:
            drop_from_peak = (current_price - peak_price) / peak_price
            if drop_from_peak <= -self.trailing_distance_pct:
                return True, (
                    f"trailing-stop hit: peak was {peak_price:.2f} (+{profit_at_peak:.2%}), "
                    f"now {drop_from_peak:.2%} off peak"
                )

        # 4. Time-limit exit for positions going nowhere.
        hours_open = (now - opened_at).total_seconds() / 3600
        if hours_open >= self.max_hold_hours:
            return True, f"time-limit exit after {hours_open:.1f}h without hitting target/stop"

        return False, None

    def record_closed_trade(self, now: datetime, pnl_amount: float, current_balance: float) -> None:
        """Call this after a position is closed (win or loss) to update daily bookkeeping."""
        self._roll_day_if_needed(now, current_balance)
        self._trades_today += 1
        self._daily_pnl += pnl_amount

        if self._daily_start_balance:
            loss_limit = self._daily_start_balance * self.max_daily_loss_pct
            if self._daily_pnl <= -abs(loss_limit):
                self._kill_switch_triggered = True

    @property
    def trades_today(self) -> int:
        return self._trades_today

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch_triggered
