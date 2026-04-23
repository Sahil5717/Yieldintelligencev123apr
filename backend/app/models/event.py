"""Market events — Acme-specific event calendar.

From Market_Events sheet. Used by trigger engine to boost time-sensitive opportunities.
"""
from sqlalchemy import Column, Integer, String, Float, Date
from app.db import Base


class MarketEvent(Base):
    __tablename__ = "market_events"

    id = Column(Integer, primary_key=True)
    event_date = Column(Date, nullable=False, index=True)
    event_end_date = Column(Date, nullable=True)
    event_type = Column(String(64), nullable=False)  # seasonal_peak | competitive | macro | regulatory
    event_name = Column(String(256), nullable=False)
    description = Column(String(1024), nullable=True)
    impact_direction = Column(String(16))  # positive | negative | neutral
    impact_magnitude = Column(String(16))  # low | medium | high
    impact_pct = Column(Float, default=0.0)
    affected_channels = Column(String(512), nullable=True)  # semicolon-separated
    affected_regions = Column(String(512), nullable=True)
    source = Column(String(128), nullable=True)
    confidence = Column(String(32), default="proposed")
