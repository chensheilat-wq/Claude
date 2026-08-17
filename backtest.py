#!/usr/bin/env python3
"""Backtest the strategy against historical Binance data (no API key needed -
klines are public). This lets you sanity-check the strategy's behavior on
real past price action before ever risking money on testnet or live.

Usage:
    python backtest.py --symbol BTCUSDT --interval 15m --days 30 --balance 400
"""

import argparse
from collections import defaultdict
from datetime import timedelta

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


def categorize_exit_reason(reason: str) -> str:
    """Buckets a RiskManager/strategy exit reason string for reporting."""
    if not reason:
        return "unknown"
    if "CRASH" in reason:
        return "crash-breaker"
    if "stop-loss" in reason:
        return "stop-loss"
    if "trailing-stop" in reason:
        return "trailing-stop"
    if "time-limit" in reason:
        return "time-limit"
    if "RSI" in reason:
        return "RSI-overbought-signal"
    return "other"


def _price_before_crash_window(df_window: pd.DataFrame, now, crash_window_minutes: float):
    target = now - timedelta(minutes=crash_window_minutes)
    candidates = df_window[df_window["open_time"] <= target]
    if candidates.empty:
        return None
    return float(candidates["close"].iloc[-1])


def run_backtest(df: pd.DataFrame, starting_balance: float, fee_pct: float = 0.001) -> dict:
    strategy = RsiTrendStrategy()
    risk = RiskManager(
        max_position_pct=0.20,
        stop_loss_pct=0.015,
        trailing_activation_pct=0.02,
        trailing_distance_pct=0.015,
        max_hold_hours=6,
        crash_drop_pct=0.07,
        crash_window_minutes=60,
        max_daily_loss_pct=0.05,
        max_trades_per_day=6,
    )

    balance = starting_balance
    position = None  # dict: entry_price, quantity, opened_at, peak_price, amount_spent
    trades = []
    total_fees_paid = 0.0
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
                buy_fee = amount * fee_pct
                total_fees_paid += buy_fee
                qty = (amount - buy_fee) / price  # fee comes out of the coins you actually receive
                position = {
                    "entry_price": price, "quantity": qty, "opened_at": now,
                    "peak_price": price, "amount_spent": amount,
                }
        else:
            position["peak_price"] = max(position["peak_price"], price)
            price_before_crash = _price_before_crash_window(window, now, risk.crash_window_minutes)

            should_exit, reason = risk.check_exit(
                entry_price=position["entry_price"],
                current_price=price,
                peak_price=position["peak_price"],
                opened_at=position["opened_at"],
                now=now,
                price_before_crash_window=price_before_crash,
            )
            if not should_exit:
                decision = strategy.decide(window, has_open_position=True)
                if decision.signal == Signal.SELL:
                    should_exit, reason = True, decision.reason
            if should_exit:
                gross_proceeds = price * position["quantity"]
                sell_fee = gross_proceeds * fee_pct
                total_fees_paid += sell_fee
                net_proceeds = gross_proceeds - sell_fee
                pnl = net_proceeds - position["amount_spent"]  # net of both buy and sell fees
                balance += pnl
                risk.record_closed_trade(now, pnl, balance)
                trades.append({"entry": position["entry_price"], "exit": price, "pnl": pnl, "reason": reason, "time": now})
                position = None

    total_return_pct = (balance - starting_balance) / starting_balance * 100
    wins = [t for t in trades if t["pnl"] > 0]
    return {
        "trades": trades,
        "final_balance": balance,
        "total_return_pct": total_return_pct,
        "num_trades": len(trades),
        "win_rate_pct": (len(wins) / len(trades) * 100) if trades else 0.0,
        "total_fees_paid": total_fees_paid,
    }


def main():
    parser = argparse.ArgumentParser(description="Backtest the RSI/SMA strategy")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--balance", type=float, default=400.0)
    parser.add_argument(
        "--fee-pct", type=float, default=0.001,
        help="Trading fee per side, as a fraction (default 0.001 = 0.1%%, Binance's standard spot taker fee).",
    )
    args = parser.parse_args()

    print(f"Fetching {args.days} days of {args.interval} candles for {args.symbol}...")
    df = fetch_history(args.symbol, args.interval, args.days)
    print(f"Got {len(df)} candles. Running backtest with starting balance ${args.balance:.2f}...\n")

    result = run_backtest(df, args.balance, fee_pct=args.fee_pct)

    print("=" * 60)
    print(f"Symbol:           {args.symbol}")
    print(f"Period:           last {args.days} days ({args.interval} candles)")
    print(f"Fee per side:     {args.fee_pct:.2%}")
    print(f"Starting balance: ${args.balance:.2f}")
    print(f"Final balance:    ${result['final_balance']:.2f}")
    print(f"Total return:     {result['total_return_pct']:+.2f}%  (net of fees)")
    print(f"Number of trades: {result['num_trades']}")
    print(f"Win rate:         {result['win_rate_pct']:.1f}%")
    print(f"Total fees paid:  ${result['total_fees_paid']:.2f}")
    print("=" * 60)

    if result["trades"]:
        print("\nExit reason breakdown:")
        stats = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0})
        for t in result["trades"]:
            cat = categorize_exit_reason(t["reason"])
            stats[cat]["count"] += 1
            stats[cat]["pnl"] += t["pnl"]
            if t["pnl"] > 0:
                stats[cat]["wins"] += 1
        for cat, s in sorted(stats.items(), key=lambda kv: -kv[1]["count"]):
            win_rate = (s["wins"] / s["count"] * 100) if s["count"] else 0.0
            print(f"  {cat:<22} count={s['count']:>3}  win_rate={win_rate:>5.1f}%  total_pnl=${s['pnl']:+.2f}")

    print("\nNOTE: past performance on historical data is NOT a guarantee of")
    print("future results. This models Binance's standard trading fee but")
    print("still ignores real-world slippage. Use this as a sanity check,")
    print("not a promise.")


if __name__ == "__main__":
    main()
