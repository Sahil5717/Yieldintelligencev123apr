"""Pydantic schemas for API responses."""
from pydantic import BaseModel, ConfigDict
from typing import Optional


class PillarSummary(BaseModel):
    pillar: str
    label: str
    total_impact: float
    action_count: int
    optimization_count: int
    optimization_total: float
    transformation_count: int
    transformation_total: float


class ActionOut(BaseModel):
    action_id: int
    catalog_id: str
    name: str
    pillar: str
    motion: str
    modeled_impact: float
    confidence: float
    ramp_months: int
    rationale: str
    timeline: Optional[str] = None
    reversibility: Optional[str] = None
    has_override: bool = False
    effective_impact: Optional[float] = None
    override_reason: Optional[str] = None


class DetectedOpportunityOut(BaseModel):
    catalog_id: str
    name: str
    pillar: str
    motion: str
    modeled_impact: float
    low_estimate: Optional[float] = None
    high_estimate: Optional[float] = None
    confidence: float
    rationale: str
    evidence: list[dict] = []
    external_boost: float = 1.0
    external_signal_refs: list[str] = []
    source: str  # auto | manual


class ExecSummary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    workspace: str
    as_of: str
    total_on_table: float
    optimization_total: float
    transformation_total: float
    optimization_action_count: int
    transformation_action_count: int
    pillars: list[PillarSummary]
    kpis: dict  # revenue, roi, spend, cac, plus deltas
    market_trends: list[dict]
    model_confidence: float
    detected_count: int


class LibraryItemOut(BaseModel):
    catalog_id: str
    name: str
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    pillar: str
    motion: str
    magnitude_low: Optional[float] = None
    magnitude_high: Optional[float] = None
    confidence: Optional[str] = None
    timeline: Optional[str] = None
    reversibility: Optional[str] = None
    trigger_conditions: Optional[str] = None
    has_rule: bool
    fired: Optional[bool] = None
    why_not: Optional[str] = None


class MarketTrendOut(BaseModel):
    name: str
    weeks_out: Optional[int] = None
    impact_pct: Optional[float] = None
    direction: str
    when: str  # human-readable
