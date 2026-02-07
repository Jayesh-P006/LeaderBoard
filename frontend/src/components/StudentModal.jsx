import { useState, useEffect } from 'react';
import { X, Trophy, Clock, Zap, Target, TrendingUp } from 'lucide-react';
import { getStudentAnalytics } from '../api';
import { formatTime, getTierClass, getScoreLevel } from '../utils';

export default function StudentModal({ userId, examId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStudentAnalytics(userId, examId)
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId, examId]);

  if (loading) return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="loading"><div className="spinner" /> Loading...</div>
      </div>
    </div>
  );

  if (!data) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '.25rem' }}>{data.full_name}</h2>
            <span style={{ color: 'var(--text-muted)', fontSize: '.85rem' }}>@{data.username}</span>
          </div>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>

        {/* Key Metrics */}
        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
          <div className="stat-card">
            <span className="stat-label">Rank</span>
            <span className="stat-value blue">#{data.dense_rank}</span>
            <span className="stat-sub">of {data.total_participants}</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Total Score</span>
            <span className="stat-value green">{Number(data.total_score).toFixed(2)}</span>
            <span className="stat-sub">out of 100</span>
          </div>
          <div className="stat-card">
            <span className="stat-label">Percentile</span>
            <span className="stat-value purple">P{Number(data.percentile_rank).toFixed(0)}</span>
            <span className={`tier-badge ${getTierClass(data.performance_tier)}`}>{data.performance_tier}</span>
          </div>
        </div>

        {/* Detailed Stats */}
        <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: '1.5rem' }}>
          <StatMini icon={<TrendingUp size={14} />} label="Z-Score" value={Number(data.z_score).toFixed(2)} />
          <StatMini icon={<Clock size={14} />} label="Time" value={formatTime(data.total_time_sec)} />
          <StatMini icon={<Zap size={14} />} label="Speed Rank" value={`#${data.speed_rank}`} />
          <StatMini icon={<Target size={14} />} label="Quartile" value={`Q${data.quartile}`} />
        </div>

        {/* Module Breakdown */}
        <div className="card" style={{ marginBottom: '1rem', background: 'var(--bg-primary)' }}>
          <div className="card-title" style={{ marginBottom: '1rem' }}>
            <Trophy size={16} /> Module Breakdown
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '.75rem' }}>
            <ModuleRow
              label="Coding"
              rank={data.coding_rank}
              weighted={data.weighted_coding}
              max={50}
              module={data.modules?.find(m => m.module_type === 'coding')}
            />
            <ModuleRow
              label="Quiz"
              rank={data.quiz_rank}
              weighted={data.weighted_quiz}
              max={30}
              module={data.modules?.find(m => m.module_type === 'quiz')}
            />
            <ModuleRow
              label="Assessment"
              rank={data.assessment_rank}
              weighted={data.weighted_assessment}
              max={20}
              module={data.modules?.find(m => m.module_type === 'assessment')}
            />
          </div>
        </div>

        {/* Comparison */}
        <div className="card" style={{ background: 'var(--bg-primary)' }}>
          <div className="card-title" style={{ marginBottom: '1rem' }}>
            <TrendingUp size={16} /> Comparison to Peers
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '.85rem' }}>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Exam Average: </span>
              <span className="font-mono">{Number(data.exam_avg).toFixed(2)}</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Exam Std Dev: </span>
              <span className="font-mono">{Number(data.exam_stddev).toFixed(2)}</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Score Above: </span>
              <span className="font-mono">{data.score_above != null ? Number(data.score_above).toFixed(2) : 'N/A (Top)'}</span>
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Score Below: </span>
              <span className="font-mono">{data.score_below != null ? Number(data.score_below).toFixed(2) : 'N/A (Last)'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatMini({ icon, label, value }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '.25rem', padding: '.75rem', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
      <span className="inline-flex" style={{ color: 'var(--text-muted)', fontSize: '.7rem', textTransform: 'uppercase', fontWeight: 600 }}>
        {icon} {label}
      </span>
      <span className="font-mono" style={{ fontWeight: 700 }}>{value}</span>
    </div>
  );
}

function ModuleRow({ label, rank, weighted, max, module }) {
  const pct = (weighted / max) * 100;
  const level = getScoreLevel(weighted, max);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <span style={{ width: '90px', fontWeight: 600, fontSize: '.85rem' }}>{label}</span>
      <span style={{ width: '45px', fontSize: '.75rem', color: 'var(--text-muted)' }}>#{rank}</span>
      <div className="score-bar" style={{ flex: 1 }}>
        <div className={`score-bar-fill ${level}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono score-label">{Number(weighted).toFixed(1)}/{max}</span>
      {module && (
        <span className="time-value" style={{ fontSize: '.75rem', color: 'var(--text-muted)', width: '60px', textAlign: 'right' }}>
          {formatTime(module.time_spent_sec)}
        </span>
      )}
    </div>
  );
}
