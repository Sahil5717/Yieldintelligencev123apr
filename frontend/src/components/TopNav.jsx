import { NavLink } from "react-router-dom";
import clsx from "clsx";

const NAV = [
  { to: "/", label: "Executive", end: true },
  { to: "/opportunities", label: "Opportunities" },
  { to: "/performance", label: "Performance" },
  { to: "/trust", label: "Trust" },
  { to: "/simulate", label: "Simulate" },
  { to: "/plan", label: "Plan" },
  { to: "/track", label: "Track" },
];

export default function TopNav({ workspace = "Acme Retail", asOf }) {
  return (
    <div className="sticky top-0 z-40 bg-white border-b border-ash-200">
      <div className="max-w-[1400px] mx-auto px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-ink flex items-center justify-center">
              <span className="font-serif italic font-semibold text-[16px] text-purple-tint leading-none">
                Y
              </span>
            </div>
            <div>
              <div className="text-[11px] text-ash-500 font-medium leading-tight">
                Yield Intelligence
              </div>
              <div className="text-[13px] text-ink font-semibold leading-tight -mt-0.5">
                {workspace}
              </div>
            </div>
          </div>
          {asOf && (
            <div className="text-[11px] text-ash-500 border-l border-ash-200 pl-4">
              Data as of <span className="font-medium text-ink">{asOf}</span>
            </div>
          )}
        </div>
        <nav className="flex items-center gap-0.5 text-[12px]">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                clsx(
                  "px-3 py-1.5 rounded-md transition-colors font-medium",
                  isActive
                    ? "bg-ink text-white"
                    : "text-ash-600 hover:text-ink hover:bg-ash-100"
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}
