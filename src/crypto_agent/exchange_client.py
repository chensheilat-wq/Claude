"""Thin wrapper around python-binance so the rest of the bot never touches
the raw SDK directly. Testnet vs. live is controlled entirely by `use_testnet`.
"""

import logging

import pandas as pd
from binance.client import Client

logger = logging.getLogger("crypto_agent")

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "num_trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]


class ExchangeClient:
    def __init__(self, api_key: str, api_secret: str, use_testnet: bool):
        self.use_testnet = use_testnet
        self.client = Client(api_key, api_secret, testnet=use_testnet)
        mode = "TESTNET (fake money)" if use_testnet else "LIVE (REAL MONEY)"
        logger.info("Exchange client initialized in %s mode", mode)

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        raw = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(raw, columns=KLINE_COLUMNS)
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        return df

    def get_current_price(self, symbol: str) -> float:
        ticker = self.client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def get_all_24h_tickers(self) -> list[dict]:
        """24h stats (incl. quoteVolume) for every symbol, in a single API call.
        Used by the screener to rank candidates by liquidity without hammering
        the API once per symbol.
        """
        return self.client.get_ticker()

    def get_quote_balance(self, quote_asset: str) -> float:
        """e.g. quote_asset='USDT' for symbol BTCUSDT."""
        balance = self.client.get_asset_balance(asset=quote_asset)
        return float(balance["free"]) if balance else 0.0

    def get_base_balance(self, base_asset: str) -> float:
        """e.g. base_asset='BTC' for symbol BTCUSDT."""
        balance = self.client.get_asset_balance(asset=base_asset)
        return float(balance["free"]) if balance else 0.0

    def place_market_buy(self, symbol: str, quote_order_qty: float) -> dict:
        logger.info("Placing MARKET BUY on %s for %.2f quote currency", symbol, quote_order_qty)
        return self.client.order_market_buy(symbol=symbol, quoteOrderQty=round(quote_order_qty, 2))

    def place_market_sell(self, symbol: str, quantity: float) -> dict:
        logger.info("Placing MARKET SELL on %s for %.8f base quantity", symbol, quantity)
        return self.client.order_market_sell(symbol=symbol, quantity=quantity)
