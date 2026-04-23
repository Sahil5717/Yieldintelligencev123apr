"""Bayesian MMM model — PyMC 5.

Hierarchical model:
    revenue_t = intercept + sum_c [ beta_c * hill(adstock(spend_c_t; alpha_c); K_c, s) ]
              + trend_t + seasonality_t + noise

Priors:
    alpha_c ~ Beta(2, 2)                       — retention in (0,1), informative
    K_c ~ LogNormal(log(mean_spend_c), 1.0)    — half-sat near observed spend scale
    beta_c ~ HalfNormal(sigma_beta)            — non-negative channel effect
    intercept ~ Normal(mean_rev, sd_rev/4)
    sigma ~ HalfNormal(sd_rev/4)

This is intentionally moderate — not over-engineered. It will converge in 10-30 minutes
on 5-year monthly Acme data (60 obs × 9 paid channels).
"""
from __future__ import annotations
import json
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from app.mmm.transforms import adstock_geometric, hill_saturation


# ----------------------------------------------------------------------------
# Data prep — from DB into model-ready arrays
# ----------------------------------------------------------------------------

def prepare_mmm_data(db, min_spend: float = 1000.0) -> dict:
    """Pull Campaign_Performance from DB, aggregate to monthly × channel.

    Returns a dict with:
        dates: list[date]                  length T (months)
        channels: list[str]                length C (paid channels only, filtered)
        spend: ndarray (T, C)              monthly spend per channel
        revenue: ndarray (T,)              total monthly revenue (paid attributed)
        channel_spend_scale: ndarray (C,)  scale factor per channel (for priors)
    """
    from app.models.campaign import CampaignPerformance
    from sqlalchemy import select, func

    # Aggregate to month × channel
    rows = db.execute(
        select(
            CampaignPerformance.date,
            CampaignPerformance.channel,
            func.sum(CampaignPerformance.spend),
            func.sum(CampaignPerformance.revenue),
        ).group_by(CampaignPerformance.date, CampaignPerformance.channel)
    ).all()

    df = pd.DataFrame(rows, columns=["date", "channel", "spend", "revenue"])
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    monthly = df.groupby(["month", "channel"], as_index=False).agg(
        spend=("spend", "sum"),
        revenue=("revenue", "sum"),
    )

    # Filter to paid channels with meaningful spend
    channel_total = monthly.groupby("channel")["spend"].sum()
    paid_channels = [c for c in channel_total.index if channel_total[c] > min_spend * 12]

    # Known non-paid/weak signals to exclude
    excluded = {"organic_search", "direct", "referral"}
    paid_channels = [c for c in paid_channels if c not in excluded]

    # Pivot to wide format
    spend_wide = monthly.pivot_table(
        index="month", columns="channel", values="spend", aggfunc="sum", fill_value=0
    )[paid_channels]
    # Total revenue per month (across all channels — model learns paid contribution)
    revenue_monthly = monthly.groupby("month")["revenue"].sum().reindex(spend_wide.index).fillna(0)

    return {
        "dates": [d.date() for d in spend_wide.index],
        "channels": paid_channels,
        "spend": spend_wide.values.astype(float),
        "revenue": revenue_monthly.values.astype(float),
        "channel_spend_scale": spend_wide.mean(axis=0).values.astype(float),
    }


# ----------------------------------------------------------------------------
# PyMC model — imported lazily so the module loads without PyMC installed
# ----------------------------------------------------------------------------

def build_and_fit(
    data: dict,
    draws: int = 1000,
    tune: int = 1000,
    chains: int = 2,
    cores: int = 2,
    target_accept: float = 0.95,
    seed: int = 42,
) -> "arviz.InferenceData":
    """Build the PyMC model and fit. Returns InferenceData (posterior samples).

    This is the slow step — 10-30 min on 60 months × 9 channels.
    """
    import pymc as pm
    import arviz as az

    channels = data["channels"]
    spend = data["spend"]                  # (T, C)
    revenue = data["revenue"]              # (T,)
    scale = data["channel_spend_scale"]    # (C,)
    T, C = spend.shape

    rev_mean = float(np.mean(revenue))
    rev_sd = float(np.std(revenue) + 1e-6)

    # Time index for linear trend
    t_idx = np.arange(T, dtype=float) / T  # scaled to [0, ~1]
    # Monthly seasonality dummies (Fourier)
    month_of_year = np.array([d.month for d in data["dates"]])
    fourier_sin = np.sin(2 * np.pi * month_of_year / 12)
    fourier_cos = np.cos(2 * np.pi * month_of_year / 12)

    with pm.Model() as model:
        # ---- Priors --------------------------------------------------------
        alpha = pm.Beta("alpha", alpha=2.0, beta=2.0, shape=C)
        K = pm.LogNormal("K", mu=np.log(np.maximum(scale, 1.0)), sigma=1.0, shape=C)
        hill_shape = pm.TruncatedNormal("hill_shape", mu=1.0, sigma=0.5, lower=0.3, upper=3.0)
        beta = pm.HalfNormal("beta", sigma=rev_sd, shape=C)

        intercept = pm.Normal("intercept", mu=rev_mean, sigma=rev_sd / 2)
        trend_coef = pm.Normal("trend_coef", mu=0, sigma=rev_sd)
        season_sin_coef = pm.Normal("season_sin", mu=0, sigma=rev_sd / 2)
        season_cos_coef = pm.Normal("season_cos", mu=0, sigma=rev_sd / 2)
        sigma_obs = pm.HalfNormal("sigma_obs", sigma=rev_sd / 2)

        # ---- Adstock via matrix multiplication ----------------------------
        # Build adstock weights matrix W of shape (T, T) per channel where
        # W[t, s] = kernel[t-s] if 0 <= t-s <= lag_max else 0
        # Adstocked = W @ spend_c for each channel c.
        import pytensor.tensor as pt

        lag_max = 6  # 6-month memory
        # Build lag indices matrix: lag_idx[t, s] = t - s, clamped to [-1, lag_max]
        # If lag is outside [0, lag_max] we want zero weight.
        t_grid = np.arange(T)
        lag_grid = t_grid[:, None] - t_grid[None, :]  # (T, T), each entry = t - s
        # Mask of valid lags
        valid = (lag_grid >= 0) & (lag_grid <= lag_max)
        lag_grid_clipped = np.clip(lag_grid, 0, lag_max)

        # For each channel, kernel[l] = alpha^l / sum_k alpha^k for k=0..lag_max
        # We compute kernel as a PyTensor op
        lag_range = pt.arange(lag_max + 1).astype("float64")  # (lag_max+1,)
        # kernel[l, c] = alpha[c]^l
        alpha_exp = alpha[None, :] ** lag_range[:, None]  # (lag_max+1, C)
        kernel = alpha_exp / alpha_exp.sum(axis=0, keepdims=True)  # normalize per channel

        # For each channel c, compute adstocked[t, c] = sum_s W_c[t, s] * spend[s, c]
        # where W_c[t, s] = kernel[t-s, c] if valid[t, s] else 0
        # Build W_c as (T, T) for each channel: index kernel by lag_grid_clipped then mask
        # kernel[lag_grid_clipped, c] gives (T, T, C)? Too big. Instead, loop over channels
        # but as a scan, which PyTensor handles well.

        adstocked_channels = []
        valid_tensor = pt.as_tensor(valid.astype(float))  # (T, T)
        for c in range(C):
            # kernel_c indexed by lag_grid_clipped
            k_c = kernel[:, c]  # (lag_max+1,)
            # W[t, s] = k_c[lag_grid_clipped[t, s]] * valid[t, s]
            W = k_c[lag_grid_clipped] * valid_tensor  # (T, T)
            spend_c = pt.as_tensor(spend[:, c])  # (T,)
            adstocked_c = pt.dot(W, spend_c)  # (T,)
            adstocked_channels.append(adstocked_c)
        adstocked = pt.stack(adstocked_channels, axis=1)  # (T, C)

        # ---- Hill saturation -----------------------------------------------
        adstocked_safe = pt.maximum(adstocked, 1e-9)
        saturated = adstocked_safe ** hill_shape / (
            adstocked_safe ** hill_shape + K[None, :] ** hill_shape
        )

        # Contribution per channel
        contributions = saturated * beta[None, :]  # (T, C)
        channel_total = contributions.sum(axis=1)  # (T,)

        # Trend + seasonality
        t_idx_tensor = pt.as_tensor(t_idx)
        trend = trend_coef * t_idx_tensor
        seasonality = season_sin_coef * pt.as_tensor(fourier_sin) + season_cos_coef * pt.as_tensor(fourier_cos)

        mu = intercept + channel_total + trend + seasonality

        pm.Normal("y_obs", mu=mu, sigma=sigma_obs, observed=revenue)

        idata = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            cores=cores,
            target_accept=target_accept,
            random_seed=seed,
            return_inferencedata=True,
            progressbar=True,
        )

    return idata


def save_posterior(idata, channels: list[str], artifact_dir: Path) -> dict:
    """Extract posterior point estimates + save artifact.

    We save:
        - mmm_posterior.nc   (full InferenceData via arviz)
        - mmm_summary.json   (posterior means + 90% CI per channel)

    The summary JSON is what the API serves; the full posterior is kept for diagnostics
    and what-if re-sampling.
    """
    import arviz as az

    artifact_dir.mkdir(parents=True, exist_ok=True)
    idata.to_netcdf(str(artifact_dir / "mmm_posterior.nc"))

    # Extract posterior per-channel summaries
    post = idata.posterior
    summary = {"channels": channels, "per_channel": {}}

    alpha_mean = post["alpha"].mean(dim=["chain", "draw"]).values
    alpha_lo = post["alpha"].quantile(0.05, dim=["chain", "draw"]).values
    alpha_hi = post["alpha"].quantile(0.95, dim=["chain", "draw"]).values

    K_mean = post["K"].mean(dim=["chain", "draw"]).values
    K_lo = post["K"].quantile(0.05, dim=["chain", "draw"]).values
    K_hi = post["K"].quantile(0.95, dim=["chain", "draw"]).values

    beta_mean = post["beta"].mean(dim=["chain", "draw"]).values
    beta_lo = post["beta"].quantile(0.05, dim=["chain", "draw"]).values
    beta_hi = post["beta"].quantile(0.95, dim=["chain", "draw"]).values

    shape_mean = float(post["hill_shape"].mean().values)

    for i, ch in enumerate(channels):
        summary["per_channel"][ch] = {
            "alpha": {"mean": float(alpha_mean[i]), "lo": float(alpha_lo[i]), "hi": float(alpha_hi[i])},
            "K": {"mean": float(K_mean[i]), "lo": float(K_lo[i]), "hi": float(K_hi[i])},
            "beta": {"mean": float(beta_mean[i]), "lo": float(beta_lo[i]), "hi": float(beta_hi[i])},
        }

    summary["hill_shape"] = shape_mean
    summary["intercept"] = float(post["intercept"].mean().values)
    summary["sigma_obs"] = float(post["sigma_obs"].mean().values)

    # R-hat diagnostic (convergence indicator)
    rhat = az.rhat(idata)
    max_rhat = float(max(
        rhat["alpha"].max().values, rhat["K"].max().values,
        rhat["beta"].max().values, rhat["hill_shape"].max().values,
    ))
    summary["diagnostics"] = {
        "max_rhat": max_rhat,
        "converged": max_rhat < 1.05,
        "n_draws": int(post.sizes["draw"]),
        "n_chains": int(post.sizes["chain"]),
    }

    with open(artifact_dir / "mmm_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def load_posterior_summary(artifact_dir: Path) -> Optional[dict]:
    """Load cached summary JSON. Fast, no PyMC import needed."""
    p = artifact_dir / "mmm_summary.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)
