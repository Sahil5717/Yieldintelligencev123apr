"""Data loader — seeds the DB from the Acme dataset + catalog + global signals.

Runs on first app boot. Idempotent (skips if tables already populated).
"""
from __future__ import annotations
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.config import settings
from app.models.campaign import CampaignPerformance
from app.models.journey import JourneyTouchpoint
from app.models.event import MarketEvent
from app.models.trend import MarketTrend
from app.models.competitive import CompetitiveIntel
from app.models.global_signal import (
    GlobalEvent, GlobalHoliday, SeasonalWindow,
    ConsumerSentiment, CategorySeasonality,
)
from app.models.opportunity import OpportunityTemplate


# ---- Pillar + motion derivation from catalog.Category -----------------------

_CATEGORY_PILLAR = {
    "Tactical": None,  # resolved per subcategory — handled below
    "Strategic-Channel": "revenue",
    "Strategic-Cost": "cost",
    "Strategic-CX": "cx",
    "Strategic-Capability": "revenue",  # capability opps unblock revenue mostly
    "Strategic-Measurement": "revenue",
    "Strategic-Content": "revenue",
    "Strategic-Pricing": "revenue",
    "Strategic-Meta": "cost",
    "Defensive": "risk",
}


def _derive_pillar(category: str, subcategory: str | None, name: str) -> str:
    """Map catalog.Category to our 4 pillars: revenue | cost | cx | risk."""
    if category == "Tactical":
        low = name.lower()
        # Cost moves: cutting, capping, pausing, removing, renegotiating, eliminating
        cost_keywords = (
            "cut", "cap ", "pause", "trim", "renegotiate", "eliminate",
            "remove", "exclude", "restrict", "consolidate", "frequency cap",
            "negative keyword", "zero-conversion",
        )
        if any(kw in low for kw in cost_keywords):
            return "cost"
        return "revenue"
    return _CATEGORY_PILLAR.get(category, "revenue")


def _derive_motion(category: str, timeline: str | None, reversibility: str | None) -> str:
    """optimization = tactical + reversible + Days/Weeks; transformation = the rest."""
    if category == "Tactical":
        return "optimization"
    if timeline in ("Days", "Weeks") and reversibility == "H":
        return "optimization"
    return "transformation"


# ---- Helpers ----------------------------------------------------------------

def _is_populated(db: Session, model) -> bool:
    count = db.execute(select(func.count()).select_from(model)).scalar_one()
    return count > 0


def _date(v):
    """Coerce any date-ish thing to a python date, or None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v).date()
        except ValueError:
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except ValueError:
                return None
    if hasattr(v, "date"):
        return v.date()
    return None


def _s(v, default=""):
    """Safe string — returns default for NaN."""
    if v is None:
        return default
    if isinstance(v, float) and pd.isna(v):
        return default
    return str(v)


def _f(v, default=0.0):
    """Safe float."""
    if v is None:
        return default
    if isinstance(v, float) and pd.isna(v):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default=0):
    return int(_f(v, default))


# ---- Loaders ----------------------------------------------------------------

def load_acme_dataset(db: Session, which: str = "5yr") -> dict:
    """Load Acme's Campaign_Performance, User_Journeys, Market_Events, Market_Trends,
    Competitive_Intel from the selected Excel.
    """
    if _is_populated(db, CampaignPerformance):
        return {"skipped": "Acme dataset already loaded"}

    path = settings.seed_dir / f"acme_{which}.xlsx"
    xl = pd.ExcelFile(path)
    counts = {}

    # Campaign performance
    df = pd.read_excel(xl, "Campaign_Performance")
    rows = []
    for _, r in df.iterrows():
        rows.append(CampaignPerformance(
            date=_date(r["date"]),
            channel=_s(r["channel"]),
            channel_type=_s(r["channel_type"]),
            campaign=_s(r["campaign"]),
            region=_s(r.get("region")),
            product=_s(r.get("product")),
            spend=_f(r["spend"]),
            revenue=_f(r["revenue"]),
            impressions=_i(r.get("impressions")),
            clicks=_i(r.get("clicks")),
            leads=_i(r.get("leads")),
            mqls=_i(r.get("mqls")),
            sqls=_i(r.get("sqls")),
            conversions=_i(r.get("conversions")),
            bounce_rate=_f(r.get("bounce_rate")),
            avg_session_duration_sec=_i(r.get("avg_session_duration_sec")),
            form_completion_rate=_f(r.get("form_completion_rate")),
            nps_score=_i(r.get("nps_score")),
            grps=_i(r.get("grps")),
            reach=_i(r.get("reach")),
            store_visits=_i(r.get("store_visits")),
            calls_generated=_i(r.get("calls_generated")),
            event_attendees=_i(r.get("event_attendees")),
            dealer_enquiries=_i(r.get("dealer_enquiries")),
        ))
    db.bulk_save_objects(rows)
    counts["campaign_performance"] = len(rows)

    # User journeys
    df = pd.read_excel(xl, "User_Journeys")
    rows = [JourneyTouchpoint(
        journey_id=_s(r["journey_id"]),
        touchpoint_order=_i(r["touchpoint_order"]),
        channel=_s(r["channel"]),
        campaign=_s(r.get("campaign")),
        timestamp=_date(r["timestamp"]),
        converted=bool(r.get("converted", False)),
        conversion_revenue=_f(r.get("conversion_revenue")),
        total_touchpoints=_i(r.get("total_touchpoints")),
    ) for _, r in df.iterrows()]
    db.bulk_save_objects(rows)
    counts["user_journeys"] = len(rows)

    # Competitive intel — date column is YYYY-MM string, parse to first of month
    df = pd.read_excel(xl, "Competitive_Intel")
    rows = []
    for _, r in df.iterrows():
        date_str = _s(r["date"])
        d = None
        if date_str:
            try:
                d = datetime.strptime(date_str + "-01", "%Y-%m-%d").date()
            except ValueError:
                d = _date(r["date"])
        rows.append(CompetitiveIntel(
            date=d,
            competitor=_s(r["competitor"]),
            channel=_s(r["channel"]),
            estimated_spend=_f(r.get("estimated_spend")),
            traffic_share=_f(r.get("traffic_share")),
            impression_share=_f(r.get("impression_share")),
            keyword_overlap=_f(r.get("keyword_overlap")),
            avg_cpc=_f(r.get("avg_cpc")),
            avg_cpm=_f(r.get("avg_cpm")),
            new_campaigns=_i(r.get("new_campaigns")),
            creative_volume=_i(r.get("creative_volume")),
        ))
    db.bulk_save_objects(rows)
    counts["competitive_intel"] = len(rows)

    # Market events
    df = pd.read_excel(xl, "Market_Events")
    rows = [MarketEvent(
        event_date=_date(r["event_date"]),
        event_end_date=_date(r.get("event_end_date")),
        event_type=_s(r["event_type"]),
        event_name=_s(r["event_name"]),
        description=_s(r.get("description")),
        impact_direction=_s(r.get("impact_direction")),
        impact_magnitude=_s(r.get("impact_magnitude")),
        impact_pct=_f(r.get("impact_pct")),
        affected_channels=_s(r.get("affected_channels")),
        affected_regions=_s(r.get("affected_regions")),
        source=_s(r.get("source")),
        confidence=_s(r.get("confidence")),
    ) for _, r in df.iterrows()]
    db.bulk_save_objects(rows)
    counts["market_events"] = len(rows)

    # Market trends — date column is YYYY-MM
    df = pd.read_excel(xl, "Market_Trends")
    rows = []
    for _, r in df.iterrows():
        date_str = _s(r["date"])
        d = None
        if date_str:
            try:
                d = datetime.strptime(date_str + "-01", "%Y-%m-%d").date()
            except ValueError:
                d = _date(r["date"])
        rows.append(MarketTrend(
            date=d,
            metric_type=_s(r["metric_type"]),
            channel=_s(r.get("channel")),
            region=_s(r.get("region")),
            value=_f(r["value"]),
            yoy_change_pct=_f(r.get("yoy_change_pct")),
            benchmark_source=_s(r.get("benchmark_source")),
            category=_s(r.get("category")),
            notes=_s(r.get("notes")),
        ))
    db.bulk_save_objects(rows)
    counts["market_trends"] = len(rows)

    db.commit()
    return counts


def load_catalog(db: Session) -> dict:
    """Load the 94-item opportunity catalog."""
    if _is_populated(db, OpportunityTemplate):
        return {"skipped": "catalog already loaded"}

    path = settings.seed_dir / "catalog.xlsx"
    df = pd.read_excel(path, sheet_name="Catalog")

    rows = []
    for _, r in df.iterrows():
        category = _s(r["Category"])
        subcategory = _s(r.get("Subcategory"))
        name = _s(r["Opportunity name"])
        timeline = _s(r.get("Timeline"))
        reversibility = _s(r.get("Reversibility"))

        rows.append(OpportunityTemplate(
            catalog_id=_s(r["ID"]),
            category=category,
            subcategory=subcategory,
            name=name,
            description=_s(r.get("Description")),
            magnitude_low=_f(r.get("Magnitude — Low ($)"), 0.0) or None,
            magnitude_high=_f(r.get("Magnitude — High ($)"), 0.0) or None,
            mag_band=_s(r.get("Mag band")),
            confidence=_s(r.get("Confidence")),
            required_signals=_s(r.get("Required data signals")),
            external_signals=_s(r.get("External signals used")),
            trigger_conditions=_s(r.get("Trigger conditions")),
            timeline=timeline,
            reversibility=reversibility,
            decision_audience=_s(r.get("Decision audience")),
            motion=_derive_motion(category, timeline, reversibility),
            pillar=_derive_pillar(category, subcategory, name),
            retail=_s(r.get("Retail"), "N"),
            b2b_saas=_s(r.get("B2B SaaS"), "N"),
            dtc=_s(r.get("DTC"), "N"),
            services=_s(r.get("Services"), "N"),
            risk_notes=_s(r.get("Risk notes")),
            effects_json=_s(r.get("Effects (JSON)")),
            impl_one_time_k=_f(r.get("Impl one-time ($K)")) or None,
            impl_annual_k=_f(r.get("Impl annual ($K)")) or None,
            impl_timing=_s(r.get("Impl timing")),
            dependencies=_s(r.get("Dependencies")),
            mutex_with=_s(r.get("Mutex with")),
            status=_s(r.get("Status"), "Proposed"),
        ))
    db.bulk_save_objects(rows)
    db.commit()
    return {"catalog_items": len(rows)}


def load_global_signals(db: Session) -> dict:
    """Load the 5 global signal CSVs."""
    counts = {}

    if not _is_populated(db, GlobalEvent):
        df = pd.read_csv(settings.seed_dir / "01_global_event_calendar.csv")
        rows = [GlobalEvent(
            event_name=_s(r["event_name"]),
            start_date=_date(r["start_date"]),
            end_date=_date(r.get("end_date")),
            regions=_s(r.get("regions"), "GLOBAL"),
            category=_s(r.get("category")),
            significance=_s(r.get("significance")),
            demand_lift_category=_s(r.get("demand_lift_category")),
            notes=_s(r.get("notes")),
        ) for _, r in df.iterrows()]
        db.bulk_save_objects(rows)
        counts["global_events"] = len(rows)

    if not _is_populated(db, GlobalHoliday):
        df = pd.read_csv(settings.seed_dir / "holidays.csv")
        rows = [GlobalHoliday(
            holiday_name=_s(r["holiday_name"]),
            date=_date(r["date"]),
            type=_s(r.get("type")),
            regions=_s(r.get("regions"), "GLOBAL"),
            commerce_impact=_s(r.get("commerce_impact")),
            notes=_s(r.get("notes")),
        ) for _, r in df.iterrows()]
        db.bulk_save_objects(rows)
        counts["holidays"] = len(rows)

    if not _is_populated(db, SeasonalWindow):
        df = pd.read_csv(settings.seed_dir / "seasonal_windows.csv")
        rows = [SeasonalWindow(
            region=_s(r["region"]),
            year=_i(r["year"]),
            start_date=_date(r["start_date"]),
            end_date=_date(r["end_date"]),
            season_window=_s(r["season_window"]),
            intensity=_s(r.get("intensity")),
            notes=_s(r.get("notes")),
        ) for _, r in df.iterrows()]
        db.bulk_save_objects(rows)
        counts["seasonal_windows"] = len(rows)

    if not _is_populated(db, ConsumerSentiment):
        df = pd.read_csv(settings.seed_dir / "consumer_sentiment.csv")
        rows = [ConsumerSentiment(
            month=_s(r["month"]),
            region=_s(r["region"]),
            index_name=_s(r["index_name"]),
            value=_f(r["value"]),
            index_source=_s(r.get("index_source")),
            change_vs_prior=_f(r.get("change_vs_prior")) or None,
            notes=_s(r.get("notes")),
        ) for _, r in df.iterrows()]
        db.bulk_save_objects(rows)
        counts["consumer_sentiment"] = len(rows)

    if not _is_populated(db, CategorySeasonality):
        df = pd.read_csv(settings.seed_dir / "category_seasonality.csv")
        rows = [CategorySeasonality(
            region=_s(r["region"]),
            category=_s(r["category"]),
            month=_s(r["month"]),
            seasonality_index=_f(r["seasonality_index"]),
            demand_driver=_s(r.get("demand_driver")),
            source_type=_s(r.get("source_type")),
            notes=_s(r.get("notes")),
        ) for _, r in df.iterrows()]
        db.bulk_save_objects(rows)
        counts["category_seasonality"] = len(rows)

    db.commit()
    return counts


def seed_all(db: Session) -> dict:
    """One-shot seed — call on app startup."""
    result = {}
    result["acme"] = load_acme_dataset(db, settings.default_dataset)
    result["catalog"] = load_catalog(db)
    result["global"] = load_global_signals(db)
    return result
