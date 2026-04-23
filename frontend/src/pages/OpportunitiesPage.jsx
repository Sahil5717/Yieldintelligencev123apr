import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronUp, Sparkles, X } from "lucide-react";
import clsx from "clsx";

import {
  getOpportunities,
  getActions,
  getLibrary,
  createOverride,
} from "../api/client";
import { fmtMoney, fmtPct, humanPillar } from "../lib/format";
import { useTray } from "../hooks/useTray";

// ---- Row + drill-down -------------------------------------------------------

function OpportunityRow({ opp, action, expanded, onToggleExpand }) {
  const { isSelected, toggle } = useTray();
  const aid = action?.action_id;

  const pillarColorMap = {
    revenue: { bg: "bg-revenue-tint", text: "text-revenue" },
    cost: { bg: "bg-cost-tint", text: "text-cost" },
    cx: { bg: "bg-cx-tint", text: "text-cx" },
    risk: { bg: "bg-risk-tint", text: "text-risk" },
  };
  const motionColorMap = {
    optimization: { bg: "bg-opt-tint", text: "text-opt-ink" },
    transformation: { bg: "bg-trans-tint", text: "text-trans-ink" },
  };

  const pc = pillarColorMap[opp.pillar] || pillarColorMap.revenue;
  const mc = motionColorMap[opp.motion] || motionColorMap.transformation;
  const hasOverride = action?.has_override;
  const displayImpact = action?.effective_impact ?? opp.modeled_impact;

  return (
    <>
      <div
        className={clsx(
          "card px-4 py-3 grid grid-cols-[18px_1fr_auto_20px] gap-3 items-center cursor-pointer transition-colors",
          expanded && "rounded-b-none border-b-0",
          hasOverride && "border-l-4 border-l-amber"
        )}
        onClick={onToggleExpand}
      >
        <input
          type="checkbox"
          checked={aid ? isSelected(aid) : false}
          onChange={(e) => {
            e.stopPropagation();
            if (aid) toggle(aid);
          }}
          onClick={(e) => e.stopPropagation()}
          className="w-3 h-3 accent-purple cursor-pointer"
        />
        <div className="min-w-0">
          <div className="text-[12.5px] text-ink font-medium leading-snug">{opp.name}</div>
          <div className="flex items-center gap-1 flex-wrap mt-1 text-[10px] text-ash-600">
            <span className={clsx("pill", pc.bg, pc.text)}>{humanPillar(opp.pillar)}</span>
            <span className={clsx("pill", mc.bg, mc.text)}>{opp.motion}</span>
            <span>·</span>
            <span>conf {Math.round((opp.confidence || 0) * 100)}%</span>
            {opp.external_boost > 1.0 && (
              <>
                <span>·</span>
                <span className="text-amber-deep font-medium">boosted</span>
              </>
            )}
          </div>
          <div className="text-[10.5px] text-ash-500 mt-1 why italic">{opp.rationale}</div>
        </div>
        <div className="text-right">
          <div className={clsx("text-[14px] money", hasOverride ? "text-amber-deep" : "text-revenue")}>
            {fmtMoney(displayImpact, { compact: true, withSign: true })}
          </div>
          <div className="text-[9.5px] text-ash-500 mt-0.5">
            {hasOverride ? (
              <span className="text-amber-deep">
                edited · was {fmtMoney(opp.modeled_impact, { compact: true })}
              </span>
            ) : (
              "annualized"
            )}
          </div>
        </div>
        <div className="flex justify-center">
          {expanded ? (
            <ChevronUp size={14} className="text-ash-400" />
          ) : (
            <ChevronDown size={14} className="text-ash-400" />
          )}
        </div>
      </div>
      {expanded && <DrillPanel opp={opp} action={action} />}
    </>
  );
}

function DrillPanel({ opp, action }) {
  const [tab, setTab] = useState("evidence");
  const [impactOverride, setImpactOverride] = useState(action?.effective_impact ?? opp.modeled_impact);
  const [confidenceOverride, setConfidenceOverride] = useState(
    Math.round((action?.effective_confidence ?? opp.confidence ?? 0.5) * 100)
  );
  const [rampOverride, setRampOverride] = useState(action?.effective_ramp_months ?? 3);
  const [reason, setReason] = useState(action?.override_reason ?? "");

  const qc = useQueryClient();
  const saveOverride = useMutation({
    mutationFn: createOverride,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["actions"] });
      qc.invalidateQueries({ queryKey: ["opportunities"] });
      qc.invalidateQueries({ queryKey: ["execSummary"] });
    },
  });

  const tabs = ["evidence", "math", "sensitivity", "dependencies"];
  const displayBase = opp.modeled_impact;
  const pctOverride = impactOverride != null && displayBase > 0 ? (impactOverride / displayBase) * 100 : 100;

  return (
    <div className="card rounded-t-none border-t-0 px-5 pt-0 pb-4 -mt-px">
      <div className="flex border-b border-ash-100 -mx-5 px-5 mb-4">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={clsx(
              "py-2.5 px-3 text-[11px] font-semibold uppercase tracking-wider capitalize transition-colors border-b-2 -mb-px",
              tab === t
                ? "text-ink border-purple"
                : "text-ash-500 border-transparent hover:text-ash-600"
            )}
          >
            {t === "math" ? "How we calculated" : t}
          </button>
        ))}
      </div>

      {tab === "evidence" && (
        <div className="grid md:grid-cols-[1.2fr_1fr] gap-4">
          <div className="bg-ash-50 border border-ash-100 rounded-md p-3">
            <div className="text-[9.5px] text-ash-500 font-bold uppercase tracking-wider mb-2">
              Why this triggered
            </div>
            {opp.evidence?.map((e, i) => (
              <div key={i} className="flex gap-2 text-[11px] text-ink leading-relaxed mb-2">
                <span
                  className={clsx(
                    "w-1.5 h-1.5 rounded-full mt-1.5 shrink-0",
                    e.strength === "strong" ? "bg-revenue" : "bg-amber"
                  )}
                />
                <div>
                  <div>{e.statement}</div>
                  <div className="text-[9.5px] text-ash-500 mt-0.5">
                    Source: {e.source}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="text-[10.5px] text-ash-600 space-y-2">
            <div>
              <div className="text-[9.5px] text-ash-500 font-bold uppercase tracking-wider mb-1">
                Low / expected / high
              </div>
              <div className="flex items-center gap-3">
                <span>Low: {fmtMoney(opp.low_estimate, { compact: true })}</span>
                <span className="font-semibold text-ink">
                  Expected: {fmtMoney(opp.modeled_impact, { compact: true })}
                </span>
                <span>High: {fmtMoney(opp.high_estimate, { compact: true })}</span>
              </div>
            </div>
            {opp.external_boost > 1.0 && (
              <div className="bg-amber-bg border border-amber-border rounded p-2 text-[10.5px] text-amber-ink">
                <Sparkles size={11} className="inline mr-1" />
                External signal boost {fmtPct((opp.external_boost - 1) * 100)}:{" "}
                {opp.external_signal_refs.join(", ")}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "math" && (
        <div className="font-mono text-[11px] bg-ink text-purple-tint rounded-md p-4 leading-relaxed">
          <div className="text-[9.5px] text-purple/70 font-sans font-bold uppercase tracking-wider mb-2">
            Impact math
          </div>
          <div className="whitespace-pre-wrap">
            {opp.rationale}
            {"\n\n"}
            Low: {fmtMoney(opp.low_estimate)}
            {"\n"}
            Expected: <span className="text-[#86EFAC]">{fmtMoney(opp.modeled_impact)}</span>
            {"\n"}
            High: {fmtMoney(opp.high_estimate)}
            {"\n\n"}
            Confidence: {Math.round((opp.confidence || 0) * 100)}%
          </div>
        </div>
      )}

      {tab === "sensitivity" && (
        <div className="text-[12px] text-ash-600 py-4">
          Sensitivity analysis shows how impact changes with key assumptions. Full sensitivity view
          coming in v1.1 — requires running the optimizer with perturbed MMM parameters.
        </div>
      )}

      {tab === "dependencies" && (
        <div className="text-[12px] text-ash-600 py-4 space-y-2">
          <div>
            <span className="font-semibold text-ink">Decision audience:</span>{" "}
            {action?.decision_audience || "CMO"}
          </div>
          <div>
            <span className="font-semibold text-ink">Timeline:</span>{" "}
            {action?.timeline || opp.timeline || "Months"}
          </div>
          <div>
            <span className="font-semibold text-ink">Reversibility:</span>{" "}
            {action?.reversibility || opp.reversibility || "M"}
          </div>
        </div>
      )}

      {/* Override panel — always visible */}
      <div className="bg-amber-bg border border-amber-border rounded-md p-3 mt-4">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10.5px] font-bold uppercase tracking-wider text-amber-deep">
            Your override
          </div>
          <button
            onClick={() => {
              setImpactOverride(opp.modeled_impact);
              setConfidenceOverride(Math.round((opp.confidence || 0) * 100));
              setRampOverride(3);
              setReason("");
            }}
            className="text-[9.5px] text-amber-ink hover:underline cursor-pointer font-semibold"
          >
            ↺ Reset to model
          </button>
        </div>

        <div className="grid grid-cols-[75px_1fr_90px] gap-3 items-center text-[11px] mb-2">
          <div className="text-ash-600">Impact</div>
          <input
            type="range"
            min={displayBase * 0.3}
            max={displayBase * 1.5}
            step={Math.max(1000, displayBase * 0.01)}
            value={impactOverride}
            onChange={(e) => setImpactOverride(Number(e.target.value))}
            className="accent-amber"
          />
          <div className="money-amber text-[13px] text-right">
            {fmtMoney(impactOverride, { compact: true })}
          </div>
        </div>
        <div className="grid grid-cols-[75px_1fr_90px] gap-3 items-center text-[11px] mb-2">
          <div className="text-ash-600">Confidence</div>
          <input
            type="range"
            min={20}
            max={99}
            step={1}
            value={confidenceOverride}
            onChange={(e) => setConfidenceOverride(Number(e.target.value))}
            className="accent-amber"
          />
          <div className="money-amber text-[13px] text-right">{confidenceOverride}%</div>
        </div>
        <div className="grid grid-cols-[75px_1fr_90px] gap-3 items-center text-[11px] mb-3">
          <div className="text-ash-600">Ramp (mo)</div>
          <input
            type="range"
            min={0}
            max={12}
            step={1}
            value={rampOverride}
            onChange={(e) => setRampOverride(Number(e.target.value))}
            className="accent-amber"
          />
          <div className="money-amber text-[13px] text-right">{rampOverride}</div>
        </div>

        <div className="text-[9.5px] text-amber-ink font-bold uppercase tracking-wider mb-1">
          Reason for override
        </div>
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="required — one sentence explaining why"
          className="w-full text-[11px] border border-amber-border rounded px-2 py-1.5 bg-white text-ink placeholder-ash-400"
        />

        <div className="flex justify-between items-center mt-3">
          <div className="text-[10px] text-ash-500">
            {pctOverride < 100 ? "↓ " : pctOverride > 100 ? "↑ " : ""}
            {Math.round(pctOverride)}% of model value
          </div>
          <button
            disabled={!reason || !action?.action_id || saveOverride.isPending}
            onClick={() => {
              saveOverride.mutate({
                action_id: action.action_id,
                impact_override: impactOverride,
                confidence_override: confidenceOverride / 100,
                ramp_months_override: rampOverride,
                reason,
              });
            }}
            className={clsx(
              "text-[11px] px-3 py-1.5 rounded-md font-semibold",
              !reason || !action?.action_id
                ? "bg-ash-200 text-ash-500 cursor-not-allowed"
                : "bg-purple text-white hover:bg-purple-deep"
            )}
          >
            {saveOverride.isPending ? "Saving…" : saveOverride.isSuccess ? "✓ Saved" : "Save override"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Library modal ----------------------------------------------------------

function LibraryModal({ open, onClose }) {
  const { data: library = [] } = useQuery({
    queryKey: ["library", true],
    queryFn: () => getLibrary({ notTriggeredOnly: true }),
    enabled: open,
  });
  const [search, setSearch] = useState("");

  const filtered = useMemo(
    () => library.filter((l) => l.name.toLowerCase().includes(search.toLowerCase())),
    [library, search]
  );

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-ink/40 flex items-center justify-center p-6">
      <div className="bg-white rounded-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-4 border-b border-ash-200 flex justify-between items-center">
          <div>
            <div className="section-title">Browse the library</div>
            <div className="text-[11px] text-ash-500 mt-0.5">
              {library.length} opportunities didn't trigger for Acme · pull any in manually
            </div>
          </div>
          <button onClick={onClose} className="text-ash-500 hover:text-ink">
            <X size={16} />
          </button>
        </div>
        <div className="p-3 border-b border-ash-100">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search 94 opportunity types…"
            className="w-full text-[12px] border border-ash-300 rounded px-3 py-2"
          />
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin p-2">
          {filtered.slice(0, 30).map((l) => (
            <div
              key={l.catalog_id}
              className="p-3 rounded border border-ash-200 mb-2 bg-ash-50 hover:bg-white hover:border-purple transition-colors"
            >
              <div className="flex justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-medium text-ink">{l.name}</div>
                  <div className="text-[10px] text-ash-500 mt-1">
                    <span className="pill bg-ash-200 text-ash-600 mr-1">{l.category}</span>
                    {l.pillar} · {l.motion} · {l.timeline || "—"}
                  </div>
                  {l.trigger_conditions && (
                    <div className="text-[10px] text-ash-500 mt-1 italic">
                      Trigger: {l.trigger_conditions}
                    </div>
                  )}
                </div>
                <button className="text-[10.5px] text-purple font-semibold hover:text-purple-deep whitespace-nowrap">
                  Add anyway →
                </button>
              </div>
            </div>
          ))}
          {filtered.length > 30 && (
            <div className="text-center text-[10.5px] text-ash-500 py-2">
              + {filtered.length - 30} more · refine your search
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- Main page --------------------------------------------------------------

export default function OpportunitiesPage() {
  const [params] = useSearchParams();
  const [expandedId, setExpandedId] = useState(null);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const pillarFilter = params.get("pillar") || "";
  const motionFilter = params.get("motion") || "";

  const { data: opps = [], isLoading } = useQuery({
    queryKey: ["opportunities", { pillar: pillarFilter, motion: motionFilter }],
    queryFn: () => getOpportunities({ pillar: pillarFilter || undefined, motion: motionFilter || undefined }),
  });
  const { data: actions = [] } = useQuery({ queryKey: ["actions"], queryFn: () => getActions() });
  const actionByCatalog = useMemo(() => {
    // Match action to opportunity by detected_opp_id isn't present here; join by order instead
    // since actions are sorted by modeled_impact desc and opportunities are too, index-match works.
    const map = {};
    opps.forEach((o, i) => {
      const a = actions.find((ac) => ac.modeled_impact === o.modeled_impact && ac.name === o.name);
      if (a) map[o.catalog_id] = a;
    });
    return map;
  }, [opps, actions]);

  const [filter, setFilter] = useState(pillarFilter || "all");

  const visibleOpps = opps.filter((o) => (filter === "all" ? true : o.pillar === filter));

  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
      <div className="text-[11px] text-ash-500 font-medium">Acme Retail · FY2025 · Opportunities</div>
      <div className="text-[22px] font-bold text-ink mt-0.5 mb-5 tracking-tight">Opportunities</div>

      {/* Hero callout */}
      <div
        className="rounded-xl p-5 text-white relative overflow-hidden mb-5"
        style={{ background: "linear-gradient(135deg, #0F1535 0%, #1E2456 62%, #2D2C6E 100%)" }}
      >
        <div
          className="absolute -right-12 -top-12 w-48 h-48 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(124,92,255,.25), transparent 70%)" }}
        />
        <div className="relative">
          <div className="text-[9px] text-purple-tint font-bold uppercase tracking-[0.18em] mb-1.5">
            What the tool detected for you
          </div>
          <div className="font-serif text-[17px] leading-snug font-medium">
            We evaluated every signal from your data and the market.{" "}
            <span className="italic text-[#86EFAC] font-semibold">
              {opps.length} opportunities fit Acme right now.
            </span>
          </div>
        </div>
      </div>

      {/* Section header + library link */}
      <div className="flex justify-between items-baseline mb-3">
        <div className="flex items-baseline gap-3">
          <div className="section-title">Detected opportunities</div>
          <div className="text-[10.5px] text-ash-500">{opps.length} found · sorted by impact</div>
        </div>
        <button
          onClick={() => setLibraryOpen(true)}
          className="text-[10.5px] text-purple font-semibold hover:text-purple-deep"
        >
          ⊕ Browse library
        </button>
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap gap-1.5 mb-4 items-center">
        <div className="text-[10px] text-ash-500 font-bold uppercase tracking-wider mr-1">Filter</div>
        {["all", "revenue", "cost", "cx", "risk"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={clsx(
              "text-[10.5px] px-2.5 py-1 rounded-full border font-medium transition-colors capitalize",
              filter === f
                ? "bg-ink text-white border-ink"
                : "bg-white text-ash-600 border-ash-300 hover:border-ash-500"
            )}
          >
            {f === "cx" ? "CX" : f}
          </button>
        ))}
      </div>

      {/* Rows */}
      <div className="space-y-1.5">
        {isLoading && (
          <div className="text-center py-8 text-ash-500 text-sm">Loading opportunities…</div>
        )}
        {!isLoading && visibleOpps.length === 0 && (
          <div className="text-center py-8 text-ash-500 text-sm">
            No opportunities for this filter. Try another.
          </div>
        )}
        {visibleOpps.map((opp) => (
          <OpportunityRow
            key={opp.catalog_id}
            opp={opp}
            action={actionByCatalog[opp.catalog_id]}
            expanded={expandedId === opp.catalog_id}
            onToggleExpand={() =>
              setExpandedId(expandedId === opp.catalog_id ? null : opp.catalog_id)
            }
          />
        ))}
      </div>

      <LibraryModal open={libraryOpen} onClose={() => setLibraryOpen(false)} />
    </div>
  );
}
