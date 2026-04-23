"""User overrides — edits made by the CMO to a model's output.

Every override is durable and audited. When the model re-runs, overrides persist
unless explicitly reset. Over time, overrides become training signal for calibration.
"""
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, Index
from sqlalchemy.sql import func
from app.db import Base


class ActionOverride(Base):
    __tablename__ = "action_overrides"

    id = Column(Integer, primary_key=True)
    workspace = Column(String(64), nullable=False, index=True)
    action_id = Column(Integer, nullable=False, index=True)

    # Override fields — NULL means 'use model value'
    impact_override = Column(Float, nullable=True)
    confidence_override = Column(Float, nullable=True)
    ramp_months_override = Column(Integer, nullable=True)

    # Audit
    reason = Column(Text, nullable=False)
    author = Column(String(128), nullable=False, default="user")
    created_at = Column(DateTime, server_default=func.now())
    active = Column(String(1), default="Y")  # Y | N (soft delete)

    __table_args__ = (
        Index("ix_override_action", "action_id", "active"),
    )
