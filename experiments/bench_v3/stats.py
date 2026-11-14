# pyright: basic
"""Interval and test statistics for grouped, clustered benchmark results."""

import math
import random
from collections.abc import Sequence


def binomial_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(successes: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided interval for a proportion, found by bisection."""

    def solve(target: float, upper: bool) -> float:
        low, high = 0.0, 1.0
        for _ in range(60):
            mid = (low + high) / 2
            tail = (
                binomial_cdf(successes, n, mid)
                if upper
                else 1 - binomial_cdf(successes - 1, n, mid)
            )
            if (tail > target) == upper:
                low = mid
            else:
                high = mid
        return (low + high) / 2

    if n == 0:
        return 0.0, 1.0
    lower = 0.0 if successes == 0 else solve(alpha / 2, upper=False)
    upper = 1.0 if successes == n else solve(alpha / 2, upper=True)
    return lower, upper


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    rate = successes / n
    centre = (rate + z * z / (2 * n)) / (1 + z * z / n)
    spread = (
        z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    )
    return max(0.0, centre - spread), min(1.0, centre + spread)


def mcnemar_exact(only_left: int, only_right: int) -> float:
    """Two-sided exact p value for paired binary outcomes."""
    total = only_left + only_right
    if total == 0:
        return 1.0
    tail = binomial_cdf(min(only_left, only_right), total, 0.5)
    return min(1.0, 2 * tail)


def holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, value * (len(ordered) - rank)))
        adjusted[name] = running
    return adjusted


def cluster_bootstrap(
    scores: Sequence[float],
    clusters: Sequence[str],
    draws: int = 2000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Mean and 95% interval, resampling clusters and then groups inside each cluster."""
    members: dict[str, list[float]] = {}
    for score, cluster in zip(scores, clusters, strict=True):
        members.setdefault(cluster, []).append(score)
    keys = sorted(members)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(draws):
        sample: list[float] = []
        for _ in keys:
            group = members[rng.choice(keys)]
            sample.extend(rng.choice(group) for _ in group)
        means.append(sum(sample) / len(sample))
    means.sort()
    centre = sum(scores) / len(scores)
    return centre, means[int(0.025 * draws)], means[int(0.975 * draws) - 1]
