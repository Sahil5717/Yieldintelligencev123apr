"""Market trends — CPC/CPM benchmarks, industry baselines."""
from sqlalchemy import Column, Integer, String, Float, Date
from app.db import Base


class MarketTrend(Base):
    __tablename__ = "market_trends"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    metric_type = Column(String(64), nullable=False)  # cpc_trend, cpm_trend, cvr_trend, etc.
    channel = Column(String(64), nullable=True, index=True)
    region = Column(String(32), nullable=True)
    value = Column(Float, nullable=False)
    yoy_change_pct = Column(Float, nullable=True)
    benchmark_source = Column(String(128), nullable=True)
    category = Column(String(64), nullable=True)
    notes = Column(String(512), nullable=True)
