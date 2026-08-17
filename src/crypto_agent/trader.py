"""Main trading loop: wires together the exchange client, strategy, and
risk manager. This is the only place that actually decides to place orders.
"""

import logging
import time
from datetime import datetime, timezone

from .config import Config
from .exchange_client import ExchangeClient
from .risk_manager import RiskManager
from .state_store import Position, StateStore
from .strategy import RsiTrendStrategy, Signal

logger = logging.getLogger("crypto_agent")


def split_symbol(symbol: str, quote_hint: str = "USDT") -> tuple[str, str]:
    """Best-effort split of e.g. 'BTCUSDT' -> ('BTC', 'USDT')."""
    if symbol.endswith(quote_hint):
        return symbol[: -len(quote_hint)], quote_hint
    # Fallback: assume last 3 chars are the quote asset (e.g. BTCBUSD-style is 4, handled above).
    return symbol[:-3], symbol[-3:]


class Trader:
    def __init__(
        self,
        config: Config,
        exchange: ExchangeClient,
        strategy: RsiTrendStrategy,
        risk_manager: RiskManager,
        state_store: StateStore | None = None,
    ):
        self.config = config
        self.exchange = exchange
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.state_store = state_store or StateStore()
        self.base_asset, self.quote_asset = split_symbol(config.symbol)
        self.position: Position | None = self.state_store.load()
        if self.position:
            logger.info("Restored open position from previous run: %s", self.position)

    def _handle_no_position(self, now: datetime) -> None:
        quote_balance = self.exchange.get_quote_balance(self.quote_asset)
        can_trade, reason = self.risk_manager.can_open_trade(now, quote_balance)
        if not can_trade:
            logger.info("Skipping BUY check: %s", reason)
            return

        klines = self.exchange.get_klines(self.config.symbol, self.config.interval)
        decision = self.strategy.decide(klines, has_open_position=False)
        logger.info("Signal=%s | %s", decision.signal.value, decision.reason)

        if decision.signal != Signal.BUY:
            return

        order_amount = self.risk_manager.position_size(quote_balance)
        if order_amount < 10:  # Binance minimum notional is typically ~$5-10
            logger.warning("Position size %.2f too small to trade, skipping", order_amount)
            return

        order = self.exchange.place_market_buy(self.config.symbol, order_amount)
        filled_qty = float(order.get("executedQty", 0)) or (order_amount / decision.price)
        entry_price = decision.price
        fills = order.get("fills")
        if fills:
            entry_price = sum(float(f["price"]) * float(f["qty"]) for f in fills) / filled_qty

        self.position = Position(
            symbol=self.config.symbol,
            entry_price=entry_price,
            quantity=filled_qty,
            opened_at=now.isoformat(),
        )
        self.state_store.save(self.position)
        logger.info("Opened position: %s", self.position)

    def _handle_open_position(self, now: datetime) -> None:
        assert self.position is not None
        current_price = self.exchange.get_current_price(self.config.symbol)

        should_exit, reason = self.risk_manager.check_exit(self.position.entry_price, current_price)
        if not should_exit:
            klines = self.exchange.get_klines(self.config.symbol, self.config.interval)
            decision = self.strategy.decide(klines, has_open_position=True)
            logger.info("Signal=%s | %s", decision.signal.value, decision.reason)
            if decision.signal == Signal.SELL:
                should_exit, reason = True, decision.reason

        if not should_exit:
            return

        order = self.exchange.place_market_sell(self.config.symbol, self.position.quantity)
        exit_price = current_price
        fills = order.get("fills")
        filled_qty = float(order.get("executedQty", self.position.quantity))
        if fills and filled_qty:
            exit_price = sum(float(f["price"]) * float(f["qty"]) for f in fills) / filled_qty

        pnl = (exit_price - self.position.entry_price) * self.position.quantity
        logger.info("Closed position (%s): entry=%.2f exit=%.2f pnl=%.2f", reason, self.position.entry_price, exit_price, pnl)

        new_balance = self.exchange.get_quote_balance(self.quote_asset)
        self.risk_manager.record_closed_trade(now, pnl, new_balance)

        self.position = None
        self.state_store.save(None)

    def run_once(self) -> None:
        now = datetime.now(timezone.utc)
        if self.risk_manager.kill_switch_active:
            logger.warning("Kill-switch active - no new trades will open today")
        if self.position is None:
            self._handle_no_position(now)
        else:
            self._handle_open_position(now)

    def run_forever(self) -> None:
        logger.info(
            "Starting trading loop for %s | interval=%s | testnet=%s",
            self.config.symbol, self.config.interval, self.exchange.use_testnet,
        )
        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("Error during trading loop iteration - will retry next cycle")
            time.sleep(self.config.loop_interval_seconds)
