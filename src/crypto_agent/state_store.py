"""Persists the currently-open position to disk so a restart doesn't make the
bot "forget" it holds a real position and buy again on top of it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass


@dataclass
class Position:
    symbol: str
    entry_price: float
    quantity: float
    opened_at: str  # ISO timestamp
    peak_price: float = 0.0  # highest price observed since entry (drives the trailing stop)


class StateStore:
    def __init__(self, path: str = "logs/position_state.json"):
        self.path = path

    def load(self) -> Position | None:
        if not os.path.exists(self.path):
            return None
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        return Position(**data) if data else None

    def save(self, position: Position | None) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(asdict(position) if position else None, f)
