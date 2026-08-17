#!/usr/bin/env python3
"""Backtest the strategy against historical Binance data (no API key needed -
klines are public). This lets you sanity-check the strategy's behavior on
real past price action before ever risking money on testnet or live.

Usage:
    python backtest.py --symbol BTCUSDT --interval 15m --days 30 --balance 400
"""

import argparse

import pandas as pd
from binance.client import Client

from src.crypto_agent.risk_manager import RiskManager
from src.crypto_agent.strategy import RsiTrendStrategy, Signal


def fetch_history(symbol: str, interval: str, days: int) -> pd.DataFrame:
    client = Client()  # no keys needed for public kline data
    raw = client.get_historical_klines(symbol, interval, f"{days} day ago UTC")
    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(raw, columns=columns)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


def run_backtest(df: pd.DataFrame, starting_balance: float) -> dict:
    strategy = RsiTrendStrategy()
    risk = RiskManager(
        max_position_pct=0.20,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_daily_loss_pct=0.05,
        max_trades_per_day=6,
    )

    balance = starting_balance
    position = None  # (entry_price, quantity)
    trades = []
    min_candles = strategy.min_candles_required()

    for i in range(min_candles, len(df)):
        window = df.iloc[: i + 1]
        now = window["open_time"].iloc[-1].to_pydatetime()
        price = float(window["close"].iloc[-1])

        if position is None:
            can_trade, _ = risk.can_open_trade(now, balance)
            if not can_trade:
                continue
            decision = strategy.decide(window, has_open_position=False)
            if decision.signal == Signal.BUY:
                amount = risk.position_size(balance)
                qty = amount / price
                position = (price, qty)
        else:
            entry_price, qty = position
            should_exit, reason = risk.check_exit(entry_price, price)
            if not should_exit:
                decision = strategy.decide(window, has_open_position=True)
                if decision.signal == Signal.SELL:
                    should_exit, reason = True, decision.reason
            if should_exit:
                pnl = (price - entry_price) * qty
                balance += pnl
                risk.record_closed_trade(now, pnl, balance)
                trades.append({"entry": entry_price, "exit": price, "pnl": pnl, "reason": reason, "time": now})
                position = None

    total_return_pct = (balance - starting_balance) / starting_balance * 100
    wins = [t for t in trades if t["pnl"] > 0]
    return {
        "trades": trades,
        "final_balance": balance,
        "total_return_pct": total_return_pct,
        "num_trades": len(trades),
        "win_rate_pct": (len(wins) / len(trades) * 100) if trades else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest the RSI/SMA strategy")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--balance", type=float, default=400.0)
    args = parser.parse_args()

    print(f"Fetching {args.days} days of {args.interval} candles for {args.symbol}...")
    df = fetch_history(args.symbol, args.interval, args.days)
    print(f"Got {len(df)} candles. Running backtest with starting balance ${args.balance:.2f}...\n")

    result = run_backtest(df, args.balance)

    print("=" * 60)
    print(f"Symbol:           {args.symbol}")
    print(f"Period:           last {args.days} days ({args.interval} candles)")
    print(f"Starting balance: ${args.balance:.2f}")
    print(f"Final balance:    ${result['final_balance']:.2f}")
    print(f"Total return:     {result['total_return_pct']:+.2f}%")
    print(f"Number of trades: {result['num_trades']}")
    print(f"Win rate:         {result['win_rate_pct']:.1f}%")
    print("=" * 60)
    print("\nNOTE: past performance on historical data is NOT a guarantee of")
    print("future results. This ignores real-world slippage and only")
    print("approximates fees. Use this as a sanity check, not a promise.")


if __name__ == "__main__":
    main()
