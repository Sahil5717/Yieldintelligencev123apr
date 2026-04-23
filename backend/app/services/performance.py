"""Performance service — assembles the channel-level diagnostic payload (Screen 03).

Pulls current state + MMM response curves + attribution to build the diagnostic view.
"""
from __future__ import annotations
from datetime import date
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.campaign import CampaignPerformance
from app.mmm.model import load_posterior_summary
from app.mmm.transforms import response_curve
from app.optimizer.portfolio import current_state
from app.core.config import settings


def _latest_lookback(db: Session, months: int = 3) -> tuple[date, date]:
    latest = db.execute(select(func.max(CampaignPerformance.date))).scalar_one()
    y, m = latest.year, latest.month
    for _ in range(months - 1):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return date(y, m, 1), latest


def build_performance(db: Session, workspace: str) -> dict:
    """Channel performance diagnostic: Pareto, frontier, per-channel stats."""
    summary = load_posterior_summary(settings.artifacts_dir)
    if not summary:
        return {"error": "MMM not yet fit — run scripts/fit_mmm.py --synthetic"}

    start, end = _latest_lookback(db, 3)

    # Aggregate spend + revenue per channel over lookback
    rows = db.execute(
        select(
            CampaignPerformance.channel,
            func.sum(CampaignPerformance.spend),
            func.sum(CampaignPerformance.revenue),
            func.count(func.distinct(CampaignPerformance.campaign)),
        )
        .where(CampaignPerformance.date >= start, CampaignPerformance.date <= end)
        .group_by(CampaignPerformance.channel)
    ).all()

    channels_data = {}
    total_spend = 0.0
    total_revenue = 0.0
    for ch, sp, rev, camps in rows:
        sp, rev = float(sp or 0), float(rev or 0)
        channels_data[ch] = {
            "spend": sp,
            "revenue": rev,
            "roi": rev / sp if sp else 0,
            "campaigns": int(camps),
        }
        total_spend += sp
        total_revenue += rev

    # Current state from MMM + marginal ROIs
    mmm_channels = summary["channels"]
    monthly_spend = {ch: channels_data.get(ch, {}).get("spend", 0) / 3 for ch in mmm_channels}
    cs = current_state(mmm_channels, monthly_spend, summary)

    # Pareto rank by revenue contribution
    ranked = sorted(channels_data.items(), key=lambda kv: -kv[1]["revenue"])
    cum_rev = 0
    pareto = []
    for ch, data in ranked:
        cum_rev += data["revenue"]
        pareto.append({
            "channel": ch,
            "revenue": data["revenue"],
            "spend": data["spend"],
            "roi": data["roi"],
            "revenue_share": data["revenue"] / total_revenue if total_revenue else 0,
            "cumulative_share": cum_rev / total_revenue if total_revenue else 0,
            "campaigns": data["campaigns"],
        })

    # Efficient frontier: classify channels by marginal ROI
    # mROI < 1: losing money
    # 1 <= mROI < 1.3: past peak / saturated
    # 1.3 <= mROI < 2: on frontier
    # mROI >= 2: headroom
    frontier_status = {}
    for ch in mmm_channels:
        m = cs["marginal_roi"].get(ch, 0)
        if m < 1.0:
            status = "losing_money"
        elif m < 1.3:
            status = "past_peak"
        elif m < 2.0:
            status = "on_frontier"
        else:
            status = "headroom"
        frontier_status[ch] = {
            "marginal_roi": m,
            "status": status,
            "monthly_spend": monthly_spend.get(ch, 0),
        }

    # Response curves for each MMM channel (for charts)
    curves = {}
    for ch in mmm_channels:
        p = summary["per_channel"][ch]
        spends, resp, marg = response_curve(
            half_sat=p["K"]["mean"],
            shape=summary.get("hill_shape", 1.0),
            scale=p["beta"]["mean"],
            alpha=p["alpha"]["mean"],
            n_points=30,
            max_spend=max(monthly_spend.get(ch, 0) * 2.5, p["K"]["mean"] * 3),
        )
        curves[ch] = {
            "spend": spends.tolist(),
            "response": resp.tolist(),
            "marginal_roi": marg.tolist(),
            "current_spend": monthly_spend.get(ch, 0),
        }

    return {
        "workspace": workspace,
        "period": {"start": start.isoformat(), "end": end.isoformat(), "months": 3},
        "totals": {
            "spend": total_spend,
            "revenue": total_revenue,
            "roi": total_revenue / total_spend if total_spend else 0,
            "channels_analyzed": len(channels_data),
        },
        "pareto": pareto,
        "frontier_status": frontier_status,
        "response_curves": curves,
        "mmm_method": summary["diagnostics"].get("method", "bayesian_pymc"),
    }
