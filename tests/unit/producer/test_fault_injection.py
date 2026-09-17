import random

from reliable_ingestion.producer.fault_injection import delay_seconds, should_duplicate


def test_should_duplicate_never_triggers_at_zero_probability():
    rng = random.Random(1)
    assert all(not should_duplicate(rng, 0.0) for _ in range(200))


def test_should_duplicate_always_triggers_at_one_probability():
    rng = random.Random(1)
    assert all(should_duplicate(rng, 1.0) for _ in range(200))


def test_delay_seconds_is_zero_at_zero_probability():
    rng = random.Random(1)
    assert all(delay_seconds(rng, 0.0, 5.0) == 0.0 for _ in range(200))


def test_delay_seconds_within_bounds_at_full_probability():
    rng = random.Random(1)
    for _ in range(200):
        value = delay_seconds(rng, 1.0, 5.0)
        assert 0.0 <= value <= 5.0


def test_same_rng_state_is_deterministic():
    first = [should_duplicate(random.Random(9), 0.5) for _ in range(20)]
    second = [should_duplicate(random.Random(9), 0.5) for _ in range(20)]
    assert first == second
