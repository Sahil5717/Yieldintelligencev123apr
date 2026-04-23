import { Routes, Route } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import TopNav from "./components/TopNav";
import Footer from "./components/Footer";
import Atlas from "./components/Atlas";
import ScenarioTray from "./components/ScenarioTray";
import { TrayProvider } from "./hooks/useTray";

import ExecutiveSummary from "./pages/ExecutiveSummary";
import OpportunitiesPage from "./pages/OpportunitiesPage";
import PerformancePage from "./pages/PerformancePage";
import TrustPage from "./pages/TrustPage";
import SimulatePage from "./pages/SimulatePage";
import PlanPage from "./pages/PlanPage";
import TrackPage from "./pages/TrackPage";
import DataSourcesPage from "./pages/DataSourcesPage";

import { getExecSummary } from "./api/client";

export default function App() {
  const [libraryOpen, setLibraryOpen] = useState(false);
  const { data: summary } = useQuery({
    queryKey: ["execSummary"],
    queryFn: () => getExecSummary(),
  });

  return (
    <TrayProvider>
      <div className="min-h-screen flex flex-col">
        <TopNav workspace="Acme Retail" asOf={summary?.as_of} />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<ExecutiveSummary />} />
            <Route path="/opportunities" element={<OpportunitiesPage />} />
            <Route path="/performance" element={<PerformancePage />} />
            <Route path="/trust" element={<TrustPage />} />
            <Route path="/simulate" element={<SimulatePage />} />
            <Route path="/plan" element={<PlanPage />} />
            <Route path="/track" element={<TrackPage />} />
            <Route path="/data" element={<DataSourcesPage />} />
          </Routes>
        </main>
        <Footer />
        <ScenarioTray onAddFromLibrary={() => setLibraryOpen(true)} />
        <Atlas />
      </div>
    </TrayProvider>
  );
}
