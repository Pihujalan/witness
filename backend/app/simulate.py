"""
Synthetic Agent Behaviour Simulator
-------------------------------------
Generates scripted "normal agent" and "rogue agent" action sequences
so the Anomaly Scorer has something honest to learn from and be
evaluated against. This is explicitly a controlled simulation, not
real fraud data - see the README for why that's the right scope for
a hackathon, not a shortcut being taken quietly.

Design note against the "too easy" trap: rogue sequences aren't all
wildly different from normal ones. A third of them are only mildly
elevated (a slightly faster burst, a moderately large amount) so the
classifier - and the reported metrics - reflect a genuinely hard
boundary, not a rigged one. Report the false positive rate alongside
recall for exactly this reason.
"""
from __future__ import annotations
import math
import random
import numpy as np


def _features_for_action(velocity_1min: int, amount: int, agent_mean: float, agent_std: float,
                          is_new_counterpart: bool, hour: int) -> dict:
    # The floor here has to scale with the amount itself (paise, so typically
    # in the thousands-to-lakhs range) - a flat "1.0" floor is fine during
    # training (agent_std is never exactly 0 there) but blows up in live use:
    # an agent whose first few real requests happen to be identical amounts
    # gets a std of exactly 0, and dividing by a ~0.01-rupee floor produces a
    # nonsensical "805000x baseline" instead of an honest "no variance yet."
    std = agent_std if agent_std > 1e-6 else max(abs(agent_mean) * 0.05, 100.0)
    return {
        "velocity_1min": float(velocity_1min),
        "amount_zscore": (amount - agent_mean) / std,
        "is_new_counterpart": 1.0 if is_new_counterpart else 0.0,
        "hour_of_day_sin": math.sin(2 * math.pi * hour / 24),
        "hour_of_day_cos": math.cos(2 * math.pi * hour / 24),
    }


def generate_dataset(n_normal: int = 600, n_rogue: int = 300, seed: int = 42):
    from .anomaly import FEATURE_NAMES  # local import avoids a circular import at module load

    rng = random.Random(seed)
    X, y = [], []

    for _ in range(n_normal):
        agent_mean = rng.uniform(300_00, 3_000_00)
        agent_std = agent_mean * rng.uniform(0.1, 0.3)
        if rng.random() < 0.12:
            # Legitimate burst: e.g. a batch of end-of-day refunds. Deliberately
            # overlaps with "borderline rogue" below - a real system has to live
            # with this ambiguity, not pretend it away.
            amount = max(100, int(rng.gauss(agent_mean * 1.6, agent_std * 1.3)))
            velocity = rng.choice([3, 4, 5])
        else:
            amount = max(100, int(rng.gauss(agent_mean, agent_std)))
            velocity = rng.choice([1, 1, 1, 2, 2, 3])
        new_counterpart = rng.random() < 0.1
        hour = rng.randint(6, 23)
        feats = _features_for_action(velocity, amount, agent_mean, agent_std, new_counterpart, hour)
        X.append([feats[n] for n in FEATURE_NAMES])
        y.append(0)

    for _ in range(n_rogue):
        agent_mean = rng.uniform(300_00, 3_000_00)
        agent_std = agent_mean * rng.uniform(0.1, 0.3)
        severity = rng.random()
        if severity < 0.5:
            # Genuinely borderline - overlaps with the legitimate-burst normal
            # cases above on purpose, so recall isn't trivially perfect and
            # the false-positive rate isn't trivially zero.
            amount = max(100, int(rng.gauss(agent_mean * 1.7, agent_std * 1.4)))
            velocity = rng.choice([3, 4, 5])
            new_counterpart = rng.random() < 0.25
        else:
            # Blatant: a salami-slicing burst, or a wild outlier amount.
            amount = int(agent_mean * rng.uniform(4, 12))
            velocity = rng.randint(7, 14)
            new_counterpart = rng.random() < 0.55
        hour = rng.randint(0, 23)
        feats = _features_for_action(velocity, amount, agent_mean, agent_std, new_counterpart, hour)
        X.append([feats[n] for n in FEATURE_NAMES])
        y.append(1)

    X = np.array(X)
    y = np.array(y)
    perm = np.random.RandomState(seed).permutation(len(X))
    return X[perm], y[perm]
