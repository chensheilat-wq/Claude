#!/usr/bin/env python3
"""One-off diagnostic: pulls real historical data and reports how close (or
far) the strategy's entry condition (RSI oversold + price above SMA trend)
actually came to firing. Use this when a backtest shows zero trades and you
want to know whether that's genuinely rare market behavior or a bug.

Usage:
    python diagnose.py --symbol BTCUSDT --interval 15m --days 90
"""

import argparse

from src.crypto_agent.indicators import rsi, sma
from backtest import fetch_history


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--rsi-oversold", type=float, default=30)
    parser.add_argument("--sma-period", type=int, default=50)
    args = parser.parse_args()

    print(f"Fetching {args.days} days of {args.interval} candles for {args.symbol}...")
    df = fetch_history(args.symbol, args.interval, args.days)
    closes = df["close"].astype(float)

    rsi_series = rsi(closes, args.rsi_period)
    sma_series = sma(closes, args.sma_period)

    valid = (~rsi_series.isna()) & (~sma_series.isna())
    rsi_v = rsi_series[valid]
    sma_v = sma_series[valid]
    price_v = closes[valid]
    time_v = df["open_time"][valid]

    oversold_mask = rsi_v < args.rsi_oversold
    above_sma_mask = price_v > sma_v
    entry_mask = oversold_mask & above_sma_mask

    print("=" * 60)
    print(f"Total usable candles:              {len(rsi_v)}")
    print(f"RSI range:                         {rsi_v.min():.1f} - {rsi_v.max():.1f}")
    print(f"Candles with RSI < {args.rsi_oversold:.0f} (oversold):        {oversold_mask.sum()}")
    print(f"Candles with price > SMA{args.sma_period} (uptrend):    {above_sma_mask.sum()}")
    print(f"Candles meeting BOTH (= entry signal): {entry_mask.sum()}")
    print("=" * 60)

    if entry_mask.sum() > 0:
        print("\nEntry signals would have fired at:")
        for t, p, r in zip(time_v[entry_mask], price_v[entry_mask], rsi_v[entry_mask]):
            print(f"  {t}  price={p:.2f}  rsi={r:.1f}")
    elif oversold_mask.sum() > 0:
        print("\nRSI DID go oversold, but never while price was above the SMA (i.e. every")
        print("dip happened during a downtrend, not a pullback within an uptrend).")
        print("Closest near-misses (oversold candles, showing price vs SMA at that moment):")
        near = rsi_v[oversold_mask].sort_values().head(5)
        for idx in near.index:
            print(f"  {time_v[idx]}  price={price_v[idx]:.2f}  sma={sma_v[idx]:.2f}  rsi={rsi_v[idx]:.1f}")
    else:
        print("\nRSI never went below the oversold threshold at all in this window.")
        print(f"Lowest RSI reached: {rsi_v.min():.1f} at {time_v[rsi_v.idxmin()]}")


if __name__ == "__main__":
    main()
