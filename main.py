#!/usr/bin/env python3
"""Entry point for the crypto investment agent.

Usage:
    python main.py

Configuration is read from a ".env" file (see .env.example).
The bot defaults to Binance TESTNET (fake money) unless USE_TESTNET=false
is explicitly set, in which case it trades with REAL MONEY.
"""

import sys

from src.crypto_agent.config import load_config
from src.crypto_agent.exchange_client import ExchangeClient
from src.crypto_agent.logger_setup import setup_logging
from src.crypto_agent.risk_manager import RiskManager
from src.crypto_agent.strategy import RsiTrendStrategy
from src.crypto_agent.trader import Trader

LIVE_WARNING = """
############################################################
#                                                          #
#   WARNING: USE_TESTNET=false                             #
#   THIS BOT IS ABOUT TO TRADE WITH REAL MONEY.             #
#                                                          #
#   Press Ctrl+C now to abort if this is not intentional.  #
#   Waiting 10 seconds...                                  #
#                                                          #
############################################################
"""


def main() -> int:
    logger = setup_logging()
    try:
        config = load_config()
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        return 1

    if not config.use_testnet:
        import time
        print(LIVE_WARNING, file=sys.stderr)
        time.sleep(10)

    exchange = ExchangeClient(config.api_key, config.api_secret, config.use_testnet)
    strategy = RsiTrendStrategy(
        rsi_period=config.rsi_period,
        rsi_oversold=config.rsi_oversold,
        rsi_overbought=config.rsi_overbought,
        sma_period=config.sma_period,
    )
    risk_manager = RiskManager(
        max_position_pct=config.max_position_pct,
        stop_loss_pct=config.stop_loss_pct,
        take_profit_pct=config.take_profit_pct,
        max_daily_loss_pct=config.max_daily_loss_pct,
        max_trades_per_day=config.max_trades_per_day,
    )
    trader = Trader(config, exchange, strategy, risk_manager)

    try:
        trader.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down (Ctrl+C).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
