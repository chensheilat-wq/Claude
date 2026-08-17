"""Risk management: position sizing, stop-loss/take-profit, and a daily kill-switch.

This module knows nothing about Binance or the strategy - it is pure bookkeeping
and math, which makes it easy to unit test and to trust. The Trader is required
to consult it before every trade.
"""

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class RiskManager:
    max_position_pct: float
    stop_loss_pct: float
    take_profit_pct: float
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

    def check_exit(self, entry_price: float, current_price: float) -> tuple[bool, str | None]:
        """Returns (should_exit, reason) based on stop-loss / take-profit thresholds."""
        if entry_price <= 0:
            return False, None
        change = (current_price - entry_price) / entry_price
        if change <= -self.stop_loss_pct:
            return True, f"stop-loss hit ({change:.2%})"
        if change >= self.take_profit_pct:
            return True, f"take-profit hit ({change:.2%})"
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
