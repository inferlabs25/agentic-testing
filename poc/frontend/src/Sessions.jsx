import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { pollJob } from './api';

export default function Sessions() {
  const [sessions, setSessions] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analysing, setAnalysing] = useState(null);
  const [jobMessage, setJobMessage] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const fetchSessions = useCallback(async () => {
    try {
      const [sessionsRes, metricsRes] = await Promise.all([
        api.get('/api/sessions'),
        api.get('/api/dashboard/metrics'),
      ]);
      setSessions(sessionsRes.data);
      setMetrics(metricsRes.data);
      setError('');
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
      setError('Unable to load sessions. Check that the backend is running.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial server synchronization.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSessions();
  }, [fetchSessions]);

  const handleAnalyse = async (e, sessionId) => {
    e.stopPropagation();
    setAnalysing(sessionId);
    setError('');
    setJobMessage('Queued analysis');
    try {
      const response = await api.post(`/api/sessions/${sessionId}/analyse`);
      const job = await pollJob(response.data.job_id, (latestJob) => {
        setJobMessage(latestJob.message || latestJob.status);
      });
      if (job.status !== 'completed') {
        throw new Error(job.error || 'Analysis failed');
      }
      await fetchSessions();
      navigate(`/sessions/${sessionId}/testcases`);
    } catch (err) {
      console.error('Analysis failed:', err);
      setError(err.message || 'Analysis failed. Verify OPENAI_API_KEY and backend logs.');
    } finally {
      setAnalysing(null);
      setJobMessage('');
    }
  };

  const statusBadge = (status) => {
    const styles = {
      recording: 'bg-red-500/10 text-red-400 border border-red-500/20',
      completed: 'bg-slate-500/10 text-slate-400 border border-slate-500/20',
      analysing: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
      analysed: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
      analysis_failed: 'bg-red-500/10 text-red-400 border border-red-500/20',
    };
    return <span className={`badge ${styles[status] || styles.completed}`}>{status.toUpperCase()}</span>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Recorded Sessions</h1>
          <p className="text-slate-400">Client-pilot workspace for AI-generated executable tests.</p>
        </div>
      </div>

      {metrics && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
          <Metric label="Sessions" value={metrics.sessions_recorded} />
          <Metric label="Tests" value={metrics.tests_generated} />
          <Metric label="Ready" value={metrics.ready_to_run} />
          <Metric label="Review" value={metrics.suggested_review} />
          <Metric label="Pass Rate" value={`${metrics.suite_pass_rate}%`} />
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {analysing && (
        <div className="mb-4 rounded-lg border border-blue-500/30 bg-blue-500/10 p-3 text-sm text-blue-100">
          {jobMessage || 'Analysis running'}
        </div>
      )}

      {sessions.length === 0 ? (
        <div className="glass-card p-12 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4 text-2xl">
            REC
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">No sessions yet</h3>
          <p className="text-slate-400 max-w-md">
            Start recording from the Chrome extension on an allowed pilot domain.
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
                  <td className="p-4">{statusBadge(session.status)}</td>
                  <td className="p-4 text-right">
                    {(session.status === 'completed' || session.status === 'recording' || session.status === 'analysis_failed') && (
                      <button
                        className="btn btn-primary text-sm py-1.5"
                        onClick={(event) => handleAnalyse(event, session.session_id)}
                        disabled={analysing === session.session_id}
                      >
                        {analysing === session.session_id ? 'Analysing...' : 'Analyse with AI'}
                      </button>
                    )}
                    {session.status === 'analysed' && (
                      <span className="text-sm text-slate-400 group-hover:text-blue-400 transition-colors">
                        View Tests
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

function Metric({ label, value }) {
  return (
    <div className="glass-card p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-white">{value}</div>
    </div>
  );
}
