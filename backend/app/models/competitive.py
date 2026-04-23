"""Competitive intelligence — competitor spend, share, overlap."""
from sqlalchemy import Column, Integer, String, Float, Date
from app.db import Base


class CompetitiveIntel(Base):
    __tablename__ = "competitive_intel"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    competitor = Column(String(64), nullable=False, index=True)
    channel = Column(String(64), nullable=False, index=True)
    estimated_spend = Column(Float, default=0.0)
    traffic_share = Column(Float, default=0.0)
    impression_share = Column(Float, default=0.0)
    keyword_overlap = Column(Float, default=0.0)
    avg_cpc = Column(Float, default=0.0)
    avg_cpm = Column(Float, default=0.0)
    new_campaigns = Column(Integer, default=0)
    creative_volume = Column(Integer, default=0)
