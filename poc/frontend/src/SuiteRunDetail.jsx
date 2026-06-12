import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api, { pollJob } from './api';

export default function SuiteRunDetail() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [suite, setSuite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    async function fetchSuite() {
      try {
        const response = await api.get(`/api/suite-runs/${runId}`);
        setSuite(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Unable to load suite run.');
      } finally {
        setLoading(false);
      }
    }
    fetchSuite();
  }, [runId]);

  const retryFailed = async () => {
    setRetrying(true);
    setError('');
    try {
      const response = await api.post(`/api/suite-runs/${runId}/retry-failed`);
      const job = await pollJob(response.data.job_id);
      if (job.status !== 'completed') {
        throw new Error(job.error || 'Retry failed');
      }
      navigate(`/suite-runs/${job.result.suite_run_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Retry failed.');
    } finally {
      setRetrying(false);
    }
  };

  const openReport = async () => {
    try {
      const response = await api.get(`/api/suite-runs/${suite.id}/report`, { responseType: 'text' });
      const blob = new Blob([response.data], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to open report.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!suite) {
    return <div className="text-white">{error || 'Suite run not found.'}</div>;
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => navigate(`/sessions/${suite.session_id}/testcases`)}
        className="text-sm text-slate-400 hover:text-white transition-colors mb-4"
      >
        Back to Test Cases
      </button>

      <div className="glass-card p-6 mb-6">
        <div className="flex justify-between items-start gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-2">Suite Run</h1>
            <p className="text-slate-400 text-sm font-mono">{suite.id}</p>
          </div>
          <span className="badge bg-blue-500/10 text-blue-300 border border-blue-500/20">
            {suite.status.toUpperCase()}
          </span>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-4 gap-3 mb-6">
        <Metric label="Total" value={suite.total_count} />
        <Metric label="Passed" value={suite.passed_count} />
        <Metric label="Failed" value={suite.failed_count} />
        <Metric label="Duration" value={`${suite.duration_seconds || 0}s`} />
      </div>

      <div className="flex gap-3">
        <button type="button" className="btn btn-primary" onClick={openReport}>
          Open Report
        </button>
        {suite.failed_count > 0 && (
          <button type="button" className="btn btn-secondary" onClick={retryFailed} disabled={retrying}>
            {retrying ? 'Retrying...' : 'Retry Failed'}
          </button>
        )}
      </div>
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
