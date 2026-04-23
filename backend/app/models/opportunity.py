"""Opportunity catalog — the library of 94 opportunity types.

Populated from the Yield Intelligence opportunity catalog Excel on seed.
These are the 'library' items; the 'detected' list is derived at request time
by running triggers against the current data snapshot.
"""
from sqlalchemy import Column, Integer, String, Float, Text, Index
from app.db import Base


class OpportunityTemplate(Base):
    __tablename__ = "opportunity_templates"

    id = Column(Integer, primary_key=True)
    catalog_id = Column(String(16), nullable=False, unique=True)  # OPP-001 .. OPP-094
    category = Column(String(64), nullable=False)  # Tactical | Strategic-*
    subcategory = Column(String(64), nullable=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)

    # Magnitude band
    magnitude_low = Column(Float, nullable=True)
    magnitude_high = Column(Float, nullable=True)
    mag_band = Column(String(8))  # S, M, L
    confidence = Column(String(8))  # H, M, L

    # Trigger-related
    required_signals = Column(Text, nullable=True)
    external_signals = Column(Text, nullable=True)
    trigger_conditions = Column(Text, nullable=True)  # English description

    # Classification
    timeline = Column(String(32))  # Days | Weeks | Months | Quarters
    reversibility = Column(String(8))  # H, M, L
    decision_audience = Column(String(64))
    motion = Column(String(16))  # optimization | transformation — derived from Category

    # Pillar mapping (derived from catalog category)
    pillar = Column(String(32))  # revenue | cost | cx | risk

    # Vertical applicability
    retail = Column(String(1), default="N")
    b2b_saas = Column(String(1), default="N")
    dtc = Column(String(1), default="N")
    services = Column(String(1), default="N")

    # Risk + effects
    risk_notes = Column(Text, nullable=True)
    effects_json = Column(Text, nullable=True)  # raw JSON from catalog

    # Implementation
    impl_one_time_k = Column(Float, nullable=True)
    impl_annual_k = Column(Float, nullable=True)
    impl_timing = Column(String(32), nullable=True)
    dependencies = Column(String(256), nullable=True)
    mutex_with = Column(String(256), nullable=True)

    status = Column(String(16), default="Proposed")


class DetectedOpportunity(Base):
    """Result of a trigger evaluation — an opp template that fired for this workspace.

    Rebuilt on demand when data or scenario changes. Also stores manual additions
    (custom-added from library) with source = 'manual'.
    """
    __tablename__ = "detected_opportunities"

    id = Column(Integer, primary_key=True)
    workspace = Column(String(64), nullable=False, index=True)
    catalog_id = Column(String(16), nullable=False)
    source = Column(String(16), nullable=False, default="auto")  # auto | manual
    detected_at = Column(String(32), nullable=False)  # ISO datetime

    # Computed impact
    modeled_impact = Column(Float, nullable=True)
    low_estimate = Column(Float, nullable=True)
    high_estimate = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)  # 0..1

    # Why triggered — plain-English rationale computed by trigger engine
    rationale = Column(Text, nullable=True)

    # Evidence — JSON array of evidence bullets with source refs
    evidence_json = Column(Text, nullable=True)

    # External signal boost factor (1.0 = no boost, 1.25 = 25% boost)
    external_boost = Column(Float, default=1.0)
    external_signal_refs = Column(String(512), nullable=True)

    __table_args__ = (
        Index("ix_det_workspace_catalog", "workspace", "catalog_id"),
    )
