"""Loads and validates configuration from environment variables (.env file)."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Config:
    api_key: str
    api_secret: str
    use_testnet: bool

    quote_asset: str
    min_24h_quote_volume: float
    max_candidates: int
    excluded_base_assets: frozenset[str]
    interval: str

    rsi_period: int
    rsi_oversold: float
    rsi_overbought: float
    sma_period: int

    max_position_pct: float
    stop_loss_pct: float
    trailing_activation_pct: float
    trailing_distance_pct: float
    max_hold_hours: float
    crash_drop_pct: float
    crash_window_minutes: float
    max_daily_loss_pct: float
    max_trades_per_day: int

    loop_interval_seconds: int

    def validate(self) -> None:
        problems = []
        if not self.use_testnet and (
            not self.api_key or self.api_key == "your_api_key_here"
        ):
            problems.append("USE_TESTNET is false but no real BINANCE_API_KEY is set.")
        if self.min_24h_quote_volume < 0:
            problems.append("MIN_24H_QUOTE_VOLUME cannot be negative.")
        if self.max_candidates <= 0:
            problems.append("MAX_CANDIDATES must be positive.")
        if not (0 < self.max_position_pct <= 1):
            problems.append("MAX_POSITION_PCT must be between 0 and 1.")
        if not (0 < self.stop_loss_pct < 1):
            problems.append("STOP_LOSS_PCT must be between 0 and 1.")
        if not (0 < self.trailing_activation_pct < 1):
            problems.append("TRAILING_ACTIVATION_PCT must be between 0 and 1.")
        if not (0 < self.trailing_distance_pct < 1):
            problems.append("TRAILING_DISTANCE_PCT must be between 0 and 1.")
        if self.max_hold_hours <= 0:
            problems.append("MAX_HOLD_HOURS must be positive.")
        if not (0 < self.crash_drop_pct < 1):
            problems.append("CRASH_DROP_PCT must be between 0 and 1.")
        if self.crash_window_minutes <= 0:
            problems.append("CRASH_WINDOW_MINUTES must be positive.")
        if not (0 < self.max_daily_loss_pct < 1):
            problems.append("MAX_DAILY_LOSS_PCT must be between 0 and 1.")
        if self.max_trades_per_day <= 0:
            problems.append("MAX_TRADES_PER_DAY must be positive.")
        if problems:
            raise ValueError("Invalid configuration:\n- " + "\n- ".join(problems))


def load_config() -> Config:
    cfg = Config(
        api_key=os.getenv("BINANCE_API_KEY", ""),
        api_secret=os.getenv("BINANCE_API_SECRET", ""),
        use_testnet=_get_bool("USE_TESTNET", True),
        quote_asset=os.getenv("QUOTE_ASSET", "USDT"),
        min_24h_quote_volume=_get_float("MIN_24H_QUOTE_VOLUME", 20_000_000),
        max_candidates=_get_int("MAX_CANDIDATES", 20),
        excluded_base_assets=frozenset(
            s.strip().upper() for s in os.getenv("EXCLUDED_BASE_ASSETS", "").split(",") if s.strip()
        ),
        interval=os.getenv("INTERVAL", "15m"),
        rsi_period=_get_int("RSI_PERIOD", 14),
        rsi_oversold=_get_float("RSI_OVERSOLD", 30),
        rsi_overbought=_get_float("RSI_OVERBOUGHT", 70),
        sma_period=_get_int("SMA_PERIOD", 50),
        max_position_pct=_get_float("MAX_POSITION_PCT", 0.20),
        stop_loss_pct=_get_float("STOP_LOSS_PCT", 0.015),
        trailing_activation_pct=_get_float("TRAILING_ACTIVATION_PCT", 0.02),
        trailing_distance_pct=_get_float("TRAILING_DISTANCE_PCT", 0.015),
        max_hold_hours=_get_float("MAX_HOLD_HOURS", 6),
        crash_drop_pct=_get_float("CRASH_DROP_PCT", 0.07),
        crash_window_minutes=_get_float("CRASH_WINDOW_MINUTES", 60),
        max_daily_loss_pct=_get_float("MAX_DAILY_LOSS_PCT", 0.05),
        max_trades_per_day=_get_int("MAX_TRADES_PER_DAY", 6),
        loop_interval_seconds=_get_int("LOOP_INTERVAL_SECONDS", 60),
    )
    cfg.validate()
    return cfg
