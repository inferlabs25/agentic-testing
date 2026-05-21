import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function TestCases() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(null);

  useEffect(() => {
    fetchTestCases();
  }, [sessionId]);

  const fetchTestCases = async () => {
    try {
      const res = await axios.get(`/api/sessions/${sessionId}/testcases`);
      setTestCases(res.data);
    } catch (err) {
      console.error('Failed to fetch test cases:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (e, id) => {
    e.stopPropagation();
    try {
      await axios.post(`/api/testcases/${id}/approve`);
      fetchTestCases();
    } catch (err) {
      console.error(err);
    }
  };

  const handleApproveAll = async () => {
    try {
      await axios.post(`/api/sessions/${sessionId}/approve-all`);
      fetchTestCases();
    } catch (err) {
      console.error(err);
    }
  };

  const handleExecute = async (e, id) => {
    e.stopPropagation();
    setExecuting(id);
    try {
      const res = await axios.post(`/api/testcases/${id}/execute`);
      navigate(`/results/${res.data.result_id}`);
    } catch (err) {
      console.error(err);
      alert('Execution failed. Is the backend running?');
    } finally {
      setExecuting(null);
      fetchTestCases();
    }
  };

  const handleRowClick = async (tc) => {
    // If it has a result, navigate to the latest result
    if (tc.status === 'passed' || tc.status === 'failed') {
      try {
        const res = await axios.get(`/api/testcases/${tc.id}/results`);
        if (res.data && res.data.length > 0) {
          navigate(`/results/${res.data[0].id}`);
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const getTypeBadge = (type) => {
    const styles = {
      happy: 'bg-green-500/10 text-green-400 border border-green-500/20',
      negative: 'bg-red-500/10 text-red-400 border border-red-500/20',
      edge: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
      security: 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
    };
    return <span className={`badge ${styles[type.toLowerCase()] || styles.happy}`}>{type}</span>;
  };

  const getStatusBadge = (status) => {
    const styles = {
      draft: 'bg-slate-500/10 text-slate-400 border border-slate-500/20',
      approved: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
      running: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 animate-pulse',
      passed: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      failed: 'bg-red-500/10 text-red-400 border border-red-500/20'
    };
    return <span className={`badge ${styles[status] || styles.draft}`}>{status.toUpperCase()}</span>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
      </div>
    );
  }

  const draftsCount = testCases.filter(t => t.status === 'draft').length;

  return (
    <div>
      <div className="mb-6">
        <button 
          onClick={() => navigate('/')}
          className="text-sm text-slate-400 hover:text-white transition-colors mb-4 flex items-center gap-1"
        >
          ← Back to Sessions
        </button>
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">AI Generated Test Cases</h1>
            <p className="text-slate-400 font-mono text-sm">Session: {sessionId.substring(0, 12)}...</p>
          </div>
          {draftsCount > 0 && (
            <button className="btn btn-secondary" onClick={handleApproveAll}>
              ✓ Approve All Drafts
            </button>
          )}
        </div>
      </div>

      {testCases.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-slate-400">No test cases generated yet. Go back and click "Analyse with AI".</p>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900/50 border-b border-slate-700/50">
                <th className="p-4 font-semibold text-slate-300 text-sm w-1/3">Title & Reason</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">Type</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">Steps</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">Status</th>
                <th className="p-4 font-semibold text-slate-300 text-sm text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {testCases.map((tc) => {
                const hasResult = tc.status === 'passed' || tc.status === 'failed';
                return (
                  <tr 
                    key={tc.id} 
                    className={`hover:bg-slate-800/30 transition-colors ${hasResult ? 'cursor-pointer group' : ''}`}
                    onClick={() => handleRowClick(tc)}
                  >
                    <td className="p-4">
                      <div className="font-medium text-white mb-1">{tc.title}</div>
                      <div className="text-xs text-slate-500 leading-relaxed">{tc.reason}</div>
                    </td>
                    <td className="p-4">{getTypeBadge(tc.test_type)}</td>
                    <td className="p-4">
                      <span className="text-slate-300">{tc.steps.length}</span>
                    </td>
                    <td className="p-4">{getStatusBadge(tc.status)}</td>
                    <td className="p-4 text-right">
                      {tc.status === 'draft' && (
                        <button 
                          className="btn btn-secondary text-sm py-1.5 ml-auto"
                          onClick={(e) => handleApprove(e, tc.id)}
                        >
                          Approve
                        </button>
                      )}
                      {(tc.status === 'approved' || tc.status === 'passed' || tc.status === 'failed') && (
                        <button 
                          className="btn btn-primary text-sm py-1.5 ml-auto"
                          onClick={(e) => handleExecute(e, tc.id)}
                          disabled={executing === tc.id}
                        >
                          {executing === tc.id ? 'Running...' : '▶ Execute'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
