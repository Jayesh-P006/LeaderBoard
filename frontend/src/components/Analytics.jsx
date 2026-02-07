import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  AreaChart, Area, Legend, ScatterChart, Scatter, ZAxis,
} from 'recharts';
import { BarChart3, PieChart as PieIcon, Activity, Users, Award, TrendingUp, Clock, Zap } from 'lucide-react';
import { getAnalyticsSummary, getAnalyticsDistribution, getAnalyticsModules, getAnalyticsLeaderboard } from '../api';
import { formatTime, CHART_COLORS, getTierClass } from '../utils';

const EXAM_ID = 1;

export default function Analytics() {
  const [summary, setSummary] = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [modules, setModules] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      getAnalyticsSummary(EXAM_ID),
      getAnalyticsDistribution(EXAM_ID),
      getAnalyticsModules(EXAM_ID),
      getAnalyticsLeaderboard(EXAM_ID, 1, 100),
    ])
      .then(([sumRes, distRes, modRes, anaRes]) => {
        setSummary(sumRes.data);
        setDistribution(distRes.data.distribution);
        setModules(modRes.data.data);
        setAnalytics(anaRes.data.data);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading"><div className="spinner" /> Loading analytics...</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;
  if (!summary) return null;

  // Prepare chart data
  const tierData = analytics ? computeTierData(analytics) : [];
  const topPerformers = modules?.slice(0, 10) || [];
  const radarData = [
    { module: 'Coding', avg: summary.avg_coding, max: summary.max_coding },
    { module: 'Quiz', avg: summary.avg_quiz, max: summary.max_quiz },
    { module: 'Assessment', avg: summary.avg_assessment, max: summary.max_assessment },
  ];
  const scatterData = analytics?.map(a => ({
    x: a.total_score,
    y: a.total_time_sec / 60,
    name: a.username,
    z: 50,
  })) || [];

  return (
    <>
      {/* ── Summary Stats ─────────────────────────────── */}
      <div className="stats-grid">
        <StatCard label="Total Students" value={summary.total_participants} color="blue" icon={<Users size={16} />} />
        <StatCard label="Average Score" value={summary.avg_score?.toFixed(2)} color="green" sub={`σ = ${summary.stddev_score?.toFixed(2)}`} icon={<Activity size={16} />} />
        <StatCard label="Highest Score" value={summary.max_score?.toFixed(2)} color="yellow" icon={<Award size={16} />} />
        <StatCard label="Score Range" value={summary.score_range?.toFixed(2)} color="purple" sub={`${summary.min_score?.toFixed(1)} — ${summary.max_score?.toFixed(1)}`} icon={<TrendingUp size={16} />} />
        <StatCard label="Pass Rate" value={`${summary.pass_rate_pct}%`} color="green" sub="≥ 40 marks" icon={<Zap size={16} />} />
        <StatCard label="Distinction" value={`${summary.distinction_rate_pct}%`} color="cyan" sub="≥ 75 marks" icon={<Award size={16} />} />
        <StatCard label="Avg Time" value={formatTime(Math.round(summary.avg_time_sec))} color="blue" icon={<Clock size={16} />} />
        <StatCard label="Fastest" value={formatTime(summary.fastest_time_sec)} color="green" sub={`Slowest: ${formatTime(summary.slowest_time_sec)}`} icon={<Clock size={16} />} />
      </div>

      {/* ── Charts Row 1 ──────────────────────────────── */}
      <div className="charts-grid">
        {/* Score Distribution */}
        <div className="card">
          <div className="card-title"><BarChart3 size={16} /> Score Distribution</div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={distribution} margin={{ top: 20, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="score_bucket" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 12 }} />
              <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} />
              <Bar dataKey="student_count" name="Students" radius={[6, 6, 0, 0]}>
                {distribution?.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Performance Tier Pie */}
        <div className="card">
          <div className="card-title"><PieIcon size={16} /> Performance Tiers</div>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={tierData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3} dataKey="count" nameKey="tier" label={({ tier, count }) => `${tier}: ${count}`}>
                {tierData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Charts Row 2 ──────────────────────────────── */}
      <div className="charts-grid">
        {/* Radar — Module Comparison */}
        <div className="card">
          <div className="card-title"><Activity size={16} /> Module Performance (Avg vs Max)</div>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="module" tick={{ fill: 'var(--text-secondary)', fontSize: 13 }} />
              <PolarRadiusAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
              <Radar name="Average" dataKey="avg" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
              <Radar name="Max" dataKey="max" stroke="#22c55e" fill="#22c55e" fillOpacity={0.15} />
              <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
              <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Scatter — Score vs Time */}
        <div className="card">
          <div className="card-title"><TrendingUp size={16} /> Score vs Time (min)</div>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 20, right: 20, bottom: 10, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="x" name="Score" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} label={{ value: 'Total Score', position: 'bottom', fill: 'var(--text-muted)', fontSize: 12 }} />
              <YAxis dataKey="y" name="Time (min)" tick={{ fill: 'var(--text-muted)', fontSize: 12 }} label={{ value: 'Time (min)', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)', fontSize: 12 }} />
              <ZAxis dataKey="z" range={[30, 60]} />
              <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} formatter={(v, n) => n === 'Time (min)' ? `${v.toFixed(0)} min` : v.toFixed(2)} />
              <Scatter data={scatterData} fill="#3b82f6" opacity={0.7} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Score Distribution Area ──────────────────── */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-title"><TrendingUp size={16} /> Score Trend (Rank Order)</div>
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart data={analytics?.map((a, i) => ({ rank: i + 1, score: a.total_score, avg: a.running_avg }))} margin={{ top: 10, right: 20, bottom: 5, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="rank" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} label={{ value: 'Rank', position: 'bottom', fill: 'var(--text-muted)' }} />
            <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
            <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text-primary)' }} />
            <Area type="monotone" dataKey="score" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} name="Score" />
            <Area type="monotone" dataKey="avg" stroke="#22c55e" fill="none" strokeDasharray="5 5" name="Running Avg" />
            <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* ── Top Performers Table ──────────────────────── */}
      <div className="card">
        <div className="card-title"><Zap size={16} /> Top 10 — Efficiency (Points/Minute)</div>
        <div className="table-container" style={{ marginTop: '1rem' }}>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Student</th>
                <th className="text-right">Coding</th>
                <th className="text-right">Quiz</th>
                <th className="text-right">Assessment</th>
                <th>Strongest</th>
                <th>Weakest</th>
                <th className="text-right">Pts/Min</th>
              </tr>
            </thead>
            <tbody>
              {topPerformers.map((m, i) => (
                <tr key={m.user_id}>
                  <td>{i + 1}</td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{m.full_name}</div>
                    <div style={{ color: 'var(--text-muted)', fontSize: '.75rem' }}>@{m.username}</div>
                  </td>
                  <td className="text-right font-mono">{Number(m.coding_raw).toFixed(1)}</td>
                  <td className="text-right font-mono">{Number(m.quiz_raw).toFixed(1)}</td>
                  <td className="text-right font-mono">{Number(m.assessment_raw).toFixed(1)}</td>
                  <td><span className="tier-badge tier-outstanding">{m.strongest_module}</span></td>
                  <td><span className="tier-badge tier-needs-improvement">{m.weakest_module}</span></td>
                  <td className="text-right">
                    <span className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>
                      {Number(m.points_per_minute).toFixed(2)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function StatCard({ label, value, color = 'blue', sub, icon }) {
  return (
    <div className="stat-card">
      <span className="stat-label inline-flex">{icon} {label}</span>
      <span className={`stat-value ${color}`}>{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}

function computeTierData(data) {
  const tiers = {};
  data.forEach((d) => {
    const t = d.performance_tier || 'Unknown';
    tiers[t] = (tiers[t] || 0) + 1;
  });
  return Object.entries(tiers).map(([tier, count]) => ({ tier, count }));
}
