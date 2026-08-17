"""Crypto Investment Agent - a Binance trading bot with built-in risk management.

Safety-first design:
- Defaults to Binance Testnet (fake money) unless explicitly configured for live trading.
- Every trade passes through RiskManager: position sizing, stop-loss, take-profit,
  a daily loss kill-switch, and a max-trades-per-day cap.
"""
