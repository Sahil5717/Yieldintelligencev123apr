import { useQuery, useMutation } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  CartesianGrid,
} from "recharts";
import { Play, Lock, Unlock } from "lucide-react";
import clsx from "clsx";

import { getActions, runOptimize, createScenario } from "../api/client";
import { useTray } from "../hooks/useTray";
import { fmtMoney, fmtX, fmtPct, humanPillar } from "../lib/format";

export default function SimulatePage() {
  const { selected } = useTray();
  const navigate = useNavigate();
  const { data: actions = [] } = useQuery({ queryKey: ["actions"], queryFn: () => getActions() });
  const selectedActions = actions.filter((a) => selected.has(a.action_id));

  const [budgetMult, setBudgetMult] = useState(100); // % of current
  const [lockedChannels, setLockedChannels] = useState({});

  const optimizeMutation = useMutation({
    mutationFn: (body) => runOptimize(body),
  });
  const commitMutation = useMutation({
    mutationFn: (body) => createScenario(body),
    onSuccess: (data) => {
      navigate(`/plan?scenario=${data.scenario_id}`);
    },
  });

  const totalImpact = selectedActions.reduce((s, a) => s + (a.effective_impact || 0), 0);
  const confidenceWeighted = selectedActions.reduce(
    (s, a) => s + (a.effective_impact || 0) * (a.effective_confidence || 0),
    0
  );
  const avgConfidence =
    selectedActions.length && totalImpact ? confidenceWeighted / totalImpact : 0;

  const runSim = () => {
    optimizeMutation.mutate({
      total_budget: null, // use current if not overridden
      min_spend_pct: 0.25,
      max_spend_pct: 2.5,
      locked_channels: Object.keys(lockedChannels).length ? lockedChannels : null,
    });
  };

  const commitScenario = () => {
    commitMutation.mutate({
      name: `Plan ${new Date().toLocaleDateString()}`,
      description: `${selectedActions.length} actions, $${(totalImpact / 1e6).toFixed(1)}M modeled impact`,
      action_ids: selectedActions.map((a) => a.action_id),
    });
  };

  const optData = optimizeMutation.data;
  const allocationChart = useMemo(() => {
    if (!optData) return [];
    const channels = Object.keys(optData.allocation);
    return channels.map((ch) => ({
      channel: ch,
      current: optData.current[ch] || 0,
      optimized: optData.allocation[ch],
      diff: (optData.allocation[ch] || 0) - (optData.current[ch] || 0),
    }));
  }, [optData]);

  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
      <div className="text-[11px] text-ash-500 font-medium">Scenario composer · compose mode</div>
      <div className="text-[22px] font-bold text-ink mt-0.5 mb-5 tracking-tight">Simulate</div>

      {selectedActions.length === 0 ? (
        <div className="card p-8 text-center">
          <div className="text-[14px] text-ink font-medium mb-2">No actions selected yet</div>
          <div className="text-[12px] text-ash-500 mb-4">
            Go to Opportunities and check any row to add it to the scenario tray.
          </div>
          <button
            onClick={() => navigate("/opportunities")}
            className="text-[11px] bg-purple text-white px-4 py-2 rounded-md font-semibold hover:bg-purple-deep"
          >
            Browse opportunities →
          </button>
        </div>
      ) : (
        <>
          {/* Selected actions summary */}
          <div className="grid md:grid-cols-[2fr_1fr] gap-4 mb-4">
            <div className="card p-4">
              <div className="section-title mb-3">Your scenario ({selectedActions.length} actions)</div>
              <div className="space-y-2">
                {selectedActions.map((a) => (
                  <div
                    key={a.action_id}
                    className="flex justify-between items-center py-2 border-b border-ash-100 last:border-b-0"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-[12px] text-ink font-medium">{a.name}</div>
                      <div className="text-[10px] text-ash-500 mt-0.5">
                        <span className="pill bg-ash-100 text-ash-600 mr-1">{humanPillar(a.pillar)}</span>
                        <span className="pill bg-ash-100 text-ash-600 mr-1">{a.motion}</span>
                        conf {Math.round((a.effective_confidence || 0) * 100)}%
                      </div>
                    </div>
                    <div
                      className={clsx(
                        "text-[13px] money whitespace-nowrap",
                        a.has_override ? "text-amber-deep" : "text-revenue"
                      )}
                    >
                      {fmtMoney(a.effective_impact, { compact: true, withSign: true })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card p-4">
              <div className="section-title mb-3">Portfolio impact</div>
              <div className="text-[10.5px] text-ash-500 uppercase tracking-wider font-bold mb-1">
                Total modeled
              </div>
              <div className="money text-[30px] text-revenue mb-3">
                {fmtMoney(totalImpact, { compact: true, withSign: true })}
              </div>
              <div className="space-y-2 text-[11.5px]">
                <div className="flex justify-between">
                  <span className="text-ash-600">Confidence weighted</span>
                  <span className="font-semibold text-ink">{fmtPct(avgConfidence * 100, { decimals: 0 })}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ash-600">Optimization actions</span>
                  <span className="font-semibold text-ink">
                    {selectedActions.filter((a) => a.motion === "optimization").length}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ash-600">Transformation plays</span>
                  <span className="font-semibold text-ink">
                    {selectedActions.filter((a) => a.motion === "transformation").length}
                  </span>
                </div>
              </div>
              <button
                onClick={commitScenario}
                disabled={commitMutation.isPending}
                className="w-full mt-4 bg-ink text-white text-[12px] py-2 rounded-md font-semibold hover:bg-ink-2"
              >
                {commitMutation.isPending ? "Creating plan…" : "Commit to Plan →"}
              </button>
            </div>
          </div>

          {/* Portfolio optimizer */}
          <div className="card p-4">
            <div className="flex justify-between items-baseline mb-3">
              <div>
                <div className="section-title">Portfolio optimizer</div>
                <div className="text-[10.5px] text-ash-500">
                  Find optimal channel allocation using MMM response curves
                </div>
              </div>
              <button
                onClick={runSim}
                disabled={optimizeMutation.isPending}
                className="text-[11px] bg-purple text-white px-3 py-1.5 rounded-md font-semibold hover:bg-purple-deep flex items-center gap-1"
              >
                <Play size={11} />
                {optimizeMutation.isPending ? "Optimizing…" : "Run optimizer"}
              </button>
            </div>

            {optData && (
              <>
                <div className="grid grid-cols-3 gap-3 mb-4 p-3 bg-ash-50 rounded-md">
                  <div>
                    <div className="text-[9.5px] text-ash-500 uppercase tracking-wider font-bold">
                      Total budget
                    </div>
                    <div className="money text-[16px] text-ink">
                      {fmtMoney(optData.total_budget, { compact: true })}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9.5px] text-ash-500 uppercase tracking-wider font-bold">
                      Expected revenue
                    </div>
                    <div className="money text-[16px] text-revenue">
                      {fmtMoney(optData.expected_revenue, { compact: true })}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9.5px] text-ash-500 uppercase tracking-wider font-bold">
                      Status
                    </div>
                    <div className="money text-[16px] text-ink">
                      {optData.converged ? "✓ Converged" : "⚠ Did not converge"}
                    </div>
                  </div>
                </div>

                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={allocationChart} margin={{ top: 10, right: 10, left: 10, bottom: 40 }}>
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
                      tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                    />
                    <Tooltip
                      contentStyle={{ background: "#0F1535", border: "none", borderRadius: 6, color: "white", fontSize: 11 }}
                      formatter={(v) => `$${v.toLocaleString()}`}
                    />
                    <Bar dataKey="current" fill="#B5BACB" name="Current" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="optimized" name="Optimized" radius={[3, 3, 0, 0]}>
                      {allocationChart.map((e, i) => (
                        <Cell key={i} fill={e.diff > 0 ? "#7C5CFF" : "#F59E0B"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </>
            )}

            {!optData && !optimizeMutation.isPending && (
              <div className="text-center text-[11px] text-ash-500 py-8">
                Click "Run optimizer" to compute optimal channel allocation.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
