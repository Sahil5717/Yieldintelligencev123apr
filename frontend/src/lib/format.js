/**
 * Formatting utilities.
 */

export const fmtMoney = (value, { compact = false, withSign = false, decimals = 0 } = {}) => {
  if (value == null || isNaN(value)) return "—";
  const sign = value > 0 && withSign ? "+" : "";
  if (compact) {
    const abs = Math.abs(value);
    if (abs >= 1_000_000_000)
      return `${sign}$${(value / 1_000_000_000).toFixed(2).replace(/\.?0+$/, "")}B`;
    if (abs >= 1_000_000)
      return `${sign}$${(value / 1_000_000).toFixed(decimals === 0 ? (abs >= 10_000_000 ? 1 : 2) : decimals).replace(/\.?0+$/, "")}M`;
    if (abs >= 1_000)
      return `${sign}$${(value / 1_000).toFixed(0)}K`;
    return `${sign}$${Math.round(value).toLocaleString()}`;
  }
  return `${sign}$${Math.round(value).toLocaleString()}`;
};

export const fmtPct = (value, { decimals = 1, withSign = false } = {}) => {
  if (value == null || isNaN(value)) return "—";
  const sign = value > 0 && withSign ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
};

export const fmtX = (value, { decimals = 2 } = {}) => {
  if (value == null || isNaN(value)) return "—";
  return `${value.toFixed(decimals)}×`;
};

export const fmtInt = (value) => {
  if (value == null || isNaN(value)) return "—";
  return Math.round(value).toLocaleString();
};

// Delta label like "+15.2% vs last quarter"
export const fmtDeltaPct = (value) => {
  if (value == null || isNaN(value)) return "";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
};

// Text-case for pillar/motion pills
export const humanPillar = (p) => {
  const map = {
    revenue: "Revenue",
    cost: "Cost",
    cx: "CX",
    risk: "Risk",
  };
  return map[p] || p;
};

export const humanMotion = (m) => {
  const map = {
    optimization: "Optimization",
    transformation: "Transformation",
  };
  return map[m] || m;
};
