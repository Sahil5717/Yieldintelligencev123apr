"""Scenarios — a set of selected actions with simulated portfolio math.

A user composes a scenario by selecting actions. The scenario carries:
- the list of selected actions (with per-action overrides)
- the simulated portfolio KPIs (computed by the optimizer module)
- status (draft | active | committed | archived)
"""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Index
from sqlalchemy.sql import func
from app.db import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True)
    workspace = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="draft")  # draft | active | committed | archived

    # Baseline snapshot (at scenario creation)
    baseline_revenue = Column(Float, nullable=True)
    baseline_spend = Column(Float, nullable=True)
    baseline_roi = Column(Float, nullable=True)
    baseline_cac = Column(Float, nullable=True)

    # Simulated state
    projected_revenue = Column(Float, nullable=True)
    projected_spend = Column(Float, nullable=True)
    projected_roi = Column(Float, nullable=True)
    projected_cac = Column(Float, nullable=True)
    incremental_revenue = Column(Float, nullable=True)
    portfolio_confidence = Column(Float, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ScenarioAction(Base):
    """M2M — an action selected for a scenario, with per-action override snapshot."""
    __tablename__ = "scenario_actions"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, nullable=False, index=True)
    action_id = Column(Integer, nullable=False, index=True)

    # Effective values (after any user override)
    effective_impact = Column(Float, nullable=False)
    effective_confidence = Column(Float, nullable=False)
    effective_ramp_months = Column(Integer, nullable=False)

    # Indicates if user overrode the model defaults for this scenario
    has_override = Column(String(1), default="N")  # Y | N

    __table_args__ = (
        Index("ix_sa_scenario_action", "scenario_id", "action_id", unique=True),
    )
