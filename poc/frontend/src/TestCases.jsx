import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api, { pollJob } from './api';

export default function TestCases() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [testCases, setTestCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(null);
  const [suiteJob, setSuiteJob] = useState(null);
  const [error, setError] = useState('');
  const [reviewCase, setReviewCase] = useState(null);
  const [reviewSteps, setReviewSteps] = useState('');
  const [reviewExpected, setReviewExpected] = useState('');
  const [reviewSaving, setReviewSaving] = useState(false);
  const [autoReviewing, setAutoReviewing] = useState(null);
  const [notice, setNotice] = useState('');

  const fetchTestCases = useCallback(async () => {
    try {
      const response = await api.get(`/api/sessions/${sessionId}/testcases`);
      setTestCases(response.data);
      setError('');
    } catch (err) {
      console.error('Failed to fetch test cases:', err);
      setError('Unable to load test cases.');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    // Initial server synchronization.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchTestCases();
  }, [fetchTestCases]);

  const counts = useMemo(() => ({
    ready: testCases.filter((item) => item.readiness_status === 'ready_to_run').length,
    suggested: testCases.filter((item) => item.readiness_status === 'suggested_review').length,
    approved: testCases.filter((item) => item.status === 'approved').length,
  }), [testCases]);

  const handleApprove = async (event, id) => {
    event.stopPropagation();
    setNotice('');
    try {
      await api.post(`/api/testcases/${id}/approve`);
      fetchTestCases();
    } catch (err) {
      setError(err.response?.data?.detail || 'Approval failed.');
    }
  };

  const handleApproveAll = async () => {
    setNotice('');
    try {
      await api.post(`/api/sessions/${sessionId}/approve-all`);
      fetchTestCases();
    } catch (err) {
      setError(err.response?.data?.detail || 'Bulk approval failed.');
    }
  };

  const handleExecute = async (event, id) => {
    event.stopPropagation();
    setExecuting(id);
    setError('');
    setNotice('');
    try {
      const response = await api.post(`/api/testcases/${id}/execute`);
      const job = await pollJob(response.data.job_id);
      if (job.status !== 'completed') {
        throw new Error(job.error || 'Execution failed');
      }
      await fetchTestCases();
      if (job.result?.result_id) {
        navigate(`/results/${job.result.result_id}`);
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Execution failed. Check backend logs.');
    } finally {
      setExecuting(null);
    }
  };

  const openReview = (event, tc) => {
    event.stopPropagation();
    setReviewCase(tc);
    setReviewSteps(JSON.stringify(tc.steps, null, 2));
    setReviewExpected(tc.expected_result || '');
    setError('');
    setNotice('');
  };

  const saveReview = async () => {
    if (!reviewCase) return;
    setReviewSaving(true);
    setError('');
    setNotice('');
    try {
      const parsedSteps = JSON.parse(reviewSteps);
      const response = await api.patch(`/api/testcases/${reviewCase.id}`, {
        steps: parsedSteps,
        expected_result: reviewExpected,
      });
      await fetchTestCases();
      setReviewCase(response.data);
      setReviewSteps(JSON.stringify(response.data.steps, null, 2));
      setReviewExpected(response.data.expected_result || '');
      if (response.data.readiness_status === 'ready_to_run') {
        setNotice('Saved and moved to READY.');
        setReviewCase(null);
      } else {
        setNotice(`Still needs review: ${response.data.readiness_reason || 'missing recorded evidence.'}`);
      }
    } catch (err) {
      setError(err instanceof SyntaxError ? 'Steps JSON is invalid.' : (err.response?.data?.detail || 'Review save failed.'));
    } finally {
      setReviewSaving(false);
    }
  };

  const runAutoReview = async (tc, closeOnReady = false) => {
    if (!tc) return;
    setAutoReviewing(tc.id);
    setError('');
    setNotice('');
    try {
      const response = await api.post(`/api/testcases/${tc.id}/auto-review`);
      await fetchTestCases();
      const updated = response.data;
      if (reviewCase?.id === tc.id) {
        setReviewCase(updated);
        setReviewSteps(JSON.stringify(updated.steps, null, 2));
        setReviewExpected(updated.expected_result || '');
      }
      if (updated.readiness_status === 'ready_to_run') {
        setNotice('Auto review made this test READY. It is now executable as a smoke validation.');
        if (closeOnReady) {
          setReviewCase(null);
        }
      } else {
        setNotice(`Still needs recorded evidence: ${updated.readiness_reason || 'selectors or assertions are not grounded yet.'}`);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Auto review failed.');
    } finally {
      setAutoReviewing(null);
    }
  };

  const handleAutoReview = async (event, tc) => {
    event.stopPropagation();
    await runAutoReview(tc);
  };

  const handleRunSuite = async () => {
    setError('');
    setNotice('');
    setSuiteJob({ message: 'Queued suite run', progress_current: 0, progress_total: counts.approved });
    try {
      const response = await api.post(`/api/sessions/${sessionId}/run-suite`);
      const job = await pollJob(response.data.job_id, setSuiteJob);
      await fetchTestCases();
      if (job.status !== 'completed') {
        throw new Error(job.error || 'Suite failed');
      }
      navigate(`/suite-runs/${job.result.suite_run_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Suite run failed.');
    } finally {
      setSuiteJob(null);
    }
  };

  const handleRowClick = async (tc) => {
    if (tc.status === 'passed' || tc.status === 'failed') {
      try {
        const response = await api.get(`/api/testcases/${tc.id}/results`);
        if (response.data && response.data.length > 0) {
          navigate(`/results/${response.data[0].id}`);
        }
      } catch (err) {
        console.error(err);
      }
    }
  };

  const typeBadge = (type) => {
    const styles = {
      happy: 'bg-green-500/10 text-green-400 border border-green-500/20',
      negative: 'bg-red-500/10 text-red-400 border border-red-500/20',
      edge: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
      security: 'bg-purple-500/10 text-purple-400 border border-purple-500/20',
    };
    return <span className={`badge ${styles[type?.toLowerCase()] || styles.happy}`}>{type}</span>;
  };

  const statusBadge = (status) => {
    const styles = {
      draft: 'bg-slate-500/10 text-slate-400 border border-slate-500/20',
      suggested_review: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
      approved: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
      running: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 animate-pulse',
      passed: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      failed: 'bg-red-500/10 text-red-400 border border-red-500/20',
    };
    return <span className={`badge ${styles[status] || styles.draft}`}>{status.toUpperCase()}</span>;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
      </div>
    );
  }

  const draftsCount = testCases.filter((item) => item.status === 'draft' && item.readiness_status === 'ready_to_run').length;

  return (
    <div>
      <div className="mb-6">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-sm text-slate-400 hover:text-white transition-colors mb-4 flex items-center gap-1"
        >
          Back to Sessions
        </button>
        <div className="flex justify-between items-end gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">AI Generated Test Cases</h1>
            <p className="text-slate-400 font-mono text-sm">Session: {sessionId.substring(0, 12)}...</p>
          </div>
          <div className="flex gap-2">
            {draftsCount > 0 && (
              <button type="button" className="btn btn-secondary" onClick={handleApproveAll}>
                Approve Ready
              </button>
            )}
            {counts.approved > 0 && (
              <button type="button" className="btn btn-primary" onClick={handleRunSuite} disabled={Boolean(suiteJob)}>
                {suiteJob ? 'Running Suite...' : 'Run Suite'}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <Summary label="Ready to Run" value={counts.ready} />
        <Summary label="Suggested Review" value={counts.suggested} />
        <Summary label="Approved" value={counts.approved} />
      </div>

      {suiteJob && (
        <div className="mb-4 rounded-lg border border-blue-500/30 bg-blue-500/10 p-3 text-sm text-blue-100">
          {suiteJob.message || suiteJob.status} ({suiteJob.progress_current}/{suiteJob.progress_total})
        </div>
      )}

      {notice && (
        <div className={`mb-4 rounded-lg border p-3 text-sm ${notice.startsWith('Still needs') ? 'border-orange-500/30 bg-orange-500/10 text-orange-100' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'}`}>
          {notice}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {reviewCase && (
        <div className="glass-card p-5 mb-5 border-orange-500/30">
          <div className="flex justify-between gap-4 mb-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Review Test</h2>
              <p className="text-sm text-orange-200 mt-1">{reviewCase.title}</p>
              <p className="text-xs text-slate-400 mt-2">{reviewCase.readiness_reason}</p>
            </div>
            <button type="button" className="text-sm text-slate-400 hover:text-white" onClick={() => setReviewCase(null)}>
              Close
            </button>
          </div>

          <div className="mb-5 flex flex-col gap-3 border-y border-slate-700/50 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-sm font-semibold text-white">Automated Review</div>
              <div className="mt-1 text-xs text-slate-400">
                Removes unsupported AI guesses and reruns readiness validation.
              </div>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => runAutoReview(reviewCase, true)}
              disabled={autoReviewing === reviewCase.id}
            >
              {autoReviewing === reviewCase.id ? 'Reviewing...' : 'Auto Review & Revalidate'}
            </button>
          </div>

          <div className="mb-5">
            <div className="mb-2 text-xs uppercase tracking-wide text-slate-500">Flow Preview</div>
            <ol className="divide-y divide-slate-700/50 rounded-lg border border-slate-700/50">
              {(reviewCase.steps || []).map((step, index) => (
                <li key={`${step.step_index || index}-${step.action}`} className="grid gap-1 p-3 text-sm md:grid-cols-[120px_1fr]">
                  <span className="font-mono text-xs uppercase text-slate-400">
                    {step.step_index || index + 1}. {step.action}
                  </span>
                  <span className="break-all text-slate-200">
                    {step.selector || step.value || 'No selector/value'}
                  </span>
                </li>
              ))}
            </ol>
          </div>

          <details className="mt-4">
            <summary className="cursor-pointer text-xs uppercase tracking-wide text-slate-500 hover:text-slate-300">
              Advanced Manual Editor
            </summary>
            <div className="mt-4">
              <label className="block text-xs uppercase tracking-wide text-slate-500 mb-2" htmlFor="expected-result">
                Expected Result
              </label>
              <textarea
                id="expected-result"
                className="w-full min-h-16 rounded-lg bg-slate-950 border border-slate-700 p-3 text-sm text-slate-200 mb-4"
                value={reviewExpected}
                onChange={(event) => setReviewExpected(event.target.value)}
              />

              <label className="block text-xs uppercase tracking-wide text-slate-500 mb-2" htmlFor="steps-json">
                Steps JSON
              </label>
              <textarea
                id="steps-json"
                className="w-full min-h-80 rounded-lg bg-slate-950 border border-slate-700 p-3 text-xs font-mono text-slate-200"
                value={reviewSteps}
                onChange={(event) => setReviewSteps(event.target.value)}
              />

              <div className="mt-4 flex gap-2">
                <button type="button" className="btn btn-secondary" onClick={saveReview} disabled={reviewSaving}>
                  {reviewSaving ? 'Saving...' : 'Save & Revalidate'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setReviewCase(null)}>
                  Cancel
                </button>
              </div>
            </div>
          </details>
        </div>
      )}

      {testCases.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-slate-400">No test cases generated yet. Go back and click Analyse with AI.</p>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900/50 border-b border-slate-700/50">
                <th className="p-4 font-semibold text-slate-300 text-sm w-1/3">Title & Reason</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">Type</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">Readiness</th>
                <th className="p-4 font-semibold text-slate-300 text-sm">Status</th>
                <th className="p-4 font-semibold text-slate-300 text-sm text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {testCases.map((tc) => {
                const hasResult = tc.status === 'passed' || tc.status === 'failed';
                const isSuggested = tc.readiness_status === 'suggested_review';
                return (
                  <tr
                    key={tc.id}
                    className={`hover:bg-slate-800/30 transition-colors ${hasResult ? 'cursor-pointer group' : ''}`}
                    onClick={() => handleRowClick(tc)}
                  >
                    <td className="p-4">
                      <div className="font-medium text-white mb-1">{tc.title}</div>
                      <div className="text-xs text-slate-500 leading-relaxed">{tc.reason}</div>
                      {tc.readiness_reason && (
                        <div className="mt-2 text-xs text-slate-400">{tc.readiness_reason}</div>
                      )}
                    </td>
                    <td className="p-4">{typeBadge(tc.test_type)}</td>
                    <td className="p-4">
                      <span className={`badge ${isSuggested ? 'bg-orange-500/10 text-orange-300 border border-orange-500/20' : 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'}`}>
                        {isSuggested ? 'REVIEW' : 'READY'}
                      </span>
                    </td>
                    <td className="p-4">{statusBadge(tc.status)}</td>
                    <td className="p-4 text-right">
                      {tc.status === 'draft' && !isSuggested && (
                        <button type="button" className="btn btn-secondary text-sm py-1.5 ml-auto" onClick={(event) => handleApprove(event, tc.id)}>
                          Approve
                        </button>
                      )}
                      {(tc.status === 'approved' || tc.status === 'passed' || tc.status === 'failed') && !isSuggested && (
                        <button
                          type="button"
                          className="btn btn-primary text-sm py-1.5 ml-auto"
                          onClick={(event) => handleExecute(event, tc.id)}
                          disabled={executing === tc.id}
                        >
                          {executing === tc.id ? 'Running...' : 'Execute'}
                        </button>
                      )}
                      {isSuggested && (
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            className="btn btn-primary text-sm py-1.5"
                            onClick={(event) => handleAutoReview(event, tc)}
                            disabled={autoReviewing === tc.id}
                          >
                            {autoReviewing === tc.id ? 'Fixing...' : 'Auto-fix'}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary text-sm py-1.5"
                            onClick={(event) => openReview(event, tc)}
                          >
                            Review
                          </button>
                        </div>
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

function Summary({ label, value }) {
  return (
    <div className="glass-card p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-white">{value}</div>
    </div>
  );
}
