from datetime import datetime, timedelta

from src.crypto_agent.risk_manager import RiskManager


def make_rm(**overrides):
    defaults = dict(
        max_position_pct=0.2,
        stop_loss_pct=0.015,
        trailing_activation_pct=0.02,
        trailing_distance_pct=0.015,
        max_hold_hours=6,
        crash_drop_pct=0.07,
        crash_window_minutes=60,
        max_daily_loss_pct=0.05,
        max_trades_per_day=3,
    )
    defaults.update(overrides)
    return RiskManager(**defaults)


NOW = datetime(2026, 1, 1, 12, 0)
OPENED_RECENTLY = NOW - timedelta(hours=1)


def test_position_size_respects_max_pct():
    rm = make_rm(max_position_pct=0.25)
    assert rm.position_size(400) == 100.0


def test_stop_loss_triggers_exit():
    rm = make_rm(stop_loss_pct=0.015)
    should_exit, reason = rm.check_exit(
        entry_price=100, current_price=98.4, peak_price=100, opened_at=OPENED_RECENTLY, now=NOW
    )
    assert should_exit is True
    assert "stop-loss" in reason


def test_no_exit_within_bounds():
    rm = make_rm()
    should_exit, reason = rm.check_exit(
        entry_price=100, current_price=100.5, peak_price=100.5, opened_at=OPENED_RECENTLY, now=NOW
    )
    assert should_exit is False
    assert reason is None


def test_trailing_stop_does_not_fire_before_activation():
    # Up only 1%, below the 2% activation threshold -> a 1.5% pullback from
    # this small peak must NOT trigger a trailing-stop exit.
    rm = make_rm(trailing_activation_pct=0.02, trailing_distance_pct=0.015)
    should_exit, reason = rm.check_exit(
        entry_price=100, current_price=99.6, peak_price=101, opened_at=OPENED_RECENTLY, now=NOW
    )
    assert should_exit is False


def test_trailing_stop_fires_after_activation_and_pullback():
    # Peak was +3% (past the 2% activation), now pulled back >1.5% from that peak.
    rm = make_rm(trailing_activation_pct=0.02, trailing_distance_pct=0.015)
    should_exit, reason = rm.check_exit(
        entry_price=100, current_price=101.4, peak_price=103, opened_at=OPENED_RECENTLY, now=NOW
    )
    assert should_exit is True
    assert "trailing-stop" in reason


def test_trailing_stop_does_not_fire_within_distance_of_peak():
    rm = make_rm(trailing_activation_pct=0.02, trailing_distance_pct=0.015)
    should_exit, _ = rm.check_exit(
        entry_price=100, current_price=102.6, peak_price=103, opened_at=OPENED_RECENTLY, now=NOW
    )
    assert should_exit is False


def test_time_limit_exit_fires_after_max_hold_hours():
    rm = make_rm(max_hold_hours=6)
    opened_at = NOW - timedelta(hours=6, minutes=1)
    should_exit, reason = rm.check_exit(
        entry_price=100, current_price=100.2, peak_price=100.5, opened_at=opened_at, now=NOW
    )
    assert should_exit is True
    assert "time-limit" in reason


def test_time_limit_exit_does_not_fire_before_max_hold_hours():
    rm = make_rm(max_hold_hours=6)
    opened_at = NOW - timedelta(hours=5)
    should_exit, _ = rm.check_exit(
        entry_price=100, current_price=100.2, peak_price=100.5, opened_at=opened_at, now=NOW
    )
    assert should_exit is False


def test_crash_circuit_breaker_overrides_normal_stop_loss():
    rm = make_rm(crash_drop_pct=0.07, stop_loss_pct=0.015)
    # Price fell 8% within the crash window - well beyond the 7% threshold.
    should_exit, reason = rm.check_exit(
        entry_price=100,
        current_price=92,
        peak_price=100,
        opened_at=OPENED_RECENTLY,
        now=NOW,
        price_before_crash_window=100,
    )
    assert should_exit is True
    assert "CRASH" in reason


def test_crash_circuit_breaker_does_not_fire_on_normal_dip():
    rm = make_rm(crash_drop_pct=0.07)
    should_exit, reason = rm.check_exit(
        entry_price=100,
        current_price=99,
        peak_price=100,
        opened_at=OPENED_RECENTLY,
        now=NOW,
        price_before_crash_window=100,
    )
    # 1% dip shouldn't trip the crash breaker or the (1.5%) stop-loss.
    assert should_exit is False


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
