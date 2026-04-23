import { Calendar, TrendingUp } from "lucide-react";

export default function TrackPage() {
  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
      <div className="text-[11px] text-ash-500 font-medium">Measure mode</div>
      <div className="text-[22px] font-bold text-ink mt-0.5 mb-5 tracking-tight">Track</div>

      <div className="card p-8 text-center">
        <Calendar size={32} className="mx-auto text-ash-400 mb-3" />
        <div className="text-[14px] text-ink font-medium mb-2">No committed plan results yet</div>
        <div className="text-[12px] text-ash-500 max-w-md mx-auto mb-4">
          Track compares predicted vs actual for committed plan items. Results appear here once a plan has been
          running for at least one reporting cycle.
        </div>
        <div className="text-[10.5px] text-ash-500 italic">
          v1 scope: results tracking requires committed scenario + data updates over time. Once you upload
          refreshed data via the Data page, Track will populate.
        </div>
      </div>

      {/* What Track WILL show - preview */}
      <div className="mt-6 card p-4 opacity-70">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={14} className="text-ash-500" />
          <div className="section-title">What Track will show</div>
        </div>
        <div className="grid grid-cols-3 gap-4 text-[11.5px]">
          <div>
            <div className="text-[10px] text-ash-500 uppercase tracking-wider font-bold mb-1">
              Per action
            </div>
            <div className="text-ash-600">
              Predicted impact vs. actual lift. Flagged if actual {"< 70%"} of predicted.
            </div>
          </div>
          <div>
            <div className="text-[10px] text-ash-500 uppercase tracking-wider font-bold mb-1">
              Calibration
            </div>
            <div className="text-ash-600">
              Model accuracy over time. Drifts in MMM priors surface here before they bias future scenarios.
            </div>
          </div>
          <div>
            <div className="text-[10px] text-ash-500 uppercase tracking-wider font-bold mb-1">
              Signals to next cycle
            </div>
            <div className="text-ash-600">
              What to re-weight, re-fit, or re-think for the next planning window. Closes the loop.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
