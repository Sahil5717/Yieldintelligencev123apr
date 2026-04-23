"""Campaign performance — per-month, per-channel, per-campaign metrics.

Maps directly to the Campaign_Performance sheet in the Acme dataset.
"""
from sqlalchemy import Column, Integer, String, Float, Date, Index
from app.db import Base


class CampaignPerformance(Base):
    __tablename__ = "campaign_performance"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    channel = Column(String(64), nullable=False, index=True)
    channel_type = Column(String(32), nullable=False)  # online | offline
    campaign = Column(String(128), nullable=False)
    region = Column(String(32), nullable=True)
    product = Column(String(32), nullable=True)

    # Financials
    spend = Column(Float, nullable=False, default=0.0)
    revenue = Column(Float, nullable=False, default=0.0)

    # Online engagement
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    leads = Column(Integer, default=0)
    mqls = Column(Integer, default=0)
    sqls = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    bounce_rate = Column(Float, default=0.0)
    avg_session_duration_sec = Column(Integer, default=0)
    form_completion_rate = Column(Float, default=0.0)
    nps_score = Column(Integer, default=0)

    # Offline engagement
    grps = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    store_visits = Column(Integer, default=0)
    calls_generated = Column(Integer, default=0)
    event_attendees = Column(Integer, default=0)
    dealer_enquiries = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_perf_date_channel", "date", "channel"),
        Index("ix_perf_channel_campaign", "channel", "campaign"),
    )
