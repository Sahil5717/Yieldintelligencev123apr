"""Portfolio optimizer — constrained budget allocation across channels.

Given per-channel response curves (from MMM), find spend allocation that maximizes
expected revenue subject to:
  - Total budget constraint
  - Per-channel min/max bounds
  - Optionally: no channel drops below X% of current

Uses scipy.optimize.minimize (SLSQP) — simpler than CVXPY for the nonlinear Hill
objective and sufficient for 10-15 channels.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize

from app.mmm.transforms import hill_saturation


def _portfolio_revenue(
    spends: np.ndarray,
    alphas: np.ndarray,
    Ks: np.ndarray,
    betas: np.ndarray,
    shape: float,
) -> float:
    """Total portfolio revenue under steady-state adstock."""
    # Steady-state effective spend: spend / (1 - alpha)
    eff = spends / np.maximum(1 - alphas, 1e-6)
    saturated = hill_saturation(eff, half_sat=Ks, shape=shape)
    return float(np.sum(betas * saturated))


def optimize_allocation(
    channels: list[str],
    current_spend: dict[str, float],
    mmm_summary: dict,
    total_budget: float | None = None,
    min_spend_pct: float = 0.25,  # no channel below 25% of current
    max_spend_pct: float = 2.5,   # no channel above 250% of current
    locked_channels: dict[str, float] | None = None,
) -> dict:
    """Optimize spend allocation.

    Args:
        channels: channel names in priority order
        current_spend: baseline per-channel monthly spend
        mmm_summary: posterior summary from MMM (alpha, K, beta per channel)
        total_budget: target total (default: sum of current_spend)
        min_spend_pct, max_spend_pct: bounds as multiple of current
        locked_channels: channels with fixed spend (not optimized)

    Returns:
        dict with per-channel optimal spend, expected revenue, marginal ROIs
    """
    locked = locked_channels or {}
    free_channels = [c for c in channels if c not in locked]
    if not free_channels:
        return {"allocation": current_spend, "expected_revenue": 0, "marginal_roi": {}}

    # Extract per-channel params
    alphas = np.array([mmm_summary["per_channel"][c]["alpha"]["mean"] for c in free_channels])
    Ks = np.array([mmm_summary["per_channel"][c]["K"]["mean"] for c in free_channels])
    betas = np.array([mmm_summary["per_channel"][c]["beta"]["mean"] for c in free_channels])
    shape = mmm_summary.get("hill_shape", 1.0)

    current = np.array([current_spend.get(c, 0.0) for c in free_channels])
    if total_budget is None:
        total_budget = current.sum() + sum(locked.values())
    free_budget = total_budget - sum(locked.values())

    # Negative objective (we're minimizing)
    def neg_revenue(x):
        return -_portfolio_revenue(x, alphas, Ks, betas, shape)

    def grad_neg_revenue(x):
        # d/dx_i of beta_i * x_i^s / (x_i^s + K_i^s) under steady-state adstock
        # Letting e_i = x_i / (1 - alpha_i), dr_i/dx_i = dr_i/de_i * 1/(1-alpha_i)
        e = x / np.maximum(1 - alphas, 1e-6)
        e_safe = np.maximum(e, 1e-9)
        num = shape * (Ks ** shape) * (e_safe ** (shape - 1))
        den = (e_safe ** shape + Ks ** shape) ** 2
        de_dx = 1 / np.maximum(1 - alphas, 1e-6)
        grad = -betas * num / den * de_dx
        return grad

    # Bounds per channel
    bounds = [
        (
            max(min_spend_pct * current[i], 0),
            max(max_spend_pct * current[i], current[i] * 1.1) if current[i] > 0 else free_budget * 0.5,
        )
        for i in range(len(free_channels))
    ]

    # Budget equality constraint
    constraints = {"type": "eq", "fun": lambda x: x.sum() - free_budget}

    # Initial guess: current spend, rescaled to fit budget
    x0 = current.copy()
    if x0.sum() > 0:
        x0 = x0 * (free_budget / x0.sum())
    else:
        x0 = np.full(len(free_channels), free_budget / len(free_channels))

    result = minimize(
        neg_revenue,
        x0,
        jac=grad_neg_revenue,
        bounds=bounds,
        constraints=[constraints],
        method="SLSQP",
        options={"maxiter": 200, "ftol": 1e-6},
    )

    optimal = np.maximum(result.x, 0)

    # Compute per-channel marginal ROI at optimum
    e = optimal / np.maximum(1 - alphas, 1e-6)
    e_safe = np.maximum(e, 1e-9)
    num = shape * (Ks ** shape) * (e_safe ** (shape - 1))
    den = (e_safe ** shape + Ks ** shape) ** 2
    marginal_roi_per_ch = betas * num / den / np.maximum(1 - alphas, 1e-6)

    allocation = {c: float(s) for c, s in zip(free_channels, optimal)}
    allocation.update(locked)

    return {
        "allocation": allocation,
        "current": {c: current_spend.get(c, 0.0) for c in channels},
        "expected_revenue": float(-result.fun),
        "marginal_roi": {c: float(m) for c, m in zip(free_channels, marginal_roi_per_ch)},
        "total_budget": float(total_budget),
        "converged": bool(result.success),
        "optimizer_message": str(result.message),
    }


def current_state(
    channels: list[str],
    current_spend: dict[str, float],
    mmm_summary: dict,
) -> dict:
    """Compute current portfolio ROI + per-channel marginal ROI at current spend.

    Useful for "where you stand" views without running optimization.
    """
    alphas = np.array([mmm_summary["per_channel"][c]["alpha"]["mean"] for c in channels])
    Ks = np.array([mmm_summary["per_channel"][c]["K"]["mean"] for c in channels])
    betas = np.array([mmm_summary["per_channel"][c]["beta"]["mean"] for c in channels])
    shape = mmm_summary.get("hill_shape", 1.0)

    spends = np.array([current_spend.get(c, 0.0) for c in channels])
    total_rev = _portfolio_revenue(spends, alphas, Ks, betas, shape)
    total_spend = spends.sum()

    e = spends / np.maximum(1 - alphas, 1e-6)
    e_safe = np.maximum(e, 1e-9)
    num = shape * (Ks ** shape) * (e_safe ** (shape - 1))
    den = (e_safe ** shape + Ks ** shape) ** 2
    marg = betas * num / den / np.maximum(1 - alphas, 1e-6)

    # Avg ROI = total revenue / total spend
    avg_roi = total_rev / total_spend if total_spend else 0

    return {
        "total_expected_revenue": float(total_rev),
        "total_spend": float(total_spend),
        "avg_roi": float(avg_roi),
        "marginal_roi": {c: float(m) for c, m in zip(channels, marg)},
        "current_spend": {c: float(s) for c, s in zip(channels, spends)},
    }
