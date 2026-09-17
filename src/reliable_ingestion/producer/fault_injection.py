from __future__ import annotations

import random


def should_duplicate(rng: random.Random, duplicate_probability: float) -> bool:
    return rng.random() < duplicate_probability


def delay_seconds(
    rng: random.Random, delay_probability: float, max_delay_seconds: float
) -> float:
    if rng.random() >= delay_probability:
        return 0.0
    return rng.uniform(0.0, max_delay_seconds)
