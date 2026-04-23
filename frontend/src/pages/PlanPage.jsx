import { useQuery } from "@tanstack/react-query";
import { useSearchParams, useNavigate } from "react-router-dom";
import { getScenario } from "../api/client";
import { fmtMoney, fmtX, fmtPct, humanPillar } from "../lib/format";
import clsx from "clsx";

export default function PlanPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const scenarioId = params.get("scenario");

  const { data: scenario, isLoading } = useQuery({
    queryKey: ["scenario", scenarioId],
    queryFn: () => getScenario(scenarioId),
    enabled: !!scenarioId,
  });

  if (!scenarioId) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
        <div className="text-[11px] text-ash-500 font-medium">Commit mode</div>
        <div className="text-[22px] font-bold text-ink mt-0.5 mb-5 tracking-tight">Plan</div>
        <div className="card p-8 text-center">
          <div className="text-[14px] text-ink font-medium mb-2">No scenario committed yet</div>
          <div className="text-[12px] text-ash-500 mb-4">
            Select actions on Opportunities, then commit from Simulate.
          </div>
          <button
            onClick={() => navigate("/opportunities")}
            className="text-[11px] bg-purple text-white px-4 py-2 rounded-md font-semibold hover:bg-purple-deep"
          >
            Go to Opportunities →
          </button>
        </div>
      </div>
    );
  }

  if (isLoading) return <div className="p-8 text-ash-500 text-sm">Loading plan…</div>;
  if (!scenario) return null;

  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
      <div className="text-[11px] text-ash-500 font-medium">Commit mode · scenario {scenario.scenario_id}</div>
      <div className="text-[22px] font-bold text-ink mt-0.5 mb-1 tracking-tight">{scenario.name}</div>
      <div className="text-[12px] text-ash-600 mb-5">
        Status:{" "}
        <span className="pill bg-amber-bg text-amber-ink capitalize">{scenario.status}</span>
      </div>

      {/* Baseline vs projected */}
      <div className="grid md:grid-cols-4 gap-3 mb-5">
        <div className="card p-4">
          <div className="text-[10.5px] text-ash-500 uppercase tracking-wider font-semibold">
            Baseline revenue
          </div>
          <div className="money text-[22px] text-ink mt-1">
            {fmtMoney(scenario.baseline.revenue, { compact: true })}
          </div>
        </div>
        <div className="card p-4 bg-revenue-tint/30">
          <div className="text-[10.5px] text-revenue uppercase tracking-wider font-semibold">
            Projected revenue
          </div>
          <div className="money text-[22px] text-revenue mt-1">
            {fmtMoney(scenario.projected.revenue, { compact: true })}
          </div>
          <div className="text-[11px] text-revenue font-semibold mt-1">
            {fmtMoney(scenario.deltas.revenue_abs, { compact: true, withSign: true })} ·{" "}
            {fmtPct(scenario.deltas.revenue_pct, { withSign: true })}
          </div>
        </div>
        <div className="card p-4">
          <div className="text-[10.5px] text-ash-500 uppercase tracking-wider font-semibold">
            Projected ROI
          </div>
          <div className="money text-[22px] text-ink mt-1">{fmtX(scenario.projected.roi)}</div>
          <div className="text-[11px] text-ash-500 mt-1">
            from {fmtX(scenario.baseline.roi)} ({fmtX(scenario.deltas.roi_delta)})
          </div>
        </div>
        <div className="card p-4">
          <div className="text-[10.5px] text-ash-500 uppercase tracking-wider font-semibold">
            Portfolio confidence
          </div>
          <div className="money text-[22px] text-ink mt-1">
            {fmtPct(scenario.portfolio_confidence * 100, { decimals: 0 })}
          </div>
        </div>
      </div>

      {/* Actions with placeholders for owner + dates */}
      <div className="card p-4">
        <div className="section-title mb-3">Plan items · {scenario.action_count} actions</div>
        <div className="text-[10.5px] text-ash-500 italic mb-3 pb-3 border-b border-ash-100">
          Owners + dates shown as placeholders for v1. In v2 these sync to Asana/Jira.
        </div>
        <div>
          <div className="grid grid-cols-[1fr_100px_100px_100px_100px] gap-3 text-[10px] text-ash-500 font-bold uppercase tracking-wider pb-2 border-b border-ash-200">
            <div>Action</div>
            <div>Pillar</div>
            <div>Owner</div>
            <div className="text-right">Start</div>
            <div className="text-right">Impact</div>
          </div>
          {scenario.actions.map((a) => (
            <div
              key={a.action_id}
              className="grid grid-cols-[1fr_100px_100px_100px_100px] gap-3 items-center py-2.5 border-b border-ash-100 text-[12px] last:border-b-0"
            >
              <div className="min-w-0">
                <div className="text-ink font-medium">{a.name}</div>
                {a.has_override && (
                  <div className="text-[10px] text-amber-deep italic mt-0.5">
                    Override: {a.override_reason}
                  </div>
                )}
              </div>
              <div>
                <span
                  className={clsx(
                    "pill",
                    a.pillar === "revenue" && "bg-revenue-tint text-revenue",
                    a.pillar === "cost" && "bg-cost-tint text-cost",
                    a.pillar === "cx" && "bg-cx-tint text-cx",
                    a.pillar === "risk" && "bg-risk-tint text-risk"
                  )}
                >
                  {humanPillar(a.pillar)}
                </span>
              </div>
              <div className="text-ash-500 italic text-[10.5px]">unassigned</div>
              <div className="text-ash-500 italic text-[10.5px] text-right">TBD</div>
              <div
                className={clsx(
                  "text-right money text-[13px]",
                  a.has_override ? "text-amber-deep" : "text-revenue"
                )}
              >
                {fmtMoney(a.effective_impact, { compact: true, withSign: true })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
