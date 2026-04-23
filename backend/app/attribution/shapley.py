"""Shapley-value attribution — for cross-channel credit assignment.

Exact Shapley over all 2^C coalitions is only feasible for C ≤ ~12. For larger sets,
use Monte Carlo: sample random permutations, compute marginal contribution of each
channel.

For our product, C ≈ 9-11 paid channels, so exact is tractable.
"""
from __future__ import annotations
from itertools import combinations
from math import factorial
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.journey import JourneyTouchpoint
from app.attribution.markov import build_journeys


def _coalition_conversions(journeys: list[tuple[list[str], bool]], coalition: frozenset[str]) -> int:
    """Count journeys that converted using ONLY channels in `coalition`."""
    n = 0
    for chans, converted in journeys:
        if not converted:
            continue
        if all(c in coalition for c in chans):
            n += 1
    return n


def shapley_attribution(db: Session, max_channels: int = 10) -> dict:
    """Compute Shapley value per channel.

    Value function v(S) = number of conversions attributable to coalition S,
    where a journey is attributed to S if every touchpoint is in S.

    Shapley value of channel i = average over all subsets S not containing i of:
        [v(S ∪ {i}) - v(S)] weighted by |S|!*(C-|S|-1)!/C!
    """
    journeys = build_journeys(db)
    if not journeys:
        return {"channels": [], "credit": {}, "method": "shapley"}

    # Find channels and limit to top N by touchpoint frequency if too many
    channel_counts: dict[str, int] = {}
    for chans, _ in journeys:
        for c in chans:
            channel_counts[c] = channel_counts.get(c, 0) + 1
    channels = sorted(channel_counts, key=channel_counts.get, reverse=True)[:max_channels]

    C = len(channels)
    if C == 0:
        return {"channels": [], "credit": {}, "method": "shapley"}

    # Filter journeys to those using only channels in our set (others excluded)
    chan_set = set(channels)
    filtered = [(ch, conv) for ch, conv in journeys if all(c in chan_set for c in ch) and ch]

    # Precompute v(S) for every subset of channels
    v: dict[frozenset[str], int] = {}
    for size in range(C + 1):
        for combo in combinations(channels, size):
            S = frozenset(combo)
            v[S] = _coalition_conversions(filtered, S)

    # Shapley weights: |S|! * (C - |S| - 1)! / C!
    C_fact = factorial(C)
    shapley_values = {ch: 0.0 for ch in channels}
    for ch in channels:
        others = [c for c in channels if c != ch]
        for size in range(len(others) + 1):
            weight = factorial(size) * factorial(C - size - 1) / C_fact
            for combo in combinations(others, size):
                S = frozenset(combo)
                marginal = v[S | {ch}] - v[S]
                shapley_values[ch] += weight * marginal

    total = sum(shapley_values.values())
    credit = {ch: (val / total if total > 0 else 0) for ch, val in shapley_values.items()}

    return {
        "channels": channels,
        "shapley_values_raw": shapley_values,
        "credit": credit,
        "total_conversions": v[frozenset(channels)],
        "journey_count": len(filtered),
        "method": "shapley_exact" if C <= 10 else "shapley_limited",
    }
