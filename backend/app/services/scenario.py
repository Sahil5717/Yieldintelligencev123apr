"""Scenario composer — selected actions + their simulated portfolio impact.

A scenario is:
    - a set of selected actions (from detected opportunities)
    - a baseline (current state snapshot)
    - projected state (baseline + sum of action impacts, tempered by confidence)
    - optional per-action user overrides
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.scenario import Scenario, ScenarioAction
from app.models.action import Action
from app.models.campaign import CampaignPerformance
from app.models.override import ActionOverride
from app.models.opportunity import DetectedOpportunity


def _baseline_kpis(db: Session) -> dict:
    """Annualized revenue/spend/ROI/CAC from the most recent 12 months."""
    latest = db.execute(select(func.max(CampaignPerformance.date))).scalar_one()
    from datetime import date
    y, m = latest.year, latest.month - 11
    while m <= 0:
        y -= 1
        m += 12
    start = date(y, m, 1)

    row = db.execute(
        select(
            func.sum(CampaignPerformance.spend),
            func.sum(CampaignPerformance.revenue),
            func.sum(CampaignPerformance.conversions),
        ).where(CampaignPerformance.date >= start, CampaignPerformance.date <= latest)
    ).one()
    spend = float(row[0] or 0)
    revenue = float(row[1] or 0)
    conv = int(row[2] or 0)
    return {
        "revenue": revenue,
        "spend": spend,
        "roi": revenue / spend if spend else 0,
        "cac": spend / conv if conv else 0,
        "conversions": conv,
    }


def _effective_action(db: Session, action: Action, workspace: str) -> dict:
    """Get action with any active override applied."""
    override = db.execute(
        select(ActionOverride)
        .where(
            ActionOverride.action_id == action.id,
            ActionOverride.active == "Y",
            ActionOverride.workspace == workspace,
        )
        .order_by(ActionOverride.created_at.desc())
    ).scalars().first()

    impact = override.impact_override if override and override.impact_override else action.modeled_impact
    confidence = override.confidence_override if override and override.confidence_override else action.confidence
    ramp = override.ramp_months_override if override and override.ramp_months_override else action.ramp_months

    return {
        "action_id": action.id,
        "name": action.name,
        "pillar": action.pillar,
        "motion": action.motion,
        "modeled_impact": action.modeled_impact,
        "confidence": action.confidence,
        "ramp_months": action.ramp_months,
        "effective_impact": impact,
        "effective_confidence": confidence,
        "effective_ramp_months": ramp,
        "has_override": override is not None,
        "override_reason": override.reason if override else None,
    }


def project_scenario(db: Session, scenario_id: int, workspace: str) -> dict:
    """Compute projected KPIs for a scenario given its selected actions."""
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        return {"error": "scenario not found"}

    # Baseline
    baseline = _baseline_kpis(db)
    if scenario.baseline_revenue is None:
        scenario.baseline_revenue = baseline["revenue"]
        scenario.baseline_spend = baseline["spend"]
        scenario.baseline_roi = baseline["roi"]
        scenario.baseline_cac = baseline["cac"]

    # Sum action impacts weighted by confidence
    action_ids = db.execute(
        select(ScenarioAction.action_id).where(ScenarioAction.scenario_id == scenario_id)
    ).scalars().all()

    incremental_revenue = 0.0
    cost_savings = 0.0
    confidence_weighted = 0.0
    total_weight = 0.0

    details = []
    for aid in action_ids:
        action = db.get(Action, aid)
        if action is None:
            continue
        eff = _effective_action(db, action, workspace)
        impact = eff["effective_impact"]
        conf = eff["effective_confidence"]

        # Revenue pillar = incremental revenue. Cost pillar = savings (reduces spend).
        if action.pillar == "cost":
            cost_savings += impact * conf  # confidence-adjusted
        else:
            incremental_revenue += impact * conf

        confidence_weighted += conf * abs(impact)
        total_weight += abs(impact)
        details.append(eff)

    projected_revenue = baseline["revenue"] + incremental_revenue
    projected_spend = baseline["spend"] - cost_savings  # savings reduce spend

    projected_roi = projected_revenue / projected_spend if projected_spend > 0 else 0
    # CAC scales roughly inversely with CVR improvements; approximate
    projected_cac = projected_spend / baseline["conversions"] if baseline["conversions"] else 0

    portfolio_confidence = confidence_weighted / total_weight if total_weight else 0

    # Persist projection back to scenario
    scenario.projected_revenue = projected_revenue
    scenario.projected_spend = projected_spend
    scenario.projected_roi = projected_roi
    scenario.projected_cac = projected_cac
    scenario.incremental_revenue = incremental_revenue
    scenario.portfolio_confidence = portfolio_confidence
    db.commit()

    return {
        "scenario_id": scenario_id,
        "name": scenario.name,
        "status": scenario.status,
        "baseline": baseline,
        "projected": {
            "revenue": projected_revenue,
            "spend": projected_spend,
            "roi": projected_roi,
            "cac": projected_cac,
        },
        "deltas": {
            "revenue_abs": incremental_revenue,
            "revenue_pct": incremental_revenue / baseline["revenue"] * 100 if baseline["revenue"] else 0,
            "cost_savings_abs": cost_savings,
            "roi_delta": projected_roi - baseline["roi"],
            "cac_delta_abs": projected_cac - baseline["cac"],
        },
        "portfolio_confidence": portfolio_confidence,
        "action_count": len(details),
        "actions": details,
    }


def materialize_actions(db: Session, workspace: str) -> int:
    """Create Action rows from DetectedOpportunity rows if not yet materialized.

    Each detected opportunity becomes 1 action. This gives us stable IDs for overrides
    and scenarios.
    """
    from app.models.opportunity import OpportunityTemplate

    existing = set(
        db.execute(
            select(Action.detected_opp_id).where(Action.workspace == workspace)
        ).scalars().all()
    )

    detected = db.execute(
        select(DetectedOpportunity, OpportunityTemplate)
        .join(OpportunityTemplate, DetectedOpportunity.catalog_id == OpportunityTemplate.catalog_id)
        .where(DetectedOpportunity.workspace == workspace)
    ).all()

    added = 0
    ramp_map = {"Days": 0, "Weeks": 1, "Months": 3, "Quarters": 6}
    for det, tmpl in detected:
        if det.id in existing:
            continue
        db.add(Action(
            workspace=workspace,
            detected_opp_id=det.id,
            action_key=f"{tmpl.catalog_id}-1",
            name=tmpl.name,
            description=tmpl.description,
            effect_type="composite",
            pillar=tmpl.pillar,
            motion=tmpl.motion,
            modeled_impact=det.modeled_impact or 0,
            confidence=det.confidence_score or 0.5,
            ramp_months=ramp_map.get(tmpl.timeline, 3),
            timeline=tmpl.timeline,
            reversibility=tmpl.reversibility,
            decision_audience=tmpl.decision_audience,
        ))
        added += 1

    db.commit()
    return added
