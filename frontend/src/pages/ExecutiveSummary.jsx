import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import clsx from "clsx";

import { getExecSummary, getOpportunities } from "../api/client";
import { fmtMoney, fmtPct, fmtX } from "../lib/format";
import { useTray } from "../hooks/useTray";

// Pillar metadata — colors, labels, associated actions
const PILLARS = [
  { key: "revenue", label: "Revenue uplift", chipBg: "bg-revenue-tint", chipText: "text-revenue" },
  { key: "cost", label: "Cost efficiency", chipBg: "bg-cost-tint", chipText: "text-cost" },
  { key: "cx", label: "Customer experience", chipBg: "bg-cx-tint", chipText: "text-cx" },
];

// --- Sub-components ----------------------------------------------------------

function Hero({ total, optTotal, transTotal, optCount, transCount }) {
  return (
    <div
      className="rounded-2xl p-8 text-white relative overflow-hidden"
      style={{
        background:
          "linear-gradient(135deg, #0F1535 0%, #1E2456 62%, #2D2C6E 100%)",
      }}
    >
      <div
        className="absolute -right-16 -top-16 w-80 h-80 rounded-full"
        style={{
          background:
            "radial-gradient(circle, rgba(124,92,255,.35), transparent 70%)",
        }}
      />
      <div className="relative">
        <div className="text-[10px] text-purple-tint/70 font-bold uppercase tracking-[0.18em] mb-2">
          Yield Intelligence
        </div>
        <div className="font-serif text-[28px] leading-[1.25] font-medium max-w-3xl">
          There's <span className="italic font-semibold text-[#86EFAC]">{fmtMoney(total, { compact: true })}</span>{" "}
          on the table across your portfolio.{" "}
          <span className="text-white/70 text-[22px]">
            <span className="italic text-[#9D7DFF]">{fmtMoney(optTotal, { compact: true })}</span> can move this quarter,{" "}
            <span className="italic text-[#9D7DFF]">{fmtMoney(transTotal, { compact: true })}</span> compounds over time.
          </span>
        </div>
        <div className="text-[12px] text-white/60 mt-4 flex items-center gap-4">
          <span>
            <span className="text-white">{optCount}</span> optimization moves
          </span>
          <span className="text-white/30">·</span>
          <span>
            <span className="text-white">{transCount}</span> transformation plays
          </span>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ label, value, delta, deltaPct, unit, isInverse }) {
  // isInverse: for CAC, lower is better
  const deltaValue = delta ?? deltaPct;
  const positiveColor = isInverse ? "text-revenue" : "text-revenue";
  const negativeColor = isInverse ? "text-cost" : "text-cost";
  const isPositive = isInverse ? deltaValue < 0 : deltaValue > 0;

  return (
    <div className="card p-5">
      <div className="text-[10.5px] text-ash-500 uppercase tracking-wider font-semibold">
        {label}
      </div>
      <div className="money text-[28px] text-ink mt-1.5">
        {value}
        {unit && <span className="text-[18px] text-ash-500 font-normal not-italic ml-1">{unit}</span>}
      </div>
      {deltaValue != null && (
        <div
          className={clsx(
            "flex items-center gap-1 text-[11px] font-semibold mt-1",
            isPositive ? positiveColor : negativeColor
          )}
        >
          {isPositive ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
          {deltaPct != null
            ? fmtPct(Math.abs(deltaPct), { decimals: 1 })
            : fmtX(Math.abs(delta))}
          <span className="text-ash-500 font-normal">vs prior qtr</span>
        </div>
      )}
    </div>
  );
}

function PillarCard({ pillar, opportunities }) {
  const { selected, toggle } = useTray();
  const navigate = useNavigate();

  // Split by motion
  const optActions = opportunities.filter((o) => o.motion === "optimization");
  const transActions = opportunities.filter((o) => o.motion === "transformation");
  const totalImpact = opportunities.reduce((s, o) => s + (o.modeled_impact || 0), 0);

  return (
    <div className="card flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-ash-100 flex items-center justify-between">
        <div>
          <div className={clsx("text-[10px] font-bold uppercase tracking-wider", pillar.chipText)}>
            {pillar.label}
          </div>
          <div className="money text-[22px] text-ink mt-0.5">
            {fmtMoney(totalImpact, { compact: true })}
          </div>
        </div>
        <div className="text-right text-[10.5px] text-ash-500">
          {opportunities.length}{" "}
          {opportunities.length === 1 ? "action" : "actions"}
        </div>
      </div>

      {/* Optimization band */}
      {optActions.length > 0 && (
        <div className="bg-opt-tint/50">
          <div className="px-4 py-2 text-[9.5px] text-opt-ink font-bold uppercase tracking-wider border-b border-cx-tint">
            Optimization · this quarter
          </div>
          {optActions.map((opp) => (
            <ActionRow key={opp.catalog_id} opp={opp} selected={selected} toggle={toggle} />
          ))}
        </div>
      )}

      {/* Transformation band */}
      {transActions.length > 0 && (
        <div className="bg-trans-tint/50">
          <div className="px-4 py-2 text-[9.5px] text-trans-ink font-bold uppercase tracking-wider border-b border-purple-tint">
            Transformation · compounds over time
          </div>
          {transActions.map((opp) => (
            <ActionRow key={opp.catalog_id} opp={opp} selected={selected} toggle={toggle} />
          ))}
        </div>
      )}

      {opportunities.length === 0 && (
        <div className="p-4 text-[11px] text-ash-500 italic text-center">
          No opportunities detected for this pillar this quarter
        </div>
      )}

      <div className="flex-1 px-4 py-3 flex items-center justify-between border-t border-ash-100 bg-white">
        <button
          onClick={() => navigate(`/opportunities?pillar=${pillar.key}`)}
          className="text-[10.5px] text-purple font-semibold hover:text-purple-deep"
        >
          See all {pillar.label.toLowerCase()} →
        </button>
      </div>
    </div>
  );
}

function ActionRow({ opp, selected, toggle }) {
  const isChecked = selected.has(opp.action_id ?? opp.catalog_id);
  // Note: Exec Summary uses catalog_id since actions list is fetched separately.
  // Wire to scenario via action_id when available.
  const key = opp.action_id ?? opp.catalog_id;

  return (
    <div className="px-4 py-2.5 border-b border-white/60 last:border-b-0 hover:bg-white/40 transition-colors">
      <div className="flex items-start gap-2.5">
        <input
          type="checkbox"
          checked={isChecked}
          onChange={() => toggle(key)}
          className="mt-0.5 w-3 h-3 rounded accent-purple cursor-pointer"
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="text-[12px] text-ink font-medium leading-tight">{opp.name}</div>
            <div className="money-green text-[13px] whitespace-nowrap">
              {fmtMoney(opp.modeled_impact, { compact: true, withSign: true })}
            </div>
          </div>
          <div className="text-[10px] text-ash-500 mt-0.5 why">{opp.rationale}</div>
          <div className="flex items-center gap-2 text-[9.5px] text-ash-500 mt-1">
            <span>conf {Math.round((opp.confidence || 0) * 100)}%</span>
            {opp.external_boost > 1.0 && (
              <>
                <span className="text-ash-300">·</span>
                <span className="text-amber-deep font-medium">
                  boosted: {opp.external_signal_refs.join(", ")}
                </span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MarketTrendsStrip({ trends }) {
  if (!trends || trends.length === 0) return null;
  return (
    <div className="card p-4">
      <div className="section-title mb-3">Market trends</div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {trends.map((t, i) => (
          <div key={i} className="flex items-start gap-2 text-[11px]">
            <div
              className={clsx(
                "w-1.5 h-1.5 rounded-full mt-1.5 shrink-0",
                t.direction === "positive" && "bg-revenue",
                t.direction === "negative" && "bg-cost",
                t.direction === "neutral" && "bg-ash-400",
                t.direction === "warning" && "bg-amber"
              )}
            />
            <div className="flex-1 min-w-0">
              <div className="font-medium text-ink leading-tight">{t.name}</div>
              <div className="text-ash-500 text-[10px] mt-0.5">{t.when}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RoiTrendChart({ kpis }) {
  // For v1 demo we synthesize a simple trailing chart from baseline KPIs since
  // the backend doesn't yet expose time-series. This is honest and clearly
  // labeled — replace with real data when /v1/kpis-trend is added.
  const [metric, setMetric] = useState("roi");
  const metrics = [
    { key: "roi", label: "ROI", unit: "×" },
    { key: "revenue", label: "Revenue", unit: "$" },
    { key: "spend", label: "Spend", unit: "$" },
    { key: "cac", label: "CAC", unit: "$" },
  ];

  // Synthesize 12 months of data around current KPIs with small variation
  const currentValue = kpis?.[metric] ?? 0;
  const data = Array.from({ length: 12 }, (_, i) => {
    const factor = 0.92 + i * 0.015 + (Math.sin(i) * 0.03);
    return {
      month: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][i],
      value: Math.round(currentValue * factor * 100) / 100,
    };
  });

  const benchmark = currentValue * 0.95;

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="section-title">12-month trend</div>
        <div className="flex gap-1 text-[11px]">
          {metrics.map((m) => (
            <button
              key={m.key}
              onClick={() => setMetric(m.key)}
              className={clsx(
                "px-2.5 py-1 rounded-md font-medium transition-colors",
                metric === m.key ? "bg-ink text-white" : "text-ash-500 hover:text-ink hover:bg-ash-100"
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 10, right: 10, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#EDEEF5" vertical={false} />
          <XAxis
            dataKey="month"
            tick={{ fontSize: 10, fill: "#8C92AC" }}
            axisLine={{ stroke: "#E5E7EF" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#8C92AC" }}
            axisLine={{ stroke: "#E5E7EF" }}
            tickLine={false}
            tickFormatter={(v) => {
              if (metric === "roi") return `${v.toFixed(1)}×`;
              if (metric === "revenue") return `$${(v / 1_000_000).toFixed(0)}M`;
              if (metric === "spend") return `$${(v / 1_000_000).toFixed(0)}M`;
              if (metric === "cac") return `$${Math.round(v / 1000)}K`;
              return v;
            }}
          />
          <Tooltip
            contentStyle={{
              background: "#0F1535",
              border: "none",
              borderRadius: 6,
              color: "white",
              fontSize: 11,
            }}
          />
          <ReferenceLine
            y={benchmark}
            stroke="#B5BACB"
            strokeDasharray="3 3"
            label={{
              value: "benchmark",
              position: "right",
              fontSize: 10,
              fill: "#8C92AC",
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke="#7C5CFF"
            strokeWidth={2.5}
            dot={{ r: 3, fill: "#7C5CFF" }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="text-[10px] text-ash-500 italic mt-2">
        Synthetic 12-month view — replace with real time-series when the backend exposes trend data.
      </div>
    </div>
  );
}

// --- Main page ---------------------------------------------------------------

export default function ExecutiveSummary() {
  const { data: summary, isLoading, error } = useQuery({
    queryKey: ["execSummary"],
    queryFn: () => getExecSummary(),
  });
  const { data: opportunities = [] } = useQuery({
    queryKey: ["opportunities"],
    queryFn: () => getOpportunities(),
  });

  if (isLoading) return <div className="p-8 text-ash-500 text-sm">Loading executive summary…</div>;
  if (error) return <div className="p-8 text-cost text-sm">Error: {error.message}</div>;
  if (!summary) return null;

  const opsByPillar = (pillarKey) => opportunities.filter((o) => o.pillar === pillarKey);

  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
      {/* Hero */}
      <Hero
        total={summary.total_on_table}
        optTotal={summary.optimization_total}
        transTotal={summary.transformation_total}
        optCount={summary.optimization_action_count}
        transCount={summary.transformation_action_count}
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-6">
        <KpiCard
          label="Revenue (annual)"
          value={fmtMoney(summary.kpis.revenue, { compact: true })}
          deltaPct={summary.kpis.revenue_delta_pct}
        />
        <KpiCard
          label="Portfolio ROI"
          value={fmtX(summary.kpis.roi)}
          delta={summary.kpis.roi_delta}
        />
        <KpiCard
          label="Spend (annual)"
          value={fmtMoney(summary.kpis.spend, { compact: true })}
          deltaPct={summary.kpis.spend_delta_pct}
          isInverse
        />
        <KpiCard
          label="CAC"
          value={fmtMoney(summary.kpis.cac)}
          deltaPct={summary.kpis.cac_delta_pct}
          isInverse
        />
      </div>

      {/* Pillar cards row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
        {PILLARS.map((p) => (
          <PillarCard key={p.key} pillar={p} opportunities={opsByPillar(p.key)} />
        ))}
      </div>

      {/* Worth-knowing alert */}
      {summary.model_confidence < 0.8 && (
        <div className="mt-5 bg-amber-bg border border-amber-border rounded-lg px-4 py-3 flex gap-3 items-start">
          <AlertTriangle size={14} className="text-amber-deep mt-0.5 shrink-0" />
          <div className="text-[12px] text-amber-ink">
            <span className="font-semibold">Worth knowing:</span> portfolio model confidence is{" "}
            {Math.round(summary.model_confidence * 100)}%. Some CTV and attribution signals rely on
            external benchmarks rather than your data. Drill into any opportunity to see its evidence chain.
          </div>
        </div>
      )}

      {/* Market trends + trend chart */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-5">
        <div className="md:col-span-1">
          <MarketTrendsStrip trends={summary.market_trends} />
        </div>
        <div className="md:col-span-2">
          <RoiTrendChart kpis={summary.kpis} />
        </div>
      </div>
    </div>
  );
}
