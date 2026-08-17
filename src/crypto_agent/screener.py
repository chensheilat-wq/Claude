"""Builds the list of candidate symbols to scan for an entry each cycle.

Deliberately liquidity-filtered: the bot's stop-loss is only as good as its
ability to actually exit near the price it saw. On an illiquid pair, the
bid/ask spread alone can exceed the 1.5% stop-loss distance, which would
silently defeat the risk management this bot is built around. So this
screener trades breadth of opportunity for a liquidity floor, rather than
scanning every listed pair indiscriminately.
"""

import logging

logger = logging.getLogger("crypto_agent")

# Trading one stablecoin against another has essentially no volatility to
# capture - there's no real setup here, so these are always excluded even if
# they'd otherwise pass the volume filter.
STABLECOINS = {
    "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "PYUSD", "EUR", "GBP", "AEUR",
}


def build_candidate_symbols(
    exchange,
    quote_asset: str,
    min_24h_quote_volume: float,
    max_candidates: int,
    excluded_base_assets: frozenset[str] = frozenset(),
) -> list[str]:
    """Returns up to `max_candidates` symbols quoted in `quote_asset`, sorted by
    24h quote volume (descending, i.e. most liquid first), after excluding:
      - pairs below `min_24h_quote_volume` (liquidity floor)
      - stablecoin-vs-stablecoin pairs
      - anything in `excluded_base_assets`
    """
    tickers = exchange.get_all_24h_tickers()

    candidates = []
    for t in tickers:
        symbol = t.get("symbol", "")
        if not symbol.endswith(quote_asset):
            continue
        base = symbol[: -len(quote_asset)]
        if not base or base in STABLECOINS or base in excluded_base_assets:
            continue
        try:
            quote_volume = float(t.get("quoteVolume", 0))
        except (TypeError, ValueError):
            continue
        if quote_volume < min_24h_quote_volume:
            continue
        candidates.append((symbol, quote_volume))

    candidates.sort(key=lambda pair: pair[1], reverse=True)
    result = [symbol for symbol, _ in candidates[:max_candidates]]
    logger.info(
        "Screener: %d liquid %s-quoted candidates selected (of %d symbols checked)",
        len(result), quote_asset, len(tickers),
    )
    return result
