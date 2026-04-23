"""MMM transforms: adstock (carryover) and Hill saturation.

Used by both the PyMC model builder and by inference code that reads posterior samples.
Pure numpy so it works without PyMC imported.
"""
from __future__ import annotations
import numpy as np


def adstock_geometric(x: np.ndarray, alpha: float, lag_max: int = 12) -> np.ndarray:
    """Geometric adstock — each period's effect decays by (1-alpha) every period.

    Args:
        x: shape (T,) spend series for one channel
        alpha: retention rate in [0, 1). 0 = no carryover, higher = longer memory.
        lag_max: truncate the convolution kernel (e.g. 12 months of memory)

    Returns:
        adstocked series, shape (T,)
    """
    if alpha <= 0:
        return x.copy()

    weights = np.array([alpha ** i for i in range(lag_max + 1)])
    weights /= weights.sum()

    out = np.zeros_like(x, dtype=float)
    for t in range(len(x)):
        for lag in range(min(t + 1, lag_max + 1)):
            out[t] += weights[lag] * x[t - lag]
    return out


def hill_saturation(x: np.ndarray, half_sat: float, shape: float = 1.0) -> np.ndarray:
    """Hill saturation curve — diminishing returns.

    Returns values in [0, 1] that saturate as x grows.
        response = x^shape / (x^shape + half_sat^shape)

    Args:
        x: adstocked spend series (>= 0)
        half_sat: spend level at which response is 50% of max — defines curvature
        shape: curve shape param; 1 = classic Hill, higher = more S-shaped

    Returns:
        saturated response in [0, 1]
    """
    x_safe = np.maximum(x, 1e-9)
    return x_safe ** shape / (x_safe ** shape + half_sat ** shape)


def marginal_roi(spend: float, half_sat: float, shape: float, scale: float,
                 alpha: float = 0.0, steady_state: bool = True) -> float:
    """Instantaneous marginal ROI at a given spend level.

    scale = beta × (contribution_multiplier). The response = scale × Hill(adstock(spend)).
    Derivative wrt spend at the operating point.

    If steady_state, uses steady-state adstock (spend/(1-alpha)).
    """
    # Under steady-state geometric adstock, effective = spend / (1 - alpha)
    eff = spend / (1 - alpha) if alpha > 0 and steady_state else spend
    eff = max(eff, 1e-9)
    # d/dx of Hill: shape * half_sat^shape * x^(shape-1) / (x^shape + half_sat^shape)^2
    num = shape * (half_sat ** shape) * (eff ** (shape - 1))
    den = (eff ** shape + half_sat ** shape) ** 2
    return scale * num / den


def response_curve(half_sat: float, shape: float, scale: float,
                   alpha: float = 0.0, n_points: int = 40,
                   max_spend: float | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate (spend, response, marginal_roi) arrays for a channel's curve.

    Response is in revenue units. Useful for frontend charts and optimizer.
    """
    if max_spend is None:
        max_spend = half_sat * 4
    spends = np.linspace(0, max_spend, n_points)
    # Under steady-state adstock, effective spend = spend / (1 - alpha)
    eff = spends / (1 - alpha) if alpha > 0 else spends
    responses = scale * hill_saturation(eff, half_sat, shape)
    # Marginal = d_response/d_spend
    marginals = np.array([marginal_roi(s, half_sat, shape, scale, alpha) for s in spends])
    return spends, responses, marginals
