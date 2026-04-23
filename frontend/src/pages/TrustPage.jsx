import { useQuery } from "@tanstack/react-query";
import { getMarkovAttribution, getShapleyAttribution, getMmmSummary } from "../api/client";
import { fmtPct } from "../lib/format";
import { ShieldCheck, AlertTriangle } from "lucide-react";
import clsx from "clsx";

function AttributionBar({ label, markov, shapley }) {
  const pct = Math.max(markov || 0, shapley || 0) * 100;
  return (
    <div className="py-2 border-b border-ash-100 last:border-b-0">
      <div className="flex justify-between items-baseline text-[11px] mb-1">
        <div className="font-medium text-ink">{label}</div>
        <div className="text-ash-500 flex gap-3">
          <span>
            Markov <span className="text-ink font-semibold">{fmtPct((markov || 0) * 100, { decimals: 1 })}</span>
          </span>
          <span>
            Shapley <span className="text-ink font-semibold">{fmtPct((shapley || 0) * 100, { decimals: 1 })}</span>
          </span>
        </div>
      </div>
      <div className="flex gap-1 h-2">
        <div className="flex-1 bg-ash-100 rounded-sm overflow-hidden">
          <div className="h-full bg-cx" style={{ width: `${(markov || 0) * 100 * (100 / pct)}%` }} />
        </div>
        <div className="flex-1 bg-ash-100 rounded-sm overflow-hidden">
          <div className="h-full bg-purple" style={{ width: `${(shapley || 0) * 100 * (100 / pct)}%` }} />
        </div>
      </div>
    </div>
  );
}

export default function TrustPage() {
  const { data: markov } = useQuery({ queryKey: ["markov"], queryFn: getMarkovAttribution });
  const { data: shapley } = useQuery({ queryKey: ["shapley"], queryFn: () => getShapleyAttribution(8) });
  const { data: mmm } = useQuery({ queryKey: ["mmm"], queryFn: getMmmSummary });

  const markovCredit = markov?.credit || {};
  const shapleyCredit = shapley?.credit || {};
  const allChannels = Array.from(new Set([...Object.keys(markovCredit), ...Object.keys(shapleyCredit)])).sort(
    (a, b) => (markovCredit[b] || 0) - (markovCredit[a] || 0)
  );

  const mmmMethod = mmm?.diagnostics?.method || "bayesian_pymc";
  const converged = mmm?.diagnostics?.converged;

  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
      <div className="text-[11px] text-ash-500 font-medium">Attribution & Trust · defend mode</div>
      <div className="text-[22px] font-bold text-ink mt-0.5 mb-5 tracking-tight">Trust</div>

      <div className="grid md:grid-cols-[1fr_1fr] gap-4 mb-4">
        {/* MMM diagnostics */}
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <ShieldCheck size={16} className="text-revenue" />
            <div className="section-title">MMM diagnostics</div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-[11px]">
            <div>
              <div className="text-ash-500 uppercase tracking-wider text-[9.5px] font-bold mb-1">Method</div>
              <div className="text-ink font-medium">
                {mmmMethod === "bootstrap_ridge" ? "Bootstrap ridge (synthetic)" : "Bayesian PyMC"}
              </div>
            </div>
            <div>
              <div className="text-ash-500 uppercase tracking-wider text-[9.5px] font-bold mb-1">Channels</div>
              <div className="text-ink font-medium">{mmm?.channels?.length || 0}</div>
            </div>
            <div>
              <div className="text-ash-500 uppercase tracking-wider text-[9.5px] font-bold mb-1">Draws</div>
              <div className="text-ink font-medium">{mmm?.diagnostics?.n_draws || 0}</div>
            </div>
            <div>
              <div className="text-ash-500 uppercase tracking-wider text-[9.5px] font-bold mb-1">Converged</div>
              <div className={clsx("font-medium", converged ? "text-revenue" : "text-cost")}>
                {converged ? "Yes" : "Pending real fit"}
              </div>
            </div>
          </div>
          {mmmMethod === "bootstrap_ridge" && (
            <div className="mt-3 p-2.5 bg-amber-bg border border-amber-border rounded text-[11px] text-amber-ink flex gap-2">
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <div>
                This deployment uses a synthetic bootstrap fallback. Run{" "}
                <code className="bg-white/60 px-1 rounded text-[10.5px]">python scripts/fit_mmm.py</code> for real
                Bayesian MMM.
              </div>
            </div>
          )}
        </div>

        {/* Overall trust score */}
        <div className="card p-4">
          <div className="section-title mb-3">Evidence strength</div>
          <div className="space-y-2 text-[11.5px]">
            <div className="flex justify-between">
              <span className="text-ash-600">Data-backed claims</span>
              <span className="font-semibold text-revenue">Strong</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ash-600">External benchmarks</span>
              <span className="font-semibold text-amber-deep">Moderate</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ash-600">Case-study references</span>
              <span className="font-semibold text-amber-deep">Moderate</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ash-600">Unverified sources</span>
              <span className="font-semibold text-cost">Weak</span>
            </div>
          </div>
          <div className="text-[10.5px] text-ash-500 italic mt-3 pt-3 border-t border-ash-100">
            Trust scores come from the evidence kind + source confidence on each opportunity. Drill into any
            opportunity for its full evidence chain.
          </div>
        </div>
      </div>

      {/* Attribution comparison */}
      <div className="card p-4">
        <div className="flex justify-between items-baseline mb-3">
          <div>
            <div className="section-title">Cross-model attribution</div>
            <div className="text-[10.5px] text-ash-500 mt-0.5">
              Two independent models on {(markov?.journey_count || 0).toLocaleString()} journeys
            </div>
          </div>
          <div className="flex gap-3 text-[10.5px] font-semibold">
            <span className="text-cx">● Markov removal</span>
            <span className="text-purple">● Shapley</span>
          </div>
        </div>
        <div>
          {allChannels.map((ch) => (
            <AttributionBar key={ch} label={ch} markov={markovCredit[ch]} shapley={shapleyCredit[ch]} />
          ))}
        </div>
        <div className="text-[10.5px] text-ash-500 italic mt-3 pt-3 border-t border-ash-100">
          When Markov and Shapley agree closely, attribution is robust. Large gaps signal a channel whose credit
          is model-sensitive — useful context when defending a number.
        </div>
      </div>
    </div>
  );
}
