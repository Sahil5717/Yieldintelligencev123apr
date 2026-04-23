"""Global signals — cross-industry reference data.

Used by the trigger engine to contextualize Acme's specific situation against
broader market seasonality, festivities, macro conditions.
"""
from sqlalchemy import Column, Integer, String, Float, Date
from app.db import Base


class GlobalEvent(Base):
    __tablename__ = "global_events"
    id = Column(Integer, primary_key=True)
    event_name = Column(String(256), nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    regions = Column(String(128), default="GLOBAL")
    category = Column(String(64))
    significance = Column(String(32))  # major | medium | minor
    demand_lift_category = Column(String(32))  # up | down | mixed
    notes = Column(String(512), nullable=True)


class GlobalHoliday(Base):
    __tablename__ = "global_holidays"
    id = Column(Integer, primary_key=True)
    holiday_name = Column(String(128), nullable=False)
    date = Column(Date, nullable=False, index=True)
    type = Column(String(64))
    regions = Column(String(128), default="GLOBAL")
    commerce_impact = Column(String(16))  # low | medium | high
    notes = Column(String(512), nullable=True)


class SeasonalWindow(Base):
    __tablename__ = "seasonal_windows"
    id = Column(Integer, primary_key=True)
    region = Column(String(64), nullable=False)
    year = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    season_window = Column(String(64), nullable=False)  # winter/summer/monsoon/etc
    intensity = Column(String(16))
    notes = Column(String(512), nullable=True)


class ConsumerSentiment(Base):
    __tablename__ = "consumer_sentiment"
    id = Column(Integer, primary_key=True)
    month = Column(String(8), nullable=False, index=True)  # YYYY-MM
    region = Column(String(64), nullable=False)
    index_name = Column(String(64), nullable=False)
    value = Column(Float, nullable=False)
    index_source = Column(String(64), nullable=True)
    change_vs_prior = Column(Float, nullable=True)
    notes = Column(String(512), nullable=True)


class CategorySeasonality(Base):
    __tablename__ = "category_seasonality"
    id = Column(Integer, primary_key=True)
    region = Column(String(64), nullable=False)
    category = Column(String(64), nullable=False, index=True)
    month = Column(String(8), nullable=False, index=True)
    seasonality_index = Column(Float, nullable=False)  # 100 = long-run average
    demand_driver = Column(String(256), nullable=True)
    source_type = Column(String(64), nullable=True)
    notes = Column(String(512), nullable=True)
