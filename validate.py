#!/usr/bin/env python3
"""Validates whether the strategy shows a REAL, CONSISTENT edge - not just a
result from one backtest window that happened to look good (or bad). Runs
the strategy across multiple symbols and multiple non-overlapping historical
time chunks, and reports each result plus an aggregate.

Why this matters: repeatedly tweaking parameters and re-testing on the same
90-day BTC window risks fitting the noise of that specific window, not
finding a real edge. This script instead asks "does this strategy make
money across a variety of coins and time periods it hasn't been tuned on?" -
which is a much harder, more honest question.

Usage:
    python validate.py --days 180 --chunks 3 --balance 400
"""

import argparse

from backtest import fetch_history, run_backtest

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]


def main():
    parser = argparse.ArgumentParser(description="Validate strategy edge across symbols and time periods")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--days", type=int, default=180, help="Total historical days to fetch per symbol")
    parser.add_argument("--chunks", type=int, default=3, help="Split the history into this many non-overlapping periods")
    parser.add_argument("--balance", type=float, default=400.0)
    parser.add_argument("--fee-pct", type=float, default=0.001)
    args = parser.parse_args()

    all_results = []

    for symbol in args.symbols:
        print(f"\n=== {symbol} ===")
        try:
            df = fetch_history(symbol, args.interval, args.days)
        except Exception as e:
            print(f"  Failed to fetch data: {e}")
            continue

        n = len(df)
        chunk_size = n // args.chunks
        if chunk_size < 100:
            print(f"  Not enough candles ({n}) to split into {args.chunks} meaningful chunks - skipping.")
            continue

        for i in range(args.chunks):
            start = i * chunk_size
            end = n if i == args.chunks - 1 else (i + 1) * chunk_size
            chunk_df = df.iloc[start:end].reset_index(drop=True)

            result = run_backtest(chunk_df, args.balance, fee_pct=args.fee_pct)
            period_start = chunk_df["open_time"].iloc[0]
            period_end = chunk_df["open_time"].iloc[-1]
            print(
                f"  period {i + 1} ({period_start.date()} to {period_end.date()}): "
                f"trades={result['num_trades']:>3}  "
                f"return={result['total_return_pct']:+6.2f}%  "
                f"win_rate={result['win_rate_pct']:5.1f}%"
            )
            all_results.append({"symbol": symbol, "period": i + 1, **result})

    if not all_results:
        print("\nNo results collected - could not fetch any data.")
        return

    returns = [r["total_return_pct"] for r in all_results]
    positive = [r for r in returns if r > 0]
    total_trades = sum(r["num_trades"] for r in all_results)

    print("\n" + "=" * 70)
    print("AGGREGATE ACROSS ALL SYMBOL / PERIOD COMBINATIONS")
    print("=" * 70)
    print(f"Total runs:                 {len(all_results)}")
    print(f"Total trades across all:    {total_trades}")
    print(f"Runs with positive return:  {len(positive)} / {len(all_results)} ({len(positive) / len(all_results) * 100:.0f}%)")
    print(f"Average return per run:     {sum(returns) / len(returns):+.2f}%")
    print(f"Best run:                   {max(returns):+.2f}%")
    print(f"Worst run:                  {min(returns):+.2f}%")
    print("=" * 70)
    print("\nHow to read this: if positive runs are close to a coin-flip (~50%) or")
    print("below, and the average return is flat or negative, the entry signal")
    print("likely does not have a real edge on this timeframe - more parameter")
    print("tuning on a single window would be overfitting noise, not finding an")
    print("edge. A real edge should show up as MOSTLY positive runs across")
    print("different coins and periods it was never tuned on.")


if __name__ == "__main__":
    main()
