"""Main trading loop: wires together the exchange client, strategy, and
risk manager. This is the only place that actually decides to place orders.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from .capital_ledger import CapitalLedger
from .config import Config
from .exchange_client import ExchangeClient
from .risk_manager import RiskManager
from .screener import build_candidate_symbols
from .state_store import Position, StateStore
from .strategy import RsiTrendStrategy, Signal, StrategyDecision

logger = logging.getLogger("crypto_agent")


class Trader:
    def __init__(
        self,
        config: Config,
        exchange: ExchangeClient,
        strategy: RsiTrendStrategy,
        risk_manager: RiskManager,
        state_store: StateStore | None = None,
        capital_ledger: CapitalLedger | None = None,
    ):
        self.config = config
        self.exchange = exchange
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.state_store = state_store or StateStore()
        self.quote_asset = config.quote_asset
        self.ledger = capital_ledger
        self.position: Position | None = self.state_store.load()
        if self.position:
            logger.info("Restored open position from previous run: %s", self.position)

        # In-memory rolling price samples, used only for the crash circuit-breaker
        # (compares current price against the price observed ~crash_window_minutes ago).
        self._price_history: list[tuple[datetime, float]] = []

    def _record_price_sample(self, now: datetime, price: float) -> None:
        self._price_history.append((now, price))
        cutoff = now - timedelta(minutes=self.risk_manager.crash_window_minutes * 2)
        self._price_history = [(t, p) for t, p in self._price_history if t >= cutoff]

    def _price_before_crash_window(self, now: datetime) -> float | None:
        target = now - timedelta(minutes=self.risk_manager.crash_window_minutes)
        candidates = [(t, p) for t, p in self._price_history if t <= target]
        if not candidates:
            return None  # not enough history yet (e.g. bot just started) - breaker simply can't fire
        return candidates[-1][1]

    def _scan_for_best_entry(self) -> tuple[str, StrategyDecision] | None:
        """Screens for liquid candidates, evaluates each for a BUY setup, and
        returns the single best one (lowest RSI = most oversold among the
        setups found), since only one position may be open at a time.
        """
        candidates = build_candidate_symbols(
            self.exchange,
            self.config.quote_asset,
            self.config.min_24h_quote_volume,
            self.config.max_candidates,
            self.config.excluded_base_assets,
        )
        if not candidates:
            logger.info("No liquid candidates passed the screener this cycle")
            return None

        best: tuple[str, StrategyDecision] | None = None
        for symbol in candidates:
            try:
                klines = self.exchange.get_klines(symbol, self.config.interval)
            except Exception:
                logger.exception("Failed to fetch klines for %s - skipping this cycle", symbol)
                continue

            decision = self.strategy.decide(klines, has_open_position=False)
            if decision.signal != Signal.BUY:
                continue

            if best is None or (
                decision.rsi_value is not None
                and best[1].rsi_value is not None
                and decision.rsi_value < best[1].rsi_value
            ):
                best = (symbol, decision)

        if best is None:
            logger.info("Scanned %d liquid candidates, no entry setup this cycle", len(candidates))
        return best

    def _handle_no_position(self, now: datetime) -> None:
        # The account is fully in the quote asset right now (no open position),
        # so this is the correct moment to check the profit-lock ladder.
        quote_balance = self.exchange.get_quote_balance(self.quote_asset)
        if self.ledger is not None:
            self.ledger.check_and_lock(quote_balance)
            trading_balance = self.ledger.trading_capital(quote_balance)
        else:
            trading_balance = quote_balance

        can_trade, reason = self.risk_manager.can_open_trade(now, trading_balance)
        if not can_trade:
            logger.info("Skipping BUY scan: %s", reason)
            return

        best = self._scan_for_best_entry()
        if best is None:
            return
        symbol, decision = best
        logger.info("Best entry candidate: %s | %s", symbol, decision.reason)

        order_amount = self.risk_manager.position_size(trading_balance)
        if order_amount < 10:  # Binance minimum notional is typically ~$5-10
            logger.warning("Position size %.2f too small to trade, skipping", order_amount)
            return

        order = self.exchange.place_market_buy(symbol, order_amount)
        filled_qty = float(order.get("executedQty", 0)) or (order_amount / decision.price)
        entry_price = decision.price
        fills = order.get("fills")
        if fills:
            entry_price = sum(float(f["price"]) * float(f["qty"]) for f in fills) / filled_qty

        self.position = Position(
            symbol=symbol,
            entry_price=entry_price,
            quantity=filled_qty,
            opened_at=now.isoformat(),
            peak_price=entry_price,
        )
        self.state_store.save(self.position)
        logger.info("Opened position: %s", self.position)

    def _handle_open_position(self, now: datetime, current_price: float) -> None:
        assert self.position is not None

        # Track the peak price since entry - this drives the trailing stop - and
        # persist it immediately so a restart mid-trade doesn't lose the high-water mark.
        if current_price > self.position.peak_price:
            self.position.peak_price = current_price
            self.state_store.save(self.position)

        opened_at = datetime.fromisoformat(self.position.opened_at)
        price_before_crash_window = self._price_before_crash_window(now)

        should_exit, reason = self.risk_manager.check_exit(
            entry_price=self.position.entry_price,
            current_price=current_price,
            peak_price=self.position.peak_price,
            opened_at=opened_at,
            now=now,
            price_before_crash_window=price_before_crash_window,
        )

        if not should_exit:
            klines = self.exchange.get_klines(self.position.symbol, self.config.interval)
            decision = self.strategy.decide(klines, has_open_position=True)
            logger.info("Signal=%s | %s", decision.signal.value, decision.reason)
            if decision.signal == Signal.SELL:
                should_exit, reason = True, decision.reason

        if not should_exit:
            return

        order = self.exchange.place_market_sell(self.position.symbol, self.position.quantity)
        exit_price = current_price
        fills = order.get("fills")
        filled_qty = float(order.get("executedQty", self.position.quantity))
        if fills and filled_qty:
            exit_price = sum(float(f["price"]) * float(f["qty"]) for f in fills) / filled_qty

        pnl = (exit_price - self.position.entry_price) * self.position.quantity
        logger.info(
            "Closed position %s (%s): entry=%.4f exit=%.4f pnl=%.2f",
            self.position.symbol, reason, self.position.entry_price, exit_price, pnl,
        )

        # Balance is pure quote-asset again now that the position is closed.
        new_balance = self.exchange.get_quote_balance(self.quote_asset)
        new_trading_balance = self.ledger.trading_capital(new_balance) if self.ledger else new_balance
        self.risk_manager.record_closed_trade(now, pnl, new_trading_balance)

        self.position = None
        self.state_store.save(None)

    def run_once(self) -> None:
        now = datetime.now(timezone.utc)

        if self.risk_manager.kill_switch_active:
            logger.warning("Kill-switch active - no new trades will open today")

        if self.position is None:
            # Crash-breaker price history only makes sense while protecting an
            # open position - nothing to protect right now, so keep it empty.
            self._price_history.clear()
            self._handle_no_position(now)
        else:
            current_price = self.exchange.get_current_price(self.position.symbol)
            self._record_price_sample(now, current_price)
            self._handle_open_position(now, current_price)

    def run_forever(self) -> None:
        logger.info(
            "Starting trading loop | quote_asset=%s | interval=%s | max_candidates=%d | testnet=%s",
            self.config.quote_asset, self.config.interval, self.config.max_candidates, self.exchange.use_testnet,
        )
        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("Error during trading loop iteration - will retry next cycle")
            time.sleep(self.config.loop_interval_seconds)
