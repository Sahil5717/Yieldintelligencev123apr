"""Markov chain attribution — removal effect method.

For each journey: sequence of channels ending in conversion or dropoff.
Build transition matrix over channels + start/conversion/null states.
A channel's credit = (overall conversion rate) - (conversion rate with that channel removed),
normalized across channels so they sum to 1.

Fast: ~seconds on 100K journeys.
"""
from __future__ import annotations
from collections import defaultdict
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.journey import JourneyTouchpoint


START = "__start__"
CONVERT = "__convert__"
NULL = "__null__"  # dropoff without converting


def build_journeys(db: Session) -> list[tuple[list[str], bool]]:
    """Load journeys from DB, return list of (channel_sequence, converted).

    Returns journeys ordered by touchpoint_order within each journey.
    """
    rows = db.execute(
        select(
            JourneyTouchpoint.journey_id,
            JourneyTouchpoint.touchpoint_order,
            JourneyTouchpoint.channel,
            JourneyTouchpoint.converted,
        ).order_by(JourneyTouchpoint.journey_id, JourneyTouchpoint.touchpoint_order)
    ).all()
    df = pd.DataFrame(rows, columns=["journey_id", "order", "channel", "converted"])
    out = []
    for jid, grp in df.groupby("journey_id"):
        chans = grp.sort_values("order")["channel"].tolist()
        converted = bool(grp["converted"].any())
        out.append((chans, converted))
    return out


def build_transition_matrix(journeys: list[tuple[list[str], bool]]) -> tuple[pd.DataFrame, list[str]]:
    """Build empirical transition probabilities over states (channels + sentinels).

    For each journey:
        START -> channel[0] -> channel[1] -> ... -> (CONVERT or NULL)

    Returns (transitions_df, all_states).
    """
    transitions: dict[tuple[str, str], int] = defaultdict(int)
    channels: set[str] = set()

    for chans, converted in journeys:
        if not chans:
            continue
        channels.update(chans)
        transitions[(START, chans[0])] += 1
        for i in range(len(chans) - 1):
            transitions[(chans[i], chans[i + 1])] += 1
        end_state = CONVERT if converted else NULL
        transitions[(chans[-1], end_state)] += 1

    states = sorted(channels) + [START, CONVERT, NULL]
    idx = {s: i for i, s in enumerate(states)}
    n = len(states)

    counts = np.zeros((n, n))
    for (a, b), c in transitions.items():
        counts[idx[a], idx[b]] = c
    row_sums = counts.sum(axis=1, keepdims=True)
    probs = np.divide(counts, row_sums, out=np.zeros_like(counts), where=row_sums > 0)

    # Absorbing states: CONVERT and NULL always transition to themselves
    probs[idx[CONVERT], idx[CONVERT]] = 1.0
    probs[idx[NULL], idx[NULL]] = 1.0

    return pd.DataFrame(probs, index=states, columns=states), states


def conversion_prob_from_start(P: pd.DataFrame, steps: int = 50) -> float:
    """Probability of reaching CONVERT starting from START under transition matrix P."""
    start_vec = np.zeros(len(P))
    start_vec[P.index.get_loc(START)] = 1.0
    # Iterate to stationary (absorbing state convergence)
    current = start_vec
    P_mat = P.values
    for _ in range(steps):
        current = current @ P_mat
    return float(current[P.index.get_loc(CONVERT)])


def markov_attribution(db: Session) -> dict:
    """Compute channel credit via removal effect.

    For each channel: remove it (redirect transitions to NULL), compute new conversion prob.
    Credit proportional to the drop.
    """
    journeys = build_journeys(db)
    if not journeys:
        return {"channels": [], "credit": {}, "baseline_conversion_prob": 0.0}

    P, states = build_transition_matrix(journeys)
    baseline = conversion_prob_from_start(P)

    channels = [s for s in states if s not in (START, CONVERT, NULL)]
    removal_effect = {}

    for ch in channels:
        P_mod = P.copy()
        # Redirect all incoming transitions to ch into NULL
        # i.e., zero out column ch, add to column NULL for each row
        incoming = P_mod[ch].copy()
        P_mod[NULL] = P_mod[NULL] + incoming
        P_mod[ch] = 0.0
        # Rebalance rows: since we moved mass, rows still sum to 1 by construction
        new_prob = conversion_prob_from_start(P_mod)
        removal_effect[ch] = max(0.0, baseline - new_prob)

    total = sum(removal_effect.values())
    credit = {ch: (v / total if total > 0 else 0) for ch, v in removal_effect.items()}

    return {
        "channels": channels,
        "baseline_conversion_prob": baseline,
        "removal_effects": removal_effect,
        "credit": credit,
        "journey_count": len(journeys),
    }
