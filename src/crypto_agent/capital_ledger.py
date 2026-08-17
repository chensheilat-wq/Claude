"""Profit-lock ladder: ratchets a growing portion of the account into an
untouchable "safe" reserve as the total account value crosses successive
milestones (principal, principal*2, principal*4, principal*8, ...).

This is bookkeeping only - the money never physically leaves the Binance
Spot account (the bot's API key deliberately has no withdrawal permission).
It simply stops being available to the strategy for new positions. Since
the bot only ever opens a new trade when it holds no open position (i.e.
the whole account is already sitting in the quote asset), the "conversion
to USDT" this ladder implies is already a given - there is nothing to sell.

Milestone rule (matches the user's own numbers exactly):
  - next_milestone starts at principal * 2 (e.g. 400 -> 800).
  - Whenever total account value reaches next_milestone, HALF of that
    milestone value becomes the new reserve (replacing, not adding to, the
    previous reserve - since the previous reserve is already half of the
    previous, smaller milestone). The other half remains as trading capital.
  - next_milestone then doubles again, forever.

Example: principal=400 -> milestones 800, 1600, 3200, 6400, ...
  800 reached  -> reserve=400,  trading capital=400
  1600 reached -> reserve=800,  trading capital=800
  3200 reached -> reserve=1600, trading capital=1600
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("crypto_agent")


@dataclass
class _LedgerState:
    principal: float
    reserve_balance: float
    next_milestone: float


class CapitalLedger:
    def __init__(self, principal: float, path: str = "logs/capital_ledger_state.json"):
        self.principal = principal
        self.path = path

        loaded = self._load()
        if loaded is not None:
            self.reserve_balance = loaded.reserve_balance
            self.next_milestone = loaded.next_milestone
        else:
            self.reserve_balance = 0.0
            self.next_milestone = principal * 2
            self._save()

    def _load(self) -> _LedgerState | None:
        if not os.path.exists(self.path):
            return None
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        return _LedgerState(**data) if data else None

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "principal": self.principal,
                    "reserve_balance": self.reserve_balance,
                    "next_milestone": self.next_milestone,
                },
                f,
            )

    def trading_capital(self, total_quote_balance: float) -> float:
        """The portion of the account the strategy is allowed to size trades from."""
        return max(0.0, total_quote_balance - self.reserve_balance)

    def check_and_lock(self, total_quote_balance: float) -> list[float]:
        """Call this ONLY when the account is fully in the quote asset (no open
        position) - i.e. right before deciding whether to open a new trade.

        Ratchets the reserve forward through any milestones the balance has
        reached or passed, and returns the list of milestones hit (empty if
        none; more than one if a single jump passed several at once).
        The reserve never decreases - it only ratchets up.
        """
        hit: list[float] = []
        while total_quote_balance >= self.next_milestone:
            self.reserve_balance = self.next_milestone / 2
            hit.append(self.next_milestone)
            self.next_milestone *= 2

        if hit:
            self._save()
            logger.info(
                "PROFIT LOCK: total balance %.2f crossed milestone(s) %s -> reserve now %.2f (untouchable), "
                "trading capital now %.2f",
                total_quote_balance, hit, self.reserve_balance, self.trading_capital(total_quote_balance),
            )
        return hit
