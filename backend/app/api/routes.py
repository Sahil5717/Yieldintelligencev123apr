"""API routes — the public interface of the backend."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import date
import json

from app.db import get_db
from app.core.config import settings
from app.services.exec_summary import build_exec_summary
from app.services.data_loader import seed_all
from app.services.performance import build_performance
from app.triggers.engine import run_detection, RULES
from app.models.opportunity import DetectedOpportunity, OpportunityTemplate
from app.models.campaign import CampaignPerformance
from app.api.schemas import DetectedOpportunityOut, LibraryItemOut
from app.mmm.model import load_posterior_summary
from app.optimizer.portfolio import optimize_allocation, current_state
from app.attribution.markov import markov_attribution
from app.attribution.shapley import shapley_attribution

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@router.post("/admin/seed")
def seed_endpoint(db: Session = Depends(get_db)):
    """Idempotent seed — safe to call repeatedly."""
    return seed_all(db)


@router.post("/admin/detect")
def detect_endpoint(workspace: str = None, db: Session = Depends(get_db)):
    """Run the trigger engine against current data and persist results."""
    from app.services.scenario import materialize_actions

    ws = workspace or settings.default_workspace
    result = run_detection(db, ws)
    added = materialize_actions(db, ws)
    result["actions_materialized"] = added
    return result


@router.get("/v1/exec-summary")
def exec_summary(workspace: str = None, db: Session = Depends(get_db)):
    ws = workspace or settings.default_workspace
    return build_exec_summary(db, ws)


@router.get("/v1/opportunities", response_model=list[DetectedOpportunityOut])
def list_opportunities(
    pillar: str | None = None,
    motion: str | None = None,
    workspace: str | None = None,
    db: Session = Depends(get_db),
):
    ws = workspace or settings.default_workspace

    q = (
        select(
            DetectedOpportunity,
            OpportunityTemplate.name,
            OpportunityTemplate.pillar,
            OpportunityTemplate.motion,
        )
        .join(OpportunityTemplate, DetectedOpportunity.catalog_id == OpportunityTemplate.catalog_id)
        .where(DetectedOpportunity.workspace == ws)
    )
    if pillar:
        q = q.where(OpportunityTemplate.pillar == pillar)
    if motion:
        q = q.where(OpportunityTemplate.motion == motion)
    q = q.order_by(DetectedOpportunity.modeled_impact.desc())

    rows = db.execute(q).all()
    out: list[DetectedOpportunityOut] = []
    for det, name, p, m in rows:
        evidence = json.loads(det.evidence_json) if det.evidence_json else []
        refs = det.external_signal_refs.split(",") if det.external_signal_refs else []
        out.append(DetectedOpportunityOut(
            catalog_id=det.catalog_id,
            name=name,
            pillar=p,
            motion=m,
            modeled_impact=det.modeled_impact or 0,
            low_estimate=det.low_estimate,
            high_estimate=det.high_estimate,
            confidence=det.confidence_score or 0,
            rationale=det.rationale or "",
            evidence=evidence,
            external_boost=det.external_boost or 1.0,
            external_signal_refs=refs,
            source=det.source,
        ))
    return out


@router.get("/v1/library", response_model=list[LibraryItemOut])
def library(
    not_triggered_only: bool = False,
    pillar: str | None = None,
    motion: str | None = None,
    db: Session = Depends(get_db),
    workspace: str | None = None,
):
    """The 94 catalog items with trigger status for this workspace."""
    ws = workspace or settings.default_workspace

    # Which catalog items fired for this workspace
    fired_ids = set(db.execute(
        select(DetectedOpportunity.catalog_id).where(DetectedOpportunity.workspace == ws)
    ).scalars().all())

    q = select(OpportunityTemplate)
    if pillar:
        q = q.where(OpportunityTemplate.pillar == pillar)
    if motion:
        q = q.where(OpportunityTemplate.motion == motion)
    rows = db.execute(q).scalars().all()

    out = []
    for t in rows:
        has_rule = t.catalog_id in RULES
        fired = t.catalog_id in fired_ids if has_rule else None
        if not_triggered_only and fired:
            continue
        out.append(LibraryItemOut(
            catalog_id=t.catalog_id,
            name=t.name,
            category=t.category,
            subcategory=t.subcategory,
            description=t.description,
            pillar=t.pillar,
            motion=t.motion,
            magnitude_low=t.magnitude_low,
            magnitude_high=t.magnitude_high,
            confidence=t.confidence,
            timeline=t.timeline,
            reversibility=t.reversibility,
            trigger_conditions=t.trigger_conditions,
            has_rule=has_rule,
            fired=fired,
        ))
    return out


@router.get("/v1/performance")
def performance(workspace: str | None = None, db: Session = Depends(get_db)):
    """Screen 03 — channel-level diagnostic view."""
    ws = workspace or settings.default_workspace
    return build_performance(db, ws)


@router.get("/v1/attribution/markov")
def attribution_markov(db: Session = Depends(get_db)):
    """Markov chain attribution — credit per channel."""
    return markov_attribution(db)


@router.get("/v1/attribution/shapley")
def attribution_shapley(max_channels: int = 8, db: Session = Depends(get_db)):
    """Shapley-value attribution — credit per channel."""
    return shapley_attribution(db, max_channels=max_channels)


@router.get("/v1/mmm/summary")
def mmm_summary():
    """Load current MMM posterior summary."""
    s = load_posterior_summary(settings.artifacts_dir)
    if not s:
        raise HTTPException(404, "MMM not yet fit. Run scripts/fit_mmm.py --synthetic")
    return s


class OptimizeRequest(BaseModel):
    total_budget: float | None = None
    min_spend_pct: float = 0.25
    max_spend_pct: float = 2.5
    locked_channels: dict[str, float] | None = None
    workspace: str | None = None


@router.post("/v1/optimize")
def optimize(req: OptimizeRequest, db: Session = Depends(get_db)):
    """Run portfolio optimization.

    Uses current monthly spend as baseline, MMM summary for response curves.
    """
    summary = load_posterior_summary(settings.artifacts_dir)
    if not summary:
        raise HTTPException(404, "MMM not yet fit")

    # Compute current monthly spend from last 3 months
    latest = db.execute(select(func.max(CampaignPerformance.date))).scalar_one()
    y, m = latest.year, latest.month
    for _ in range(2):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    start = date(y, m, 1)

    rows = db.execute(
        select(CampaignPerformance.channel, func.sum(CampaignPerformance.spend))
        .where(CampaignPerformance.date >= start)
        .group_by(CampaignPerformance.channel)
    ).all()
    current = {ch: float(s) / 3 for ch, s in rows}

    return optimize_allocation(
        channels=summary["channels"],
        current_spend=current,
        mmm_summary=summary,
        total_budget=req.total_budget,
        min_spend_pct=req.min_spend_pct,
        max_spend_pct=req.max_spend_pct,
        locked_channels=req.locked_channels,
    )


# ---- Actions ----------------------------------------------------------------

@router.get("/v1/actions")
def list_actions(
    pillar: str | None = None,
    motion: str | None = None,
    workspace: str | None = None,
    db: Session = Depends(get_db),
):
    """List all materialized actions (one per detected opportunity) with overrides applied."""
    from app.models.action import Action
    from app.services.scenario import _effective_action

    ws = workspace or settings.default_workspace
    q = select(Action).where(Action.workspace == ws)
    if pillar:
        q = q.where(Action.pillar == pillar)
    if motion:
        q = q.where(Action.motion == motion)
    q = q.order_by(Action.modeled_impact.desc())
    rows = db.execute(q).scalars().all()
    return [_effective_action(db, a, ws) for a in rows]


# ---- Scenarios --------------------------------------------------------------

class ScenarioCreate(BaseModel):
    name: str
    description: str | None = None
    action_ids: list[int] = []
    workspace: str | None = None


@router.post("/v1/scenarios")
def create_scenario(req: ScenarioCreate, db: Session = Depends(get_db)):
    """Create a new scenario with an initial set of actions."""
    from app.models.scenario import Scenario, ScenarioAction
    from app.models.action import Action
    from app.services.scenario import project_scenario, _effective_action

    ws = req.workspace or settings.default_workspace
    scn = Scenario(workspace=ws, name=req.name, description=req.description, status="draft")
    db.add(scn)
    db.flush()

    for aid in req.action_ids:
        action = db.get(Action, aid)
        if action is None:
            continue
        eff = _effective_action(db, action, ws)
        db.add(ScenarioAction(
            scenario_id=scn.id,
            action_id=aid,
            effective_impact=eff["effective_impact"],
            effective_confidence=eff["effective_confidence"],
            effective_ramp_months=eff["effective_ramp_months"],
            has_override="Y" if eff["has_override"] else "N",
        ))
    db.commit()

    return project_scenario(db, scn.id, ws)


@router.get("/v1/scenarios/{scenario_id}")
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    from app.models.scenario import Scenario
    from app.services.scenario import project_scenario

    scn = db.get(Scenario, scenario_id)
    if scn is None:
        raise HTTPException(404, "scenario not found")
    return project_scenario(db, scenario_id, scn.workspace)


class ScenarioUpdateActions(BaseModel):
    add_action_ids: list[int] = []
    remove_action_ids: list[int] = []


@router.patch("/v1/scenarios/{scenario_id}/actions")
def update_scenario_actions(scenario_id: int, req: ScenarioUpdateActions, db: Session = Depends(get_db)):
    from app.models.scenario import Scenario, ScenarioAction
    from app.models.action import Action
    from app.services.scenario import project_scenario, _effective_action

    scn = db.get(Scenario, scenario_id)
    if scn is None:
        raise HTTPException(404, "scenario not found")

    # Remove
    if req.remove_action_ids:
        db.query(ScenarioAction).filter(
            ScenarioAction.scenario_id == scenario_id,
            ScenarioAction.action_id.in_(req.remove_action_ids),
        ).delete(synchronize_session=False)

    # Add (dedup against existing)
    existing = set(
        db.execute(
            select(ScenarioAction.action_id).where(ScenarioAction.scenario_id == scenario_id)
        ).scalars().all()
    )
    for aid in req.add_action_ids:
        if aid in existing:
            continue
        action = db.get(Action, aid)
        if action is None:
            continue
        eff = _effective_action(db, action, scn.workspace)
        db.add(ScenarioAction(
            scenario_id=scenario_id,
            action_id=aid,
            effective_impact=eff["effective_impact"],
            effective_confidence=eff["effective_confidence"],
            effective_ramp_months=eff["effective_ramp_months"],
            has_override="Y" if eff["has_override"] else "N",
        ))

    db.commit()
    return project_scenario(db, scenario_id, scn.workspace)


# ---- Overrides --------------------------------------------------------------

class OverrideCreate(BaseModel):
    action_id: int
    impact_override: float | None = None
    confidence_override: float | None = None
    ramp_months_override: int | None = None
    reason: str
    workspace: str | None = None


@router.post("/v1/overrides")
def create_override(req: OverrideCreate, db: Session = Depends(get_db)):
    """Create (or update) an override for a given action."""
    from app.models.override import ActionOverride

    ws = req.workspace or settings.default_workspace
    # Deactivate prior overrides for this action
    db.query(ActionOverride).filter(
        ActionOverride.action_id == req.action_id,
        ActionOverride.workspace == ws,
        ActionOverride.active == "Y",
    ).update({"active": "N"}, synchronize_session=False)

    ov = ActionOverride(
        workspace=ws,
        action_id=req.action_id,
        impact_override=req.impact_override,
        confidence_override=req.confidence_override,
        ramp_months_override=req.ramp_months_override,
        reason=req.reason,
        author="user",
    )
    db.add(ov)
    db.commit()
    db.refresh(ov)
    return {"override_id": ov.id, "action_id": req.action_id}


@router.delete("/v1/overrides/{override_id}")
def deactivate_override(override_id: int, db: Session = Depends(get_db)):
    """Deactivate an override (soft delete)."""
    from app.models.override import ActionOverride
    ov = db.get(ActionOverride, override_id)
    if ov is None:
        raise HTTPException(404, "override not found")
    ov.active = "N"
    db.commit()
    return {"deactivated": override_id}
