import { useState, useEffect } from 'react';
import { Search, Trophy, ArrowUp, ArrowDown, Clock, Medal } from 'lucide-react';
import { getLeaderboard } from '../api';
import { formatTime, getRankClass, getScoreLevel } from '../utils';
import StudentModal from './StudentModal';

const EXAM_ID = 1;

export default function Leaderboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [selectedUserId, setSelectedUserId] = useState(null);

  const perPage = 25;

  useEffect(() => {
    setLoading(true);
    getLeaderboard(EXAM_ID, page, perPage)
      .then((res) => { setData(res.data); setError(null); })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) return <div className="loading"><div className="spinner" /> Loading leaderboard...</div>;
  if (error) return <div className="error-msg">Error: {error}</div>;
  if (!data) return null;

  const filtered = data.leaderboard.filter((e) =>
    !search || e.username.toLowerCase().includes(search.toLowerCase()) ||
    e.full_name.toLowerCase().includes(search.toLowerCase())
  );

  const totalPages = Math.ceil(data.total_participants / perPage);

  return (
    <>
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <div className="card-title">
            <Trophy size={18} /> {data.exam_title}
            <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '.85rem', marginLeft: '.5rem' }}>
              {data.total_participants} participants
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <input
              type="text"
              className="search-input"
              placeholder="Search student..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {data.cached && (
              <span style={{ fontSize: '.7rem', color: 'var(--accent-green)', background: 'rgba(34,197,94,.1)', padding: '.25rem .5rem', borderRadius: '4px' }}>
                CACHED
              </span>
            )}
          </div>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Student</th>
                <th className="text-right">Coding (50%)</th>
                <th className="text-right">Quiz (30%)</th>
                <th className="text-right">Assessment (20%)</th>
                <th className="text-right">Total Score</th>
                <th className="text-right">Time</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((entry) => (
                <tr
                  key={entry.user_id}
                  onClick={() => setSelectedUserId(entry.user_id)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>
                    <span className={`rank-badge ${getRankClass(entry.rank)}`}>
                      {entry.rank}
                    </span>
                  </td>
                  <td>
                    <div>
                      <div style={{ fontWeight: 600 }}>{entry.full_name}</div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '.75rem' }}>@{entry.username}</div>
                    </div>
                  </td>
                  <td className="text-right">
                    <ScoreBar score={entry.weighted_coding} max={50} />
                  </td>
                  <td className="text-right">
                    <ScoreBar score={entry.weighted_quiz} max={30} />
                  </td>
                  <td className="text-right">
                    <ScoreBar score={entry.weighted_assessment} max={20} />
                  </td>
                  <td className="text-right">
                    <span className="font-mono" style={{ fontWeight: 700, fontSize: '1rem', color: entry.total_score >= 75 ? 'var(--accent-green)' : entry.total_score >= 50 ? 'var(--accent-yellow)' : 'var(--accent-red)' }}>
                      {entry.total_score.toFixed(2)}
                    </span>
                  </td>
                  <td className="text-right">
                    <span className="time-value inline-flex" style={{ color: 'var(--text-secondary)' }}>
                      <Clock size={14} /> {formatTime(entry.total_time_sec)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <button disabled={page === 1} onClick={() => setPage(page - 1)}>
            <ArrowUp size={14} style={{ transform: 'rotate(-90deg)' }} /> Prev
          </button>
          <span>Page {page} of {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            Next <ArrowDown size={14} style={{ transform: 'rotate(-90deg)' }} />
          </button>
        </div>
      </div>

      {selectedUserId && (
        <StudentModal
          userId={selectedUserId}
          examId={EXAM_ID}
          onClose={() => setSelectedUserId(null)}
        />
      )}
    </>
  );
}

function ScoreBar({ score, max }) {
  const pct = Math.min(100, (score / max) * 100);
  const level = getScoreLevel(score, max);
  return (
    <div className="score-bar-container">
      <div className="score-bar">
        <div className={`score-bar-fill ${level}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="score-label font-mono">{score.toFixed(1)}</span>
    </div>
  );
}
