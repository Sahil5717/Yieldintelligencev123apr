"""Actions — concrete moves derived from detected opportunities.

One opportunity can have multiple actions. Actions are what get selected for
a scenario.
"""
from sqlalchemy import Column, Integer, String, Float, Text, Index
from app.db import Base


class Action(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True)
    workspace = Column(String(64), nullable=False, index=True)
    detected_opp_id = Column(Integer, nullable=False, index=True)
    action_key = Column(String(128), nullable=False)  # human-readable key for reference

    # What to do
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    effect_type = Column(String(64))  # spend_shift | spend_cut | spend_cap | new_channel | capability
    effect_params_json = Column(Text, nullable=True)

    # Classification
    pillar = Column(String(16), nullable=False)  # revenue | cost | cx | risk
    motion = Column(String(16), nullable=False)  # optimization | transformation

    # Impact estimates — model-generated
    modeled_impact = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.5)  # 0..1
    ramp_months = Column(Integer, nullable=False, default=1)

    # Execution properties
    timeline = Column(String(32))  # Days | Weeks | Months | Quarters
    reversibility = Column(String(8))  # H | M | L
    decision_audience = Column(String(64))

    __table_args__ = (
        Index("ix_act_workspace_pillar", "workspace", "pillar"),
    )


class ActionEvidence(Base):
    """Atomic evidence bullets that support an action's rationale."""
    __tablename__ = "action_evidence"

    id = Column(Integer, primary_key=True)
    action_id = Column(Integer, nullable=False, index=True)
    statement = Column(Text, nullable=False)
    source = Column(String(256), nullable=True)
    kind = Column(String(32))  # data | benchmark | external | case_study
    strength = Column(String(16))  # strong | moderate | weak
    value = Column(Float, nullable=True)  # numeric value when applicable
