/**
 * API client for Yield Intelligence backend.
 * In dev: Vite proxies /v1/* to http://localhost:8000
 * In prod on Railway: same origin, nginx/FastAPI serves both
 */

const API_BASE = import.meta.env.VITE_API_BASE || "";

async function request(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const res = await fetch(url, { ...opts, headers });
  if (!res.ok) {
    const txt = await res.text();
    let detail = txt;
    try {
      detail = JSON.parse(txt).detail || txt;
    } catch { /* keep as text */ }
    const err = new Error(`${res.status} ${res.statusText}: ${detail}`);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

// --- Exec Summary ------------------------------------------------------------
export const getExecSummary = (workspace) =>
  request(`/v1/exec-summary${workspace ? `?workspace=${workspace}` : ""}`);

// --- Opportunities -----------------------------------------------------------
export const getOpportunities = ({ pillar, motion } = {}) => {
  const q = new URLSearchParams();
  if (pillar) q.set("pillar", pillar);
  if (motion) q.set("motion", motion);
  const qs = q.toString();
  return request(`/v1/opportunities${qs ? `?${qs}` : ""}`);
};

export const getLibrary = ({ notTriggeredOnly, pillar, motion } = {}) => {
  const q = new URLSearchParams();
  if (notTriggeredOnly) q.set("not_triggered_only", "true");
  if (pillar) q.set("pillar", pillar);
  if (motion) q.set("motion", motion);
  const qs = q.toString();
  return request(`/v1/library${qs ? `?${qs}` : ""}`);
};

// --- Performance --------------------------------------------------------------
export const getPerformance = () => request("/v1/performance");

// --- Attribution --------------------------------------------------------------
export const getMarkovAttribution = () => request("/v1/attribution/markov");
export const getShapleyAttribution = (maxChannels = 8) =>
  request(`/v1/attribution/shapley?max_channels=${maxChannels}`);

// --- MMM & Optimization ------------------------------------------------------
export const getMmmSummary = () => request("/v1/mmm/summary");
export const runOptimize = (body = {}) =>
  request("/v1/optimize", { method: "POST", body: JSON.stringify(body) });

// --- Actions & Scenarios -----------------------------------------------------
export const getActions = ({ pillar, motion } = {}) => {
  const q = new URLSearchParams();
  if (pillar) q.set("pillar", pillar);
  if (motion) q.set("motion", motion);
  const qs = q.toString();
  return request(`/v1/actions${qs ? `?${qs}` : ""}`);
};

export const createScenario = (body) =>
  request("/v1/scenarios", { method: "POST", body: JSON.stringify(body) });
export const getScenario = (id) => request(`/v1/scenarios/${id}`);
export const updateScenarioActions = (id, body) =>
  request(`/v1/scenarios/${id}/actions`, { method: "PATCH", body: JSON.stringify(body) });

// --- Overrides ----------------------------------------------------------------
export const createOverride = (body) =>
  request("/v1/overrides", { method: "POST", body: JSON.stringify(body) });
export const deleteOverride = (id) =>
  request(`/v1/overrides/${id}`, { method: "DELETE" });

// --- Health -------------------------------------------------------------------
export const getHealth = () => request("/health");
