import { useQuery } from "@tanstack/react-query";
import { Upload, Database, RefreshCw } from "lucide-react";

import { getExecSummary } from "../api/client";

export default function DataSourcesPage() {
  const { data: summary } = useQuery({ queryKey: ["execSummary"], queryFn: () => getExecSummary() });

  return (
    <div className="max-w-[1400px] mx-auto px-6 pt-6 pb-24">
      <div className="text-[11px] text-ash-500 font-medium">Reference</div>
      <div className="text-[22px] font-bold text-ink mt-0.5 mb-5 tracking-tight">Data &amp; sources</div>

      <div className="grid md:grid-cols-[2fr_1fr] gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Database size={14} className="text-ink" />
            <div className="section-title">Currently loaded</div>
          </div>
          <div className="space-y-2 text-[12px]">
            <DataRow label="Campaign performance" value="23,760 rows" detail="60 months × 11 channels" />
            <DataRow label="User journeys" value="117,887 touchpoints" detail="40,000 unique journey paths" />
            <DataRow label="Market events" value="5 events" detail="seasonal + competitive markers" />
            <DataRow label="Market trends" value="40 benchmarks" detail="CPC/CPM/CVR vs industry" />
            <DataRow label="Competitive intel" value="180 competitor rows" detail="spend estimates + share" />
            <DataRow label="Opportunity catalog" value="94 types" detail="with pillar + motion classification" />
            <DataRow label="Global signals" value="2,815 rows" detail="events, holidays, seasonality, sentiment" />
          </div>
          <div className="text-[10.5px] text-ash-500 italic mt-3 pt-3 border-t border-ash-100">
            Data as of <span className="text-ink font-medium">{summary?.as_of || "—"}</span>. Acme Retail
            dataset packaged in this build.
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Upload size={14} className="text-ink" />
            <div className="section-title">Replace data</div>
          </div>
          <div className="text-[11.5px] text-ash-600 mb-3">
            CSV upload to replace Acme data with your own. Supported formats match the Acme dataset schema.
          </div>
          <button className="w-full text-[11px] border border-ash-300 rounded-md py-2 text-ash-500 cursor-not-allowed mb-3">
            Upload CSV (v1.1)
          </button>

          <div className="flex items-center gap-2 mb-2 mt-4">
            <RefreshCw size={12} className="text-ink" />
            <div className="text-[12px] font-semibold text-ink">Refit MMM</div>
          </div>
          <div className="text-[11px] text-ash-600 mb-2">
            Run <code className="bg-ash-100 px-1.5 rounded text-[10.5px]">python scripts/fit_mmm.py</code> after
            uploading new data.
          </div>
          <div className="text-[10.5px] text-ash-500 italic">
            <code>--synthetic</code>: 30s bootstrap fallback.<br />
            <code>(default)</code>: 20-40min Bayesian PyMC fit.
          </div>
        </div>
      </div>

      <div className="card p-4 mt-4">
        <div className="section-title mb-3">Global signals catalog</div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3 text-[11.5px]">
          <div>
            <div className="text-[9.5px] text-ash-500 uppercase tracking-wider font-bold mb-1">
              Event calendar
            </div>
            <div className="text-ink font-medium">45 rows</div>
          </div>
          <div>
            <div className="text-[9.5px] text-ash-500 uppercase tracking-wider font-bold mb-1">Holidays</div>
            <div className="text-ink font-medium">30 rows</div>
          </div>
          <div>
            <div className="text-[9.5px] text-ash-500 uppercase tracking-wider font-bold mb-1">
              Seasonal windows
            </div>
            <div className="text-ink font-medium">40 rows</div>
          </div>
          <div>
            <div className="text-[9.5px] text-ash-500 uppercase tracking-wider font-bold mb-1">
              Consumer sentiment
            </div>
            <div className="text-ink font-medium">300 rows</div>
          </div>
          <div>
            <div className="text-[9.5px] text-ash-500 uppercase tracking-wider font-bold mb-1">
              Category seasonality
            </div>
            <div className="text-ink font-medium">2,400 rows</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DataRow({ label, value, detail }) {
  return (
    <div className="flex justify-between py-2 border-b border-ash-100 last:border-b-0">
      <div>
        <div className="text-ink font-medium">{label}</div>
        <div className="text-[10.5px] text-ash-500 mt-0.5">{detail}</div>
      </div>
      <div className="text-right text-ash-600 font-medium">{value}</div>
    </div>
  );
}
