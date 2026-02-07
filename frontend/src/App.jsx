import { useState } from 'react';
import { Trophy, BarChart3, RefreshCw } from 'lucide-react';
import Leaderboard from './components/Leaderboard';
import Analytics from './components/Analytics';

function App() {
  const [activeTab, setActiveTab] = useState('leaderboard');
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRefresh = () => setRefreshKey((k) => k + 1);

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="header-title">
          <Trophy size={28} color="#f59e0b" />
          <span>Exam Leaderboard</span>
        </div>
        <nav className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'leaderboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('leaderboard')}
          >
            <Trophy size={16} />
            <span>Leaderboard</span>
          </button>
          <button
            className={`nav-tab ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveTab('analytics')}
          >
            <BarChart3 size={16} />
            <span>Analytics</span>
          </button>
        </nav>
        <button className="nav-tab" onClick={handleRefresh} title="Refresh data">
          <RefreshCw size={18} />
        </button>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {activeTab === 'leaderboard' && <Leaderboard key={`lb-${refreshKey}`} />}
        {activeTab === 'analytics' && <Analytics key={`an-${refreshKey}`} />}
      </main>

      {/* Footer */}
      <footer style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-muted)', fontSize: '.8rem', borderTop: '1px solid var(--border)' }}>
        <span>Exam Leaderboard System &copy; {new Date().getFullYear()}</span>
      </footer>
    </div>
  );
}

export default App;
