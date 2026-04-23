"""Trigger evaluation engine — determines which catalog opportunities apply to Acme.

Each catalog item has a trigger_conditions string (English). This module implements
explicit rules for a subset of catalog IDs, producing:
  - whether the trigger fires (bool)
  - modeled impact (dollars)
  - confidence score (0..1)
  - rationale (plain English)
  - evidence bullets (source-attributed)
  - external signal boost factor

For catalog items without explicit rules, the item is evaluable from the library
only (CMO can add manually). This is realistic v1 scope — the full 94-item rule
coverage is an ongoing project.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.campaign import CampaignPerformance
from app.models.competitive import CompetitiveIntel
from app.models.event import MarketEvent
from app.models.trend import MarketTrend
from app.models.opportunity import OpportunityTemplate, DetectedOpportunity


# -----------------------------------------------------------------------------
# Data snapshot — computed once per trigger run, passed to every rule
# -----------------------------------------------------------------------------

@dataclass
class DataSnapshot:
    """Pre-computed aggregates the rules need. Built once per run."""
    as_of: date
    lookback_months: int

    # Channel-level aggregates (last lookback_months)
    channel_spend: dict[str, float] = field(default_factory=dict)
    channel_revenue: dict[str, float] = field(default_factory=dict)
    channel_roi: dict[str, float] = field(default_factory=dict)
    channel_conversions: dict[str, int] = field(default_factory=dict)
    portfolio_spend: float = 0.0
    portfolio_revenue: float = 0.0
    portfolio_roi: float = 0.0
    portfolio_median_roi: float = 0.0

    # Campaign-level (for sub-1x, past-peak, etc.)
    campaign_stats: list[dict] = field(default_factory=list)

    # Competitive
    competitor_avg_cpm_growth_pct: dict[str, float] = field(default_factory=dict)

    # Market events in look-ahead window
    upcoming_events: list[dict] = field(default_factory=list)


def build_snapshot(db: Session, lookback_months: int = 3) -> DataSnapshot:
    """Roll up Acme data into the aggregates the trigger engine needs."""
    # Find latest date in data
    latest = db.execute(select(func.max(CampaignPerformance.date))).scalar_one()
    if latest is None:
        return DataSnapshot(as_of=date.today(), lookback_months=lookback_months)

    cutoff = latest.replace(day=1)
    # Go back N months
    y, m = cutoff.year, cutoff.month
    for _ in range(lookback_months - 1):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    cutoff = date(y, m, 1)

    snap = DataSnapshot(as_of=latest, lookback_months=lookback_months)

    # Channel-level aggregates over lookback
    rows = db.execute(
        select(
            CampaignPerformance.channel,
            func.sum(CampaignPerformance.spend),
            func.sum(CampaignPerformance.revenue),
            func.sum(CampaignPerformance.conversions),
        )
        .where(CampaignPerformance.date >= cutoff)
        .group_by(CampaignPerformance.channel)
    ).all()

    for ch, spend, rev, conv in rows:
        snap.channel_spend[ch] = float(spend or 0)
        snap.channel_revenue[ch] = float(rev or 0)
        snap.channel_conversions[ch] = int(conv or 0)
        snap.channel_roi[ch] = (float(rev or 0) / float(spend or 1)) if spend else 0.0

    snap.portfolio_spend = sum(snap.channel_spend.values())
    snap.portfolio_revenue = sum(snap.channel_revenue.values())
    snap.portfolio_roi = snap.portfolio_revenue / snap.portfolio_spend if snap.portfolio_spend else 0.0
    rois = sorted(snap.channel_roi.values())
    snap.portfolio_median_roi = rois[len(rois) // 2] if rois else 0.0

    # Campaign-level over lookback
    camp_rows = db.execute(
        select(
            CampaignPerformance.campaign,
            CampaignPerformance.channel,
            func.sum(CampaignPerformance.spend),
            func.sum(CampaignPerformance.revenue),
            func.sum(CampaignPerformance.conversions),
        )
        .where(CampaignPerformance.date >= cutoff)
        .group_by(CampaignPerformance.campaign, CampaignPerformance.channel)
    ).all()

    for camp, ch, spend, rev, conv in camp_rows:
        sp = float(spend or 0)
        rv = float(rev or 0)
        snap.campaign_stats.append({
            "campaign": camp,
            "channel": ch,
            "spend": sp,
            "revenue": rv,
            "conversions": int(conv or 0),
            "roi": (rv / sp) if sp else 0.0,
        })

    # Competitive CPM growth — compare last month vs 6 months earlier
    cpm_rows = db.execute(
        select(CompetitiveIntel.channel, CompetitiveIntel.date, CompetitiveIntel.avg_cpm)
        .where(CompetitiveIntel.avg_cpm > 0)
        .order_by(CompetitiveIntel.channel, CompetitiveIntel.date)
    ).all()
    df = pd.DataFrame(cpm_rows, columns=["channel", "date", "cpm"])
    if not df.empty:
        for ch, grp in df.groupby("channel"):
            if len(grp) >= 7:
                recent = grp.iloc[-1]["cpm"]
                prior = grp.iloc[-7]["cpm"]
                if prior > 0:
                    snap.competitor_avg_cpm_growth_pct[ch] = (recent - prior) / prior * 100

    # Upcoming events (next 180 days)
    horizon = latest + timedelta(days=180)
    ev_rows = db.execute(
        select(MarketEvent).where(
            MarketEvent.event_date >= latest,
            MarketEvent.event_date <= horizon,
        )
    ).scalars().all()
    for e in ev_rows:
        snap.upcoming_events.append({
            "name": e.event_name,
            "date": e.event_date.isoformat(),
            "type": e.event_type,
            "direction": e.impact_direction,
            "magnitude": e.impact_magnitude,
            "pct": e.impact_pct,
            "channels": (e.affected_channels or "").split(";") if e.affected_channels else [],
            "weeks_out": (e.event_date - latest).days // 7,
        })

    return snap


# -----------------------------------------------------------------------------
# Trigger rule registry
# -----------------------------------------------------------------------------

@dataclass
class DetectionResult:
    catalog_id: str
    fires: bool
    modeled_impact: float = 0.0
    low_estimate: float = 0.0
    high_estimate: float = 0.0
    confidence: float = 0.5
    rationale: str = ""
    evidence: list[dict] = field(default_factory=list)
    external_boost: float = 1.0
    external_signal_refs: list[str] = field(default_factory=list)
    why_not: str = ""  # populated when not fires


RULES: dict[str, Callable[[DataSnapshot], DetectionResult]] = {}


def rule(catalog_id: str):
    def deco(fn):
        RULES[catalog_id] = fn
        return fn
    return deco


# ---- Individual rule implementations ---------------------------------------

@rule("OPP-001")
def _rule_opp_001(snap: DataSnapshot) -> DetectionResult:
    """Shift budget from saturated channel to channel with headroom."""
    if not snap.channel_roi:
        return DetectionResult("OPP-001", False, why_not="no channel data")

    sat = [ch for ch, roi in snap.channel_roi.items() if roi < snap.portfolio_median_roi * 0.8]
    head = [ch for ch, roi in snap.channel_roi.items() if roi > snap.portfolio_median_roi * 1.3]

    if not sat or not head:
        return DetectionResult("OPP-001", False,
            why_not=f"no clear saturated+headroom pair (median ROI {snap.portfolio_median_roi:.2f}×)")

    # Move ~15% of saturated channel spend into headroom; net lift = (head_roi - sat_roi) × amount
    sat_ch = min(sat, key=lambda c: snap.channel_roi[c])
    head_ch = max(head, key=lambda c: snap.channel_roi[c])
    amount = snap.channel_spend[sat_ch] * 0.15
    lift = (snap.channel_roi[head_ch] - snap.channel_roi[sat_ch]) * amount

    return DetectionResult(
        "OPP-001", True,
        modeled_impact=lift * (12 / snap.lookback_months),  # annualize
        low_estimate=lift * 0.6 * (12 / snap.lookback_months),
        high_estimate=lift * 1.3 * (12 / snap.lookback_months),
        confidence=0.85,
        rationale=(
            f"{sat_ch} ROI {snap.channel_roi[sat_ch]:.2f}× below portfolio median "
            f"({snap.portfolio_median_roi:.2f}×); {head_ch} ROI {snap.channel_roi[head_ch]:.2f}× above"
        ),
        evidence=[
            {"statement": f"{sat_ch}: ROI {snap.channel_roi[sat_ch]:.2f}× on ${snap.channel_spend[sat_ch]:,.0f} spend ({snap.lookback_months}mo)",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": f"{head_ch}: ROI {snap.channel_roi[head_ch]:.2f}× on ${snap.channel_spend[head_ch]:,.0f} spend ({snap.lookback_months}mo)",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": f"Portfolio median ROI: {snap.portfolio_median_roi:.2f}×",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
        ],
    )


@rule("OPP-003")
def _rule_opp_003(snap: DataSnapshot) -> DetectionResult:
    """Eliminate sub-1× ROI campaign at zero downside."""
    sub = [c for c in snap.campaign_stats if 0 < c["roi"] < 1.0 and c["spend"] > 10000]
    if not sub:
        return DetectionResult("OPP-003", False, why_not="no campaigns below 1× ROI with material spend")

    total_wasted_spend = sum(c["spend"] - c["revenue"] for c in sub)
    annual = total_wasted_spend * (12 / snap.lookback_months)

    return DetectionResult(
        "OPP-003", True,
        modeled_impact=annual,
        low_estimate=annual * 0.7,
        high_estimate=annual,
        confidence=0.92,
        rationale=f"{len(sub)} campaigns below 1× ROI burning ${total_wasted_spend:,.0f} over {snap.lookback_months} months",
        evidence=[
            {"statement": f"Worst: {c['campaign']} at {c['roi']:.2f}× ROI, ${c['spend']:,.0f} spend, ${c['revenue']:,.0f} revenue",
             "source": "campaign_performance", "kind": "data", "strength": "strong"}
            for c in sorted(sub, key=lambda x: x["roi"])[:3]
        ],
    )


@rule("OPP-007")
def _rule_opp_007(snap: DataSnapshot) -> DetectionResult:
    """Frequency cap on over-served retargeting audience — heuristic on retargeting channels."""
    rt_channels = [ch for ch in snap.channel_spend if "retargeting" in ch.lower() or "_rt" in ch.lower() or ch.lower().endswith(" rt")]
    if not rt_channels:
        # Also look for display that might be RT
        rt_channels = [ch for ch in snap.channel_spend if "display" in ch.lower()]
    if not rt_channels:
        return DetectionResult("OPP-007", False, why_not="no retargeting channel identified")

    # Proxy: if RT channel ROI < 1.5x, frequency cap likely saves 10-15% of spend with minimal rev impact
    worst_rt = min(rt_channels, key=lambda c: snap.channel_roi.get(c, 99))
    if snap.channel_roi.get(worst_rt, 99) > 1.5:
        return DetectionResult("OPP-007", False, why_not=f"{worst_rt} ROI {snap.channel_roi[worst_rt]:.2f}× healthy")

    savings = snap.channel_spend[worst_rt] * 0.12 * (12 / snap.lookback_months)
    return DetectionResult(
        "OPP-007", True,
        modeled_impact=savings,
        low_estimate=savings * 0.6,
        high_estimate=savings * 1.4,
        confidence=0.78,
        rationale=f"{worst_rt} ROI {snap.channel_roi[worst_rt]:.2f}× — retargeting over-served to converted users",
        evidence=[
            {"statement": f"{worst_rt}: ROI {snap.channel_roi[worst_rt]:.2f}× on ${snap.channel_spend[worst_rt]:,.0f} spend",
             "source": "campaign_performance", "kind": "data", "strength": "moderate"},
            {"statement": "Typical frequency cap at 5/week saves 10–15% of RT spend with <2% CVR impact",
             "source": "industry benchmark", "kind": "benchmark", "strength": "moderate"},
        ],
    )


@rule("OPP-078")
def _rule_opp_078(snap: DataSnapshot) -> DetectionResult:
    """Prepare for cookie deprecation — always-on for any workspace until done."""
    return DetectionResult(
        "OPP-078", True,
        modeled_impact=500000,  # rule-of-thumb defensive value
        low_estimate=200000,
        high_estimate=1500000,
        confidence=0.70,
        rationale="Cookieless deadline Q4 2026 — every workspace needs a measurement rebuild plan",
        evidence=[
            {"statement": "Chrome 3rd-party cookie deprecation scheduled Q4 2026",
             "source": "Google public roadmap", "kind": "external", "strength": "strong"},
            {"statement": "Industry estimate: 15–25% attribution loss without mitigation",
             "source": "IAB 2024", "kind": "benchmark", "strength": "moderate"},
        ],
        external_signal_refs=["cookieless_deadline"],
    )


@rule("OPP-024")
def _rule_opp_024(snap: DataSnapshot) -> DetectionResult:
    """Launch CTV testing — Hulu/Roku/Pluto — boosted by upcoming seasonal demand."""
    ctv_channels = [ch for ch in snap.channel_spend if "ctv" in ch.lower() or "hulu" in ch.lower() or "roku" in ch.lower()]
    if ctv_channels:
        return DetectionResult("OPP-024", False, why_not="CTV already active in Acme's mix")

    # Budget sizing: 20% of linear TV OR 5% of portfolio, whichever is smaller (conservative)
    tv_spend = sum(v for ch, v in snap.channel_spend.items() if ch.lower().startswith("tv") or "television" in ch.lower())
    budget_shift = min(tv_spend * 0.20, snap.portfolio_spend * 0.05)
    if budget_shift < 50000:
        return DetectionResult("OPP-024", False, why_not="insufficient TV budget to meaningfully reallocate")

    # Expected ROI of CTV: 1.8x (conservative, on incremental spend)
    incremental_revenue = budget_shift * 1.8
    # Net benefit: incremental revenue MINUS the opportunity cost of what TV would have earned
    tv_roi = (snap.channel_revenue.get("tv_national", 0) / snap.channel_spend.get("tv_national", 1)) if snap.channel_spend.get("tv_national") else 1.0
    net = (1.8 - tv_roi) * budget_shift if tv_roi > 0 else incremental_revenue * 0.3
    if net <= 0:
        return DetectionResult("OPP-024", False, why_not=f"TV ROI {tv_roi:.2f}× already above CTV benchmark 1.8×")
    annual_impact = net * (12 / snap.lookback_months)

    boost = 1.0
    sig_refs = []
    for e in snap.upcoming_events:
        if e["direction"] == "positive" and e["weeks_out"] <= 12:
            boost = max(boost, 1.2)
            sig_refs.append(e["name"])

    return DetectionResult(
        "OPP-024", True,
        modeled_impact=annual_impact * boost,
        low_estimate=annual_impact * 0.4,
        high_estimate=annual_impact * 1.6 * boost,
        confidence=0.65,
        rationale="No CTV presence; reallocating 20% of TV budget earns incremental lift given CTV ROI benchmarks",
        evidence=[
            {"statement": f"Linear TV spend: ${tv_spend:,.0f} ({snap.lookback_months}mo); CTV not yet activated",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": f"Current TV ROI: {tv_roi:.2f}× — benchmark CTV ROI: 1.8× on test spend",
             "source": "campaign_performance + eMarketer 2024", "kind": "benchmark", "strength": "moderate"},
        ],
        external_boost=boost,
        external_signal_refs=sig_refs,
    )


@rule("OPP-050")
def _rule_opp_050(snap: DataSnapshot) -> DetectionResult:
    """Implement server-side tagging (CAPI + sGTM) to recover iOS-blocked conversions."""
    # Attribution-sensitive channels only: paid social + paid search
    meta_spend = sum(v for ch, v in snap.channel_spend.items() if "social_paid" in ch.lower() or "meta" in ch.lower() or "facebook" in ch.lower())
    google_spend = sum(v for ch, v in snap.channel_spend.items() if "paid_search" in ch.lower())
    combined = meta_spend + google_spend
    if combined < 100000:
        return DetectionResult("OPP-050", False, why_not="insufficient paid social + paid search spend to justify SSL build")

    combined_rev = sum(v for ch, v in snap.channel_revenue.items()
                       if ("social_paid" in ch.lower() or "meta" in ch.lower() or "facebook" in ch.lower() or "paid_search" in ch.lower()))
    annual_rev = combined_rev * (12 / snap.lookback_months)
    # Only ~60% of paid social/search revenue is iOS mobile; of that, 6-8% is signal loss
    ios_share = 0.60
    recovery_rate = 0.065
    recovery = annual_rev * ios_share * recovery_rate

    return DetectionResult(
        "OPP-050", True,
        modeled_impact=recovery,
        low_estimate=annual_rev * ios_share * 0.04,
        high_estimate=annual_rev * ios_share * 0.08,
        confidence=0.78,
        rationale=f"${combined:,.0f} paid social+search spend; iOS signal loss recovers ~{recovery_rate*100:.1f}% of affected revenue via CAPI+sGTM",
        evidence=[
            {"statement": f"Paid social+search spend: ${combined:,.0f} ({snap.lookback_months}mo); revenue: ${combined_rev:,.0f}",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": "iOS14.5+ mobile share ~60% of paid social/search traffic",
             "source": "Meta business summit 2024", "kind": "external", "strength": "moderate"},
            {"statement": "Post-iOS14.5 signal loss typically 6–8% of mobile conversions",
             "source": "Meta public benchmark", "kind": "external", "strength": "moderate"},
        ],
    )


@rule("OPP-083")
def _rule_opp_083(snap: DataSnapshot) -> DetectionResult:
    """Diversify vendor concentration — triggered when single channel > 35% of spend."""
    if not snap.portfolio_spend:
        return DetectionResult("OPP-083", False, why_not="no spend data")
    shares = {ch: v / snap.portfolio_spend for ch, v in snap.channel_spend.items()}
    concentrated = {ch: s for ch, s in shares.items() if s > 0.35}
    if not concentrated:
        top = max(shares, key=shares.get)
        return DetectionResult("OPP-083", False,
            why_not=f"max channel concentration {shares[top]*100:.1f}% ({top}) — below 35% threshold")

    ch = max(concentrated, key=concentrated.get)
    # Defensive value ~10% of concentrated channel spend (avoided disruption loss)
    defensive_value = snap.channel_spend[ch] * 0.10 * (12 / snap.lookback_months)
    return DetectionResult(
        "OPP-083", True,
        modeled_impact=defensive_value,
        low_estimate=defensive_value * 0.5,
        high_estimate=defensive_value * 2.0,
        confidence=0.62,
        rationale=f"{ch} at {concentrated[ch]*100:.1f}% of spend — platform/policy disruption risk",
        evidence=[
            {"statement": f"{ch}: {concentrated[ch]*100:.1f}% of total media spend",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": "2021 iOS14.5 showed $X billion impact on single-vendor-concentrated advertisers",
             "source": "industry analysis", "kind": "external", "strength": "moderate"},
        ],
    )


@rule("OPP-052")
def _rule_opp_052(snap: DataSnapshot) -> DetectionResult:
    """Renegotiate media agency contract — fires when total spend > $5M (agency-scale) as proxy.

    In real engagement we'd check agency fee vs benchmark; for demo we estimate 0.5-1% of
    eligible spend is recoverable through renegotiation.
    """
    eligible_spend = snap.portfolio_spend * (12 / snap.lookback_months)  # annualized
    if eligible_spend < 5_000_000:
        return DetectionResult("OPP-052", False, why_not=f"annual spend ${eligible_spend:,.0f} below agency renegotiation threshold ($5M)")

    # Forrester median agency fee: 1.9%. Typical retainer: 2.3-2.8%. Recovery: ~0.5%
    savings = eligible_spend * 0.005
    return DetectionResult(
        "OPP-052", True,
        modeled_impact=savings,
        low_estimate=eligible_spend * 0.002,
        high_estimate=eligible_spend * 0.010,
        confidence=0.70,
        rationale=f"${eligible_spend/1e6:.1f}M annual spend qualifies for agency fee renegotiation; typical recovery ~0.5%",
        evidence=[
            {"statement": f"Annual media spend: ${eligible_spend:,.0f}",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": "Forrester 2024 median agency fee for $5M+ accounts: 1.9%",
             "source": "Forrester Agency Benchmarks 2024", "kind": "benchmark", "strength": "moderate"},
            {"statement": "Typical renegotiation outcome: 0.2-1.0% fee reduction",
             "source": "industry surveys", "kind": "benchmark", "strength": "moderate"},
        ],
    )


@rule("OPP-043")
def _rule_opp_043(snap: DataSnapshot) -> DetectionResult:
    """Consolidate measurement stack — fires when multiple overlapping signals likely present.

    Proxy: if portfolio spend > $3M, most clients have 4+ measurement tools with overlap.
    Typical savings: 15-25% of measurement stack cost, estimated at ~1% of media spend.
    """
    annual_spend = snap.portfolio_spend * (12 / snap.lookback_months)
    if annual_spend < 3_000_000:
        return DetectionResult("OPP-043", False, why_not=f"portfolio too small (${annual_spend:,.0f}) to have stack overlap")

    savings = annual_spend * 0.01 * 0.20
    return DetectionResult(
        "OPP-043", True,
        modeled_impact=savings,
        low_estimate=savings * 0.5,
        high_estimate=savings * 1.5,
        confidence=0.65,
        rationale=f"${annual_spend/1e6:.1f}M scale typically runs 4+ measurement tools with 20% overlap",
        evidence=[
            {"statement": f"Annual media spend: ${annual_spend:,.0f}",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": "Enterprise martech stacks average 4-6 overlapping measurement/attribution tools",
             "source": "Gartner 2024", "kind": "benchmark", "strength": "moderate"},
            {"statement": "Typical consolidation saves 15-25% of stack licensing",
             "source": "MartechAdvisor surveys", "kind": "benchmark", "strength": "moderate"},
        ],
    )


@rule("OPP-062")
def _rule_opp_062(snap: DataSnapshot) -> DetectionResult:
    """Implement one-page / accelerated checkout — CX.

    Fires when online revenue > $5M annualized.
    Lift: 4-8% conversion rate on affected online revenue, net of implementation cost.
    """
    online_channels = {"paid_search", "social_paid", "display", "email", "organic_search", "video_youtube"}
    online_revenue_period = sum(v for ch, v in snap.channel_revenue.items() if ch in online_channels)
    annual_online = online_revenue_period * (12 / snap.lookback_months)
    if annual_online < 5_000_000:
        return DetectionResult("OPP-062", False, why_not=f"online revenue ${annual_online:,.0f} below checkout optimization threshold ($5M)")

    # 6% CVR lift (midpoint) on attributable revenue — but cap realistic expectation
    # Conservative: 6% of (online revenue × 30% checkout-attributable share)
    checkout_attributable = annual_online * 0.30
    lift_rate = 0.06
    gross_lift = checkout_attributable * lift_rate
    net_lift = gross_lift - 100_000  # amortized build cost

    return DetectionResult(
        "OPP-062", True,
        modeled_impact=net_lift,
        low_estimate=checkout_attributable * 0.04 - 100_000,
        high_estimate=checkout_attributable * 0.08 - 100_000,
        confidence=0.68,
        rationale=f"${annual_online/1e6:.1f}M online revenue; one-page checkout lifts CVR 4-8% on checkout-attributable flow",
        evidence=[
            {"statement": f"Online revenue: ${annual_online:,.0f} annualized",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": "Shopify / Baymard studies: one-page checkout lifts CVR 4-8% vs multi-step",
             "source": "Baymard Institute 2024", "kind": "benchmark", "strength": "strong"},
            {"statement": "Typical implementation: $300-500K (product + eng), 3-month delivery",
             "source": "industry estimates", "kind": "benchmark", "strength": "moderate"},
        ],
    )


@rule("OPP-068")
def _rule_opp_068(snap: DataSnapshot) -> DetectionResult:
    """Build comprehensive lifecycle email program — CX.

    Fires when email is active but email revenue is < 10% of total revenue.
    """
    email_spend = snap.channel_spend.get("email", 0)
    email_revenue = snap.channel_revenue.get("email", 0)
    if email_spend == 0:
        return DetectionResult("OPP-068", False, why_not="email channel not active")

    email_share_of_revenue = email_revenue / snap.portfolio_revenue if snap.portfolio_revenue else 0
    if email_share_of_revenue >= 0.10:
        return DetectionResult("OPP-068", False,
            why_not=f"email already {email_share_of_revenue*100:.1f}% of revenue — healthy program")

    annual_email_rev = email_revenue * (12 / snap.lookback_months)
    uplift = annual_email_rev * 0.40
    return DetectionResult(
        "OPP-068", True,
        modeled_impact=uplift,
        low_estimate=annual_email_rev * 0.20,
        high_estimate=annual_email_rev * 0.60,
        confidence=0.72,
        rationale=f"Email at {email_share_of_revenue*100:.1f}% of revenue — benchmark retail is 15-20%; lifecycle triggers unlock 30-50% uplift",
        evidence=[
            {"statement": f"Email revenue: ${email_revenue:,.0f} ({email_share_of_revenue*100:.1f}% of total)",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": "Retail email benchmark: 15-20% of total revenue from email program",
             "source": "Klaviyo / Litmus 2024", "kind": "benchmark", "strength": "strong"},
            {"statement": "Adding 12+ lifecycle triggers: typical 30-50% revenue uplift",
             "source": "Klaviyo customer studies", "kind": "case_study", "strength": "moderate"},
        ],
    )


@rule("OPP-070")
def _rule_opp_070(snap: DataSnapshot) -> DetectionResult:
    """Optimize site performance (Core Web Vitals) — CX.

    Fires when online revenue is material. Lift: 1-3% CVR (conservative 1.5%).
    """
    online_channels = {"paid_search", "social_paid", "display", "email", "organic_search", "video_youtube"}
    online_rev_period = sum(v for ch, v in snap.channel_revenue.items() if ch in online_channels)
    annual_online = online_rev_period * (12 / snap.lookback_months)
    if annual_online < 3_000_000:
        return DetectionResult("OPP-070", False, why_not=f"online revenue ${annual_online:,.0f} too small to prioritize speed work")

    # Site-speed-attributable share: ~40% of online revenue (mobile-heavy)
    speed_attributable = annual_online * 0.40
    lift = speed_attributable * 0.015
    return DetectionResult(
        "OPP-070", True,
        modeled_impact=lift,
        low_estimate=speed_attributable * 0.008,
        high_estimate=speed_attributable * 0.030,
        confidence=0.60,
        rationale="Core Web Vitals improvements lift mobile CVR 1-3%; applies to mobile-attributable online revenue",
        evidence=[
            {"statement": f"Online revenue exposure: ${annual_online:,.0f} annualized",
             "source": "campaign_performance", "kind": "data", "strength": "strong"},
            {"statement": "Google / Akamai: 100ms latency reduction = 1% CVR lift on mobile",
             "source": "Google / Akamai studies", "kind": "benchmark", "strength": "moderate"},
        ],
    )


# -----------------------------------------------------------------------------
# Runner
# -----------------------------------------------------------------------------

def evaluate_all(db: Session, workspace: str) -> list[DetectionResult]:
    """Evaluate every registered rule. Returns all results (fired + not-fired)."""
    snap = build_snapshot(db, lookback_months=3)
    return [rule_fn(snap) for rule_fn in RULES.values()]


def persist_detections(db: Session, workspace: str, results: list[DetectionResult]) -> int:
    """Clear prior auto-detections for this workspace, write fired ones."""
    # Clear auto-source only (preserve manual)
    db.query(DetectedOpportunity).filter_by(workspace=workspace, source="auto").delete()

    count = 0
    now = datetime.utcnow().isoformat()
    for r in results:
        if not r.fires:
            continue
        db.add(DetectedOpportunity(
            workspace=workspace,
            catalog_id=r.catalog_id,
            source="auto",
            detected_at=now,
            modeled_impact=r.modeled_impact,
            low_estimate=r.low_estimate,
            high_estimate=r.high_estimate,
            confidence_score=r.confidence,
            rationale=r.rationale,
            evidence_json=json.dumps(r.evidence),
            external_boost=r.external_boost,
            external_signal_refs=",".join(r.external_signal_refs) if r.external_signal_refs else None,
        ))
        count += 1

    db.commit()
    return count


def run_detection(db: Session, workspace: str) -> dict:
    """Full pipeline: evaluate + persist. Returns summary."""
    results = evaluate_all(db, workspace)
    fired = [r for r in results if r.fires]
    n = persist_detections(db, workspace, results)
    return {
        "rules_evaluated": len(results),
        "rules_fired": len(fired),
        "detections_persisted": n,
        "total_impact_modeled": sum(r.modeled_impact for r in fired),
        "unfired": [{"catalog_id": r.catalog_id, "why_not": r.why_not} for r in results if not r.fires],
    }
