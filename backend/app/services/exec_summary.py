"""Exec Summary service — assembles the top-level dashboard payload."""
from __future__ import annotations
from datetime import date, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.schemas import ExecSummary, PillarSummary
from app.models.campaign import CampaignPerformance
from app.models.event import MarketEvent
from app.models.opportunity import DetectedOpportunity, OpportunityTemplate


PILLAR_LABELS = {
    "revenue": "Revenue uplift",
    "cost": "Cost efficiency",
    "cx": "Customer experience",
    "risk": "Risk & resilience",
}


def _kpis(db: Session) -> dict:
    """Compute current KPIs: last 3 months vs prior 3 months for deltas."""
    latest = db.execute(select(func.max(CampaignPerformance.date))).scalar_one()
    if latest is None:
        return {}

    def _window(end_date, months):
        y, m = end_date.year, end_date.month
        for _ in range(months - 1):
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        return date(y, m, 1)

    current_start = _window(latest, 3)
    prior_end = current_start - timedelta(days=1)
    prior_start = _window(prior_end, 3)

    def _agg(start, end):
        row = db.execute(
            select(
                func.sum(CampaignPerformance.spend),
                func.sum(CampaignPerformance.revenue),
                func.sum(CampaignPerformance.conversions),
            ).where(CampaignPerformance.date >= start, CampaignPerformance.date <= end)
        ).one()
        spend = float(row[0] or 0)
        revenue = float(row[1] or 0)
        conv = int(row[2] or 0)
        return {
            "spend": spend,
            "revenue": revenue,
            "conversions": conv,
            "roi": revenue / spend if spend else 0.0,
            "cac": spend / conv if conv else 0.0,
        }

    curr = _agg(current_start, latest)
    prior = _agg(prior_start, prior_end)

    def _delta(c, p):
        return ((c - p) / p * 100) if p else 0.0

    return {
        "revenue": round(curr["revenue"], 0),
        "revenue_delta_pct": round(_delta(curr["revenue"], prior["revenue"]), 1),
        "spend": round(curr["spend"], 0),
        "spend_delta_pct": round(_delta(curr["spend"], prior["spend"]), 1),
        "roi": round(curr["roi"], 2),
        "roi_delta": round(curr["roi"] - prior["roi"], 2),
        "cac": round(curr["cac"], 0),
        "cac_delta_pct": round(_delta(curr["cac"], prior["cac"]), 1),
        "as_of": latest.isoformat(),
        "period_months": 3,
    }


def _market_trends(db: Session, limit: int = 6) -> list[dict]:
    """Upcoming market events + key signals, closest-first."""
    latest = db.execute(select(func.max(CampaignPerformance.date))).scalar_one()
    if latest is None:
        return []
    horizon = latest + timedelta(days=180)
    events = db.execute(
        select(MarketEvent)
        .where(MarketEvent.event_date >= latest, MarketEvent.event_date <= horizon)
        .order_by(MarketEvent.event_date)
        .limit(limit)
    ).scalars().all()

    out = []
    for e in events:
        weeks = (e.event_date - latest).days // 7
        out.append({
            "name": e.event_name,
            "weeks_out": weeks,
            "impact_pct": e.impact_pct,
            "direction": e.impact_direction or "neutral",
            "when": f"In {weeks} weeks · {e.event_type.replace('_', ' ')}" if weeks > 0 else e.event_type,
        })
    # Always include Cookieless signal as a standing risk marker
    if len(out) < limit:
        out.append({
            "name": "Cookieless deadline",
            "weeks_out": None,
            "impact_pct": None,
            "direction": "warning",
            "when": "Q4 2026 · act now",
        })
    return out


def _pillar_rollups(db: Session, workspace: str) -> tuple[list[PillarSummary], float, float, int, int, int]:
    """Aggregate detected opportunities into pillar summaries + top-line totals."""
    # Join detected with template to get pillar + motion
    rows = db.execute(
        select(
            OpportunityTemplate.pillar,
            OpportunityTemplate.motion,
            DetectedOpportunity.modeled_impact,
        )
        .join(OpportunityTemplate, DetectedOpportunity.catalog_id == OpportunityTemplate.catalog_id)
        .where(DetectedOpportunity.workspace == workspace)
    ).all()

    # Pillars we surface on Exec Summary (risk is hidden per v4 lock)
    surfaced_pillars = ["revenue", "cost", "cx"]
    buckets: dict[str, dict] = {
        p: {"total": 0.0, "action_count": 0, "opt_count": 0, "opt_total": 0.0, "trans_count": 0, "trans_total": 0.0}
        for p in surfaced_pillars
    }

    for pillar, motion, impact in rows:
        if pillar not in surfaced_pillars:
            continue
        b = buckets[pillar]
        b["total"] += impact or 0
        b["action_count"] += 1
        if motion == "optimization":
            b["opt_count"] += 1
            b["opt_total"] += impact or 0
        else:
            b["trans_count"] += 1
            b["trans_total"] += impact or 0

    pillars = [
        PillarSummary(
            pillar=p,
            label=PILLAR_LABELS[p],
            total_impact=round(b["total"], 0),
            action_count=b["action_count"],
            optimization_count=b["opt_count"],
            optimization_total=round(b["opt_total"], 0),
            transformation_count=b["trans_count"],
            transformation_total=round(b["trans_total"], 0),
        )
        for p, b in buckets.items()
    ]

    total_on_table = sum(p.total_impact for p in pillars)
    optimization_total = sum(p.optimization_total for p in pillars)
    transformation_total = sum(p.transformation_total for p in pillars)
    opt_count = sum(p.optimization_count for p in pillars)
    trans_count = sum(p.transformation_count for p in pillars)

    return pillars, total_on_table, optimization_total, transformation_total, opt_count, trans_count


def _model_confidence(db: Session, workspace: str) -> float:
    """Average confidence across detected opps, weighted by impact."""
    rows = db.execute(
        select(DetectedOpportunity.modeled_impact, DetectedOpportunity.confidence_score)
        .where(DetectedOpportunity.workspace == workspace)
    ).all()
    if not rows:
        return 0.0
    num = sum((i or 0) * (c or 0) for i, c in rows)
    den = sum((i or 0) for i, _ in rows)
    return round(num / den, 2) if den else 0.0


def build_exec_summary(db: Session, workspace: str) -> ExecSummary:
    pillars, total, opt_total, trans_total, opt_n, trans_n = _pillar_rollups(db, workspace)
    detected_count = db.execute(
        select(func.count()).select_from(DetectedOpportunity).where(DetectedOpportunity.workspace == workspace)
    ).scalar_one()

    return ExecSummary(
        workspace=workspace,
        as_of=db.execute(select(func.max(CampaignPerformance.date))).scalar_one().isoformat(),
        total_on_table=total,
        optimization_total=opt_total,
        transformation_total=trans_total,
        optimization_action_count=opt_n,
        transformation_action_count=trans_n,
        pillars=pillars,
        kpis=_kpis(db),
        market_trends=_market_trends(db),
        model_confidence=_model_confidence(db, workspace),
        detected_count=detected_count,
    )
