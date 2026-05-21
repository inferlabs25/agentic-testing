import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function Sessions() {
  const [sessions, setSessions] = null || useState([]);
  const [loading, setLoading] = useState(true);
  const [analysing, setAnalysing] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const res = await axios.get('/api/sessions');
      setSessions(res.data);
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyse = async (e, sessionId) => {
    e.stopPropagation();
    setAnalysing(sessionId);
    try {
      await axios.post(`/api/sessions/${sessionId}/analyse`);
      await fetchSessions();
      navigate(`/sessions/${sessionId}/testcases`);
    } catch (err) {
      console.error('Analysis failed:', err);
      alert('Analysis failed. Make sure backend is running with OPENAI_API_KEY set.');
    } finally {
      setAnalysing(null);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      recording: 'bg-red-500/10 text-red-400 border border-red-500/20',
      completed: 'bg-slate-500/10 text-slate-400 border border-slate-500/20',
      analysing: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
      analysed: 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
    };
    return <span className={`badge ${styles[status] || styles.completed}`}>{status.toUpperCase()}</span>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Recorded Sessions</h1>
          <p className="text-slate-400">View and analyse your captured browser sessions.</p>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="glass-card p-12 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4 text-2xl">
            🎥
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">No sessions yet</h3>
          <p className="text-slate-400 max-w-md">
            Install the Chrome extension and start recording a session to see it appear here automatically.
          </p>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900/50 border-b border-slate-700/50">
                <th className="p-4 font-semibold text-slate-300 text-sm">Session ID</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">URL</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">Steps</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">Status</th>
                <th className="p-4 font-semibold text-slate-300 text-sm text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {sessions.map((session) => (
                <tr 
                  key={session.session_id} 
                  className="hover:bg-slate-800/30 transition-colors cursor-pointer group"
                  onClick={() => navigate(`/sessions/${session.session_id}/testcases`)}
                >
                  <td className="p-4">
                    <div className="font-mono text-sm text-blue-400">
                      {session.session_id.substring(0, 8)}...
                    </div>
                    <div className="text-xs text-slate-500 mt-1">
                      {new Date(session.created_at).toLocaleString()}
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="text-sm truncate max-w-xs text-slate-300" title={session.url || 'Unknown'}>
                      {session.url || 'Unknown URL'}
                    </div>
                  </td>
                  <td className="p-4">
                    <span className="text-slate-300 font-medium">{session.steps_count}</span>
                  </td>
                  <td className="p-4">
                    {getStatusBadge(session.status)}
                  </td>
                  <td className="p-4 text-right">
                    {(session.status === 'completed' || session.status === 'recording') && (
                      <button 
                        className="btn btn-primary text-sm py-1.5"
                        onClick={(e) => handleAnalyse(e, session.session_id)}
                        disabled={analysing === session.session_id}
                      >
                        {analysing === session.session_id ? (
                          <><div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div> Analysing...</>
                        ) : (
                          '✨ Analyse with AI'
                        )}
                      </button>
                    )}
                    {session.status === 'analysed' && (
                      <span className="text-sm text-slate-400 group-hover:text-blue-400 transition-colors">
                        View Tests →
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
