import { useState } from "react";
import { useLocation } from "react-router-dom";
import { MessageCircle, X } from "lucide-react";
import clsx from "clsx";

// Screen-contextual canned prompts + answers
const LIBRARY = {
  "/": [
    {
      q: "What's the single biggest move I could make?",
      a: "OPP-001 (budget reallocation from OOH to organic/search) at $12.85M is your largest detected opportunity. It's also the highest-confidence one (85%) because it's grounded entirely in your own ROI data. If you could only do one thing this quarter, start here.",
    },
    {
      q: "How much of this is reversible?",
      a: "About $13.4M is fully reversible (optimization motion — tactical budget shifts). The remaining $17.2M sits in transformation moves: lifecycle email ($7.9M), checkout rebuild ($3.2M), SSL/CAPI ($4.9M), site speed ($1.1M). These compound but take months to land.",
    },
    {
      q: "What are we not showing?",
      a: "The library contains 94 opportunity types. Only 8 triggered for you this quarter based on your data. 86 are visible in 'Browse library' — some didn't trigger because your data doesn't indicate the problem (e.g., vendor concentration is 34.9%, just under the 35% threshold).",
    },
    {
      q: "How confident are these numbers?",
      a: "The weighted portfolio confidence is 78%. Highest-confidence claims (90%+): sub-1× ROI eliminations. Lower-confidence (60-70%): any opportunity relying on external benchmarks (SSL recovery, CTV launch). Each opportunity shows its own confidence and evidence chain when drilled into.",
    },
  ],
  "/opportunities": [
    {
      q: "Why did this trigger?",
      a: "Click any opportunity to see the evidence chain: which signals matched, what the math is, and what sources back it. Every number on this page is defensible.",
    },
    {
      q: "Can I add something the tool missed?",
      a: "Yes. Click 'Browse library' in the header or 'Add from library' in the scenario tray. You can pull any of the 86 non-triggered opportunities in manually, with a required reason — that preserves the audit trail.",
    },
    {
      q: "What if I disagree with the impact number?",
      a: "Open any opportunity and scroll to the 'Your override' section. You can adjust impact, confidence, or ramp time — with a required reason. Your edited value shows across the product in amber and carries through all downstream scenario math.",
    },
  ],
  "/performance": [
    {
      q: "Which channels are saturated?",
      a: "TV national and events are showing signs of saturation — their marginal ROI is near 1.0×, meaning the next dollar barely breaks even. The optimizer suggests shifting budget from these to email, call center, and video_youtube which have more headroom.",
    },
    {
      q: "Why is OOH losing money?",
      a: "OOH's ROI is 4.04× vs portfolio median 7.97×. On the efficient frontier, it's classified 'past peak'. The channel is working but opportunity cost is high — every dollar there is a dollar not earning the portfolio median.",
    },
  ],
  "/trust": [
    {
      q: "How was the MMM fit?",
      a: "Current deployment uses a bootstrap-ridge fallback (60-observation dataset, 2-year window). Run `python scripts/fit_mmm.py` to replace with a real PyMC Bayesian MMM. Diagnostics and R-hat values will be visible here once the real fit lands.",
    },
  ],
  "/simulate": [
    {
      q: "What does locking a channel do?",
      a: "Locked channels hold their current spend. The optimizer reallocates the remaining budget across unlocked channels. Useful for 'I can't touch TV this quarter, what's the best I can do with everything else?'",
    },
  ],
  "/plan": [
    {
      q: "What happens when I commit a scenario?",
      a: "Committed scenarios become your Plan — the baseline against which Track measures actual results. You can still have other scenarios in draft, but only one is committed at a time.",
    },
  ],
  "/track": [
    {
      q: "What if results don't match predictions?",
      a: "Track compares predicted vs actual per action. Underperformance triggers a review — was the model wrong (calibration), was execution delayed (ramp), or did external conditions change (a competitor, a macro shift)? Each cause has a different next-cycle response.",
    },
  ],
};

export default function Atlas() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const prompts = LIBRARY[location.pathname] || LIBRARY["/"];
  const [active, setActive] = useState(null);

  return (
    <>
      {/* Floating bubble */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-lg hover:scale-105 transition-transform cursor-pointer"
          style={{
            background: "linear-gradient(135deg, #F59E0B 0%, #B45309 80%)",
          }}
        >
          <span className="font-serif italic font-semibold text-2xl text-white leading-none">
            A
          </span>
        </button>
      )}

      {/* Panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-[380px] max-h-[540px] flex flex-col card shadow-xl">
          <div
            className="p-4 rounded-t-lg flex justify-between items-start"
            style={{ background: "linear-gradient(135deg, #F59E0B 0%, #B45309 80%)" }}
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="font-serif italic font-semibold text-[18px] text-white">
                  Atlas
                </span>
              </div>
              <div className="text-[11px] text-white/80 mt-0.5">
                Answers about what you're seeing
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-white/80 hover:text-white"
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-thin p-3">
            {active == null ? (
              <div className="space-y-1.5">
                <div className="text-[10.5px] text-ash-500 font-semibold uppercase tracking-wider mb-2 px-1">
                  Common questions
                </div>
                {prompts.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => setActive(i)}
                    className="w-full text-left text-[12px] text-ink p-2.5 rounded-md border border-ash-200 hover:border-purple hover:bg-purple-tint/40 transition-colors"
                  >
                    {p.q}
                  </button>
                ))}
              </div>
            ) : (
              <div>
                <button
                  onClick={() => setActive(null)}
                  className="text-[10.5px] text-ash-500 hover:text-ink mb-2 flex items-center gap-1"
                >
                  ← Back
                </button>
                <div className="text-[12.5px] font-semibold text-ink mb-2">
                  {prompts[active].q}
                </div>
                <div className="text-[12px] text-ash-600 leading-relaxed">
                  {prompts[active].a}
                </div>
              </div>
            )}
          </div>

          <div className="text-[10px] text-ash-500 italic px-3 py-2 border-t border-ash-200">
            Atlas answers from a library of screen-specific prompts. Full conversation mode coming soon.
          </div>
        </div>
      )}
    </>
  );
}
