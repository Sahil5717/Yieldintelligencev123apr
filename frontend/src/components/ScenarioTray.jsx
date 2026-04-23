import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getActions } from "../api/client";
import { useTray } from "../hooks/useTray";
import { fmtMoney } from "../lib/format";
import { X, Plus } from "lucide-react";

export default function ScenarioTray({ onAddFromLibrary }) {
  const { selected, toggle, clear } = useTray();
  const navigate = useNavigate();
  const { data: actions = [] } = useQuery({ queryKey: ["actions"], queryFn: () => getActions() });

  if (selected.size === 0) return null;

  const selectedActions = actions.filter((a) => selected.has(a.action_id));
  const totalImpact = selectedActions.reduce(
    (sum, a) => sum + (a.effective_impact || 0),
    0
  );

  return (
    <div className="fixed bottom-0 left-0 right-0 z-30 bg-white border-t border-ash-200 shadow-lg">
      <div className="max-w-[1400px] mx-auto px-6 py-3 flex items-center gap-4">
        <div className="flex-1 flex items-center gap-3 overflow-x-auto scrollbar-thin">
          <div className="text-[12px] text-ash-600 whitespace-nowrap">
            <span className="font-bold text-ink">{selected.size}</span> selected ·{" "}
            <span className="money-green">{fmtMoney(totalImpact, { compact: true })}</span>{" "}
            impact
          </div>
          <div className="h-5 w-px bg-ash-200" />
          <div className="flex gap-1.5 overflow-x-auto">
            {selectedActions.slice(0, 4).map((a) => (
              <div
                key={a.action_id}
                className="flex items-center gap-1.5 text-[11px] bg-ash-100 px-2 py-1 rounded-md whitespace-nowrap"
              >
                <span className="max-w-[200px] truncate">{a.name}</span>
                <button
                  onClick={() => toggle(a.action_id)}
                  className="text-ash-500 hover:text-ink"
                >
                  <X size={11} />
                </button>
              </div>
            ))}
            {selectedActions.length > 4 && (
              <div className="text-[11px] text-ash-500 px-2 py-1">
                +{selectedActions.length - 4} more
              </div>
            )}
          </div>
        </div>

        <button
          onClick={onAddFromLibrary}
          className="text-[11px] text-ash-600 border border-ash-300 px-3 py-1.5 rounded-md font-semibold hover:border-purple hover:text-purple flex items-center gap-1 whitespace-nowrap"
        >
          <Plus size={12} /> Add from library
        </button>
        <button
          onClick={() => clear()}
          className="text-[11px] text-ash-500 hover:text-ink whitespace-nowrap"
        >
          Clear
        </button>
        <button
          onClick={() => navigate("/simulate")}
          className="text-[11px] bg-purple text-white px-3.5 py-1.5 rounded-md font-semibold hover:bg-purple-deep whitespace-nowrap"
        >
          Simulate →
        </button>
      </div>
    </div>
  );
}
