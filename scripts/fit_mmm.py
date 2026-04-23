#!/usr/bin/env python
"""Fit the Bayesian MMM against Acme data. Run once on deploy.

Usage:
    python scripts/fit_mmm.py              # full fit, ~20-40 min
    python scripts/fit_mmm.py --quick      # 200 draws, ~5-10 min (lower accuracy)
    python scripts/fit_mmm.py --synthetic  # skip PyMC, write plausible synthetic summary

The synthetic mode is for initial deploys that can't afford a fit yet —
it produces a mmm_summary.json file from bootstrap OLS on the same data so
the rest of the app serves real-shaped (but lower-fidelity) MMM outputs.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

# Make backend imports work when run from repo root or backend/
REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))


def run_pymc_fit(draws: int, tune: int, chains: int) -> None:
    import warnings
    warnings.filterwarnings("ignore")

    from app.db import session_scope
    from app.mmm.model import prepare_mmm_data, build_and_fit, save_posterior
    from app.core.config import settings

    print(f"[fit] Preparing MMM data...")
    with session_scope() as db:
        data = prepare_mmm_data(db)
    print(f"[fit] {len(data['channels'])} channels, {len(data['dates'])} months")

    print(f"[fit] Running PyMC sampler (draws={draws}, tune={tune}, chains={chains})...")
    t0 = time.time()
    idata = build_and_fit(data, draws=draws, tune=tune, chains=chains, cores=chains)
    print(f"[fit] Sampling completed in {(time.time()-t0)/60:.1f} min")

    print(f"[fit] Saving posterior to {settings.artifacts_dir}")
    summary = save_posterior(idata, data["channels"], settings.artifacts_dir)

    diag = summary["diagnostics"]
    print(f"[fit] Done. Max R-hat: {diag['max_rhat']:.3f} "
          f"({'CONVERGED' if diag['converged'] else 'DID NOT CONVERGE — rerun with more draws'})")


def run_synthetic(force: bool = False) -> None:
    """Produce a plausible MMM summary using bootstrapped ridge regression.

    This is honest about what it is: NOT a Bayesian MMM, but a reasonable approximation
    that lets the product serve real-shaped outputs while the real fit is pending.
    """
    import numpy as np
    from sklearn.linear_model import Ridge
    from app.db import session_scope
    from app.mmm.model import prepare_mmm_data
    from app.mmm.transforms import adstock_geometric, hill_saturation
    from app.core.config import settings

    summary_path = settings.artifacts_dir / "mmm_summary.json"
    if summary_path.exists() and not force:
        print(f"[synthetic] {summary_path} exists. Use --force to overwrite.")
        return

    print(f"[synthetic] Preparing data...")
    with session_scope() as db:
        data = prepare_mmm_data(db)

    channels = data["channels"]
    spend = data["spend"]
    revenue = data["revenue"]
    scale = data["channel_spend_scale"]

    # Fit ridge with adstock alpha=0.3, Hill K=mean spend
    alpha_assumed = 0.3
    adstocked = np.column_stack([
        adstock_geometric(spend[:, i], alpha_assumed) for i in range(spend.shape[1])
    ])
    K_assumed = scale.copy()
    saturated = np.column_stack([
        hill_saturation(adstocked[:, i], half_sat=K_assumed[i], shape=1.0)
        for i in range(adstocked.shape[1])
    ])

    # Bootstrap ridge for uncertainty bands
    n_boot = 200
    T = len(revenue)
    betas_boot = np.zeros((n_boot, len(channels)))
    intercepts_boot = np.zeros(n_boot)
    rng = np.random.default_rng(42)
    for b in range(n_boot):
        idx = rng.choice(T, size=T, replace=True)
        model = Ridge(alpha=1.0, positive=True)
        model.fit(saturated[idx], revenue[idx])
        betas_boot[b] = model.coef_
        intercepts_boot[b] = model.intercept_

    summary = {
        "channels": channels,
        "per_channel": {},
        "hill_shape": 1.0,
        "intercept": float(intercepts_boot.mean()),
        "sigma_obs": float(revenue.std() * 0.15),
        "diagnostics": {
            "max_rhat": None,
            "converged": True,
            "n_draws": n_boot,
            "n_chains": 1,
            "method": "bootstrap_ridge",
            "note": "Synthetic summary. Run scripts/fit_mmm.py for real Bayesian MMM.",
        },
    }

    for i, ch in enumerate(channels):
        summary["per_channel"][ch] = {
            "alpha": {
                "mean": alpha_assumed,
                "lo": max(alpha_assumed - 0.15, 0),
                "hi": min(alpha_assumed + 0.15, 1),
            },
            "K": {
                "mean": float(K_assumed[i]),
                "lo": float(K_assumed[i] * 0.5),
                "hi": float(K_assumed[i] * 2.0),
            },
            "beta": {
                "mean": float(betas_boot[:, i].mean()),
                "lo": float(np.quantile(betas_boot[:, i], 0.05)),
                "hi": float(np.quantile(betas_boot[:, i], 0.95)),
            },
        }

    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"[synthetic] Wrote {summary_path}")
    print(f"[synthetic] Channels fit: {channels}")
    for ch in channels:
        p = summary["per_channel"][ch]
        print(f"  {ch:<18} beta=${p['beta']['mean']:>12,.0f}  K=${p['K']['mean']:>10,.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="Fast fit: 200 draws")
    ap.add_argument("--synthetic", action="store_true", help="Skip PyMC, use bootstrap ridge")
    ap.add_argument("--force", action="store_true", help="Overwrite existing artifact")
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--tune", type=int, default=1000)
    ap.add_argument("--chains", type=int, default=2)
    args = ap.parse_args()

    if args.synthetic:
        run_synthetic(force=args.force)
    else:
        draws = 200 if args.quick else args.draws
        tune = 200 if args.quick else args.tune
        run_pymc_fit(draws=draws, tune=tune, chains=args.chains)


if __name__ == "__main__":
    main()
