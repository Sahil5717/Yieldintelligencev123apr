"""User journey touchpoints — for attribution (Markov chain, Shapley).

Each row is one touchpoint in a user's path. Rollups to conversion at the journey level.
"""
from sqlalchemy import Column, Integer, String, Float, Date, Boolean, Index
from app.db import Base


class JourneyTouchpoint(Base):
    __tablename__ = "journey_touchpoints"

    id = Column(Integer, primary_key=True)
    journey_id = Column(String(32), nullable=False, index=True)
    touchpoint_order = Column(Integer, nullable=False)
    channel = Column(String(64), nullable=False, index=True)
    campaign = Column(String(128), nullable=True)
    timestamp = Column(Date, nullable=False)
    converted = Column(Boolean, nullable=False, default=False)
    conversion_revenue = Column(Float, nullable=False, default=0.0)
    total_touchpoints = Column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_journey_id_order", "journey_id", "touchpoint_order"),
    )
