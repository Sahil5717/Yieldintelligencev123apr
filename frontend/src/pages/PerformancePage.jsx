import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import clsx from "clsx";

import { getPerformance } from "../api/client";
import { fmtMoney, fmtX, fmtPct } from "../lib/format";

const STATUS_META = {
  losing_money: { label: "Losing money", color: "bg-cost-tint text-cost" },
  past_peak: { label: "Past peak", color: "bg-amber-bg text-amber-deep" },
  on_frontier: { label: "On frontier", color: "bg-opt-tint text-opt-ink" },
  headroom: { label: "Headroom", color: "bg-revenue-tint text-revenue" },
};

export default function PerformancePage() {
  const { data, isLoading } = useQuery({ queryKey: ["performance"], queryFn: getPerformance });
  const [selectedChannel, setSelectedChannel] = useState(null);

  if (isLoading) return <div className="p-8 text-ash-500 text-sm">Loading performance…</div>;
  if (!data) return null;

  const pareto = data.pareto || [];
  const frontier = data.frontier_status || {};
  const curves = data.response_curves || {};

  const activeChannel = selectedChannel || (pareto[0] && pareto[0].channel);
  const curveData = curves[activeChannel];
  const chartData = curveData
    ? curveData.spend.map((s, i) => ({
        spend: s,
        response: curveData.response[i],
        marginal: curveData.marginal_roi[i],
      }))
    : [];

  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
      <div className="text-[11px] text-ash-500 font-medium">Channel performance · diagnose mode</div>
      <div className="text-[22px] font-bold text-ink mt-0.5 mb-2 tracking-tight">Performance</div>
      <div className="text-[12px] text-ash-600 mb-5">
        {data.totals.channels_analyzed} channels · ${(data.totals.spend / 1e6).toFixed(1)}M spend ·{" "}
        ${(data.totals.revenue / 1e6).toFixed(1)}M revenue · ROI {fmtX(data.totals.roi)}
      </div>

      {/* Pareto */}
      <div className="card p-4 mb-4">
        <div className="flex justify-between items-baseline mb-3">
          <div>
            <div className="section-title">Revenue Pareto</div>
            <div className="text-[10.5px] text-ash-500">Last 3 months · cumulative share</div>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={pareto} margin={{ top: 5, right: 20, left: 10, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#EDEEF5" vertical={false} />
            <XAxis
              dataKey="channel"
              tick={{ fontSize: 10, fill: "#8C92AC" }}
              axisLine={{ stroke: "#E5E7EF" }}
              tickLine={false}
              angle={-25}
              textAnchor="end"
              height={40}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#8C92AC" }}
              axisLine={{ stroke: "#E5E7EF" }}
              tickLine={false}
              tickFormatter={(v) => `$${(v / 1e6).toFixed(0)}M`}
            />
            <Tooltip
              contentStyle={{ background: "#0F1535", border: "none", borderRadius: 6, color: "white", fontSize: 11 }}
              formatter={(v) => `$${v.toLocaleString()}`}
            />
            <Bar dataKey="revenue" fill="#7C5CFF" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid md:grid-cols-[1fr_1.3fr] gap-4">
        {/* Efficient frontier — per-channel status */}
        <div className="card p-4">
          <div className="section-title mb-3">Efficient frontier</div>
          <div className="space-y-1.5">
            {Object.entries(frontier)
              .sort(([, a], [, b]) => b.marginal_roi - a.marginal_roi)
              .map(([ch, info]) => {
                const meta = STATUS_META[info.status] || {};
                return (
                  <button
                    key={ch}
                    onClick={() => setSelectedChannel(ch)}
                    className={clsx(
                      "w-full text-left flex items-center justify-between px-3 py-2 rounded-md border transition-colors",
                      activeChannel === ch
                        ? "bg-ash-100 border-ink"
                        : "border-ash-200 hover:border-ash-400"
                    )}
                  >
                    <div>
                      <div className="text-[11.5px] font-medium text-ink">{ch}</div>
                      <div className="text-[10px] text-ash-500 mt-0.5">
                        ${info.monthly_spend.toLocaleString()}/mo
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={clsx("pill", meta.color)}>{meta.label}</span>
                      <span className="text-[11px] money text-ink w-12 text-right">
                        {info.marginal_roi.toFixed(2)}×
                      </span>
                    </div>
                  </button>
                );
              })}
          </div>
        </div>

        {/* Response curve for selected channel */}
        <div className="card p-4">
          <div className="flex justify-between items-baseline mb-3">
            <div>
              <div className="section-title">Response curve: {activeChannel}</div>
              <div className="text-[10.5px] text-ash-500">
                Current spend: {fmtMoney(curveData?.current_spend || 0)}
              </div>
            </div>
          </div>
          {curveData && (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDEEF5" vertical={false} />
                <XAxis
                  dataKey="spend"
                  tick={{ fontSize: 10, fill: "#8C92AC" }}
                  axisLine={{ stroke: "#E5E7EF" }}
                  tickLine={false}
                  tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#8C92AC" }}
                  axisLine={{ stroke: "#E5E7EF" }}
                  tickLine={false}
                  tickFormatter={(v) => `$${(v / 1e6).toFixed(1)}M`}
                />
                <Tooltip
                  contentStyle={{ background: "#0F1535", border: "none", borderRadius: 6, color: "white", fontSize: 11 }}
                  formatter={(v, k) => (k === "response" ? `$${v.toLocaleString()}` : v.toFixed(2))}
                  labelFormatter={(v) => `Spend: $${v.toLocaleString()}`}
                />
                <ReferenceLine
                  x={curveData.current_spend}
                  stroke="#7C5CFF"
                  strokeDasharray="4 4"
                  label={{ value: "now", position: "top", fontSize: 10, fill: "#7C5CFF" }}
                />
                <Line
                  type="monotone"
                  dataKey="response"
                  stroke="#0F1535"
                  strokeWidth={2.5}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
          <div className="text-[10px] text-ash-500 italic mt-2">
            Model: {data.mmm_method === "bootstrap_ridge" ? "bootstrap ridge (synthetic)" : "Bayesian MMM"}
          </div>
        </div>
      </div>
    </div>
  );
}
