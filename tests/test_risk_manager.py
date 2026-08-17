from datetime import datetime, timedelta

from src.crypto_agent.risk_manager import RiskManager


def make_rm(**overrides):
    defaults = dict(
        max_position_pct=0.2,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_daily_loss_pct=0.05,
        max_trades_per_day=3,
    )
    defaults.update(overrides)
    return RiskManager(**defaults)


def test_position_size_respects_max_pct():
    rm = make_rm(max_position_pct=0.25)
    assert rm.position_size(400) == 100.0


def test_stop_loss_triggers_exit():
    rm = make_rm(stop_loss_pct=0.02)
    should_exit, reason = rm.check_exit(entry_price=100, current_price=97.9)
    assert should_exit is True
    assert "stop-loss" in reason


def test_take_profit_triggers_exit():
    rm = make_rm(take_profit_pct=0.04)
    should_exit, reason = rm.check_exit(entry_price=100, current_price=104.5)
    assert should_exit is True
    assert "take-profit" in reason


def test_no_exit_within_bounds():
    rm = make_rm()
    should_exit, reason = rm.check_exit(entry_price=100, current_price=101)
    assert should_exit is False
    assert reason is None


def test_max_trades_per_day_blocks_further_trades():
    rm = make_rm(max_trades_per_day=2)
    now = datetime(2026, 1, 1, 10, 0)
    rm.record_closed_trade(now, pnl_amount=1, current_balance=401)
    rm.record_closed_trade(now, pnl_amount=1, current_balance=402)
    can_trade, reason = rm.can_open_trade(now, 402)
    assert can_trade is False
    assert "Max trades" in reason


def test_daily_loss_limit_triggers_kill_switch():
    rm = make_rm(max_daily_loss_pct=0.05)
    now = datetime(2026, 1, 1, 10, 0)
    # First call establishes the daily starting balance (400).
    can_trade, _ = rm.can_open_trade(now, 400)
    assert can_trade is True
    # Lose more than 5% of 400 (= 20) in one trade.
    rm.record_closed_trade(now, pnl_amount=-25, current_balance=375)
    can_trade, reason = rm.can_open_trade(now, 375)
    assert can_trade is False
    assert "kill-switch" in reason.lower()


def test_kill_switch_resets_on_new_day():
    rm = make_rm(max_daily_loss_pct=0.05, max_trades_per_day=1)
    day1 = datetime(2026, 1, 1, 10, 0)
    rm.can_open_trade(day1, 400)
    rm.record_closed_trade(day1, pnl_amount=-25, current_balance=375)
    assert rm.can_open_trade(day1, 375)[0] is False

    day2 = day1 + timedelta(days=1)
    can_trade, _ = rm.can_open_trade(day2, 375)
    assert can_trade is True
