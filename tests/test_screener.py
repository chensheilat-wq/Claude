from src.crypto_agent.screener import build_candidate_symbols


class FakeExchange:
    def __init__(self, tickers):
        self._tickers = tickers

    def get_all_24h_tickers(self):
        return self._tickers


def ticker(symbol, quote_volume):
    return {"symbol": symbol, "quoteVolume": str(quote_volume)}


def test_filters_by_quote_asset():
    exchange = FakeExchange([
        ticker("BTCUSDT", 100_000_000),
        ticker("BTCETH", 100_000_000),  # not USDT-quoted
    ])
    result = build_candidate_symbols(exchange, "USDT", min_24h_quote_volume=0, max_candidates=10)
    assert result == ["BTCUSDT"]


def test_filters_illiquid_pairs_below_volume_floor():
    exchange = FakeExchange([
        ticker("BTCUSDT", 100_000_000),
        ticker("SHITCOINUSDT", 500),
    ])
    result = build_candidate_symbols(exchange, "USDT", min_24h_quote_volume=20_000_000, max_candidates=10)
    assert result == ["BTCUSDT"]


def test_excludes_stablecoin_pairs():
    exchange = FakeExchange([
        ticker("BTCUSDT", 100_000_000),
        ticker("USDCUSDT", 200_000_000),
        ticker("FDUSDUSDT", 200_000_000),
    ])
    result = build_candidate_symbols(exchange, "USDT", min_24h_quote_volume=0, max_candidates=10)
    assert result == ["BTCUSDT"]


def test_excludes_explicitly_excluded_base_assets():
    exchange = FakeExchange([
        ticker("BTCUSDT", 100_000_000),
        ticker("DOGEUSDT", 90_000_000),
    ])
    result = build_candidate_symbols(
        exchange, "USDT", min_24h_quote_volume=0, max_candidates=10, excluded_base_assets=frozenset({"DOGE"})
    )
    assert result == ["BTCUSDT"]


def test_sorted_by_volume_descending_and_capped():
    exchange = FakeExchange([
        ticker("AUSDT", 50_000_000),
        ticker("BUSDT", 200_000_000),
        ticker("CUSDT", 100_000_000),
    ])
    result = build_candidate_symbols(exchange, "USDT", min_24h_quote_volume=0, max_candidates=2)
    assert result == ["BUSDT", "CUSDT"]
