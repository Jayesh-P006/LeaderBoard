export const formatTime = (seconds) => {
  if (!seconds && seconds !== 0) return '--';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

export const getRankClass = (rank) => {
  if (rank === 1) return 'rank-1';
  if (rank === 2) return 'rank-2';
  if (rank === 3) return 'rank-3';
  return 'rank-other';
};

export const getTierClass = (tier) => {
  if (!tier) return 'tier-average';
  const t = tier.toLowerCase().replace(/\s+/g, '-');
  return `tier-${t}`;
};

export const getScoreLevel = (score, max = 100) => {
  const pct = (score / max) * 100;
  if (pct >= 70) return 'high';
  if (pct >= 40) return 'medium';
  return 'low';
};

export const CHART_COLORS = [
  '#3b82f6', '#22c55e', '#eab308', '#ef4444',
  '#a855f7', '#06b6d4', '#f97316', '#ec4899',
];
