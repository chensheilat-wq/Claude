import os

from src.crypto_agent.capital_ledger import CapitalLedger


def make_ledger(tmp_path, principal=400.0):
    path = os.path.join(tmp_path, "ledger.json")
    return CapitalLedger(principal=principal, path=path)


def test_starts_with_no_reserve_and_first_milestone_at_double_principal(tmp_path):
    ledger = make_ledger(tmp_path)
    assert ledger.reserve_balance == 0.0
    assert ledger.next_milestone == 800.0
    assert ledger.trading_capital(400.0) == 400.0


def test_no_lock_before_milestone_reached(tmp_path):
    ledger = make_ledger(tmp_path)
    hit = ledger.check_and_lock(799.99)
    assert hit == []
    assert ledger.reserve_balance == 0.0


def test_matches_user_example_sequence(tmp_path):
    """Exactly reproduces the 400 -> 800 -> 1600 -> 3200 sequence the user specified."""
    ledger = make_ledger(tmp_path, principal=400.0)

    hit = ledger.check_and_lock(800.0)
    assert hit == [800.0]
    assert ledger.reserve_balance == 400.0
    assert ledger.trading_capital(800.0) == 400.0
    assert ledger.next_milestone == 1600.0

    hit = ledger.check_and_lock(1600.0)
    assert hit == [1600.0]
    assert ledger.reserve_balance == 800.0
    assert ledger.trading_capital(1600.0) == 800.0
    assert ledger.next_milestone == 3200.0

    hit = ledger.check_and_lock(3200.0)
    assert hit == [3200.0]
    assert ledger.reserve_balance == 1600.0
    assert ledger.trading_capital(3200.0) == 1600.0
    assert ledger.next_milestone == 6400.0


def test_ladder_continues_indefinitely(tmp_path):
    ledger = make_ledger(tmp_path)  # next_milestone starts at 400 * 2^1 = 800
    for _ in range(5):
        ledger.check_and_lock(ledger.next_milestone)
    assert ledger.next_milestone == 400 * (2 ** 6)  # 5 more doublings on top of the initial 2^1


def test_reserve_ratchets_and_never_decreases_on_drawdown(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.check_and_lock(800.0)
    assert ledger.reserve_balance == 400.0

    # Trading capital lost money and total dropped back down - reserve must not shrink.
    hit = ledger.check_and_lock(500.0)
    assert hit == []
    assert ledger.reserve_balance == 400.0
    assert ledger.trading_capital(500.0) == 100.0


def test_single_jump_crosses_multiple_milestones_at_once(tmp_path):
    ledger = make_ledger(tmp_path)
    # A huge single gain jumps straight past 800 and 1600, landing at 2000.
    hit = ledger.check_and_lock(2000.0)
    assert hit == [800.0, 1600.0]
    assert ledger.reserve_balance == 800.0  # half of the highest milestone crossed (1600)
    assert ledger.next_milestone == 3200.0


def test_trading_capital_never_negative(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.reserve_balance = 400.0  # simulate a locked reserve larger than the current total
    assert ledger.trading_capital(100.0) == 0.0


def test_state_persists_across_instances(tmp_path):
    path = os.path.join(tmp_path, "ledger.json")
    ledger1 = CapitalLedger(principal=400.0, path=path)
    ledger1.check_and_lock(800.0)

    ledger2 = CapitalLedger(principal=400.0, path=path)
    assert ledger2.reserve_balance == 400.0
    assert ledger2.next_milestone == 1600.0
