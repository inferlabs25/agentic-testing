import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function ResultDetail() {
  const { resultId } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const res = await axios.get(`/api/results/${resultId}`);
        setResult(res.data);
      } catch (err) {
        console.error('Failed to fetch result:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchResult();
  }, [resultId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!result) {
    return <div className="text-white">Result not found.</div>;
  }

  const getTypeBadge = (type) => {
    if (!type) return null;
    const styles = {
      happy: 'bg-green-500/10 text-green-400 border border-green-500/20',
      negative: 'bg-red-500/10 text-red-400 border border-red-500/20',
      edge: 'bg-orange-500/10 text-orange-400 border border-orange-500/20',
      security: 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
    };
    return <span className={`badge ${styles[type.toLowerCase()] || styles.happy}`}>{type}</span>;
  };

  const isPassed = result.overall_status === 'passed';

  return (
    <div>
      <div className="mb-6">
        <button 
          onClick={() => navigate(-1)}
          className="text-sm text-slate-400 hover:text-white transition-colors mb-4 flex items-center gap-1"
        >
          ← Back to Test Cases
        </button>
        
        <div className="glass-card p-6 flex justify-between items-start">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-2xl font-bold text-white">{result.test_case_title}</h1>
              {getTypeBadge(result.test_case_type)}
              <span className={`badge ${isPassed ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'}`}>
                {isPassed ? 'PASSED' : 'FAILED'}
              </span>
            </div>
            <p className="text-slate-400 text-sm">
              Executed on {new Date(result.created_at).toLocaleString()} • Duration: {result.duration_seconds}s
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Step-by-step execution */}
        <div className="glass-card overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-700/50 bg-slate-900/50">
            <h3 className="font-semibold text-white">Execution Steps</h3>
          </div>
          <div className="p-4 flex-1 overflow-y-auto max-h-[600px]">
            <div className="space-y-4">
              {result.step_results.map((step, idx) => (
                <div key={idx} className="flex gap-4">
                  <div className="mt-1">
                    {step.status === 'passed' ? (
                      <div className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-500 flex items-center justify-center border border-emerald-500/30 shadow-sm shadow-emerald-500/10">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
                      </div>
                    ) : (
                      <div className="w-6 h-6 rounded-full bg-red-500/20 text-red-500 flex items-center justify-center border border-red-500/30 shadow-sm shadow-red-500/10">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                      </div>
                    )}
                  </div>
                  <div className="flex-1 bg-slate-800/40 rounded-lg p-3 border border-slate-700/30">
                    <div className="flex justify-between items-start mb-1">
                      <div className="font-mono text-sm text-blue-300">
                        {step.action} {step.selector && <span className="text-slate-400">on {step.selector}</span>}
                      </div>
                      <div className="text-xs text-slate-500">{step.duration_ms}ms</div>
                    </div>
                    {step.error && (
                      <div className="mt-2 text-xs text-red-400 bg-red-500/10 p-2 rounded border border-red-500/20 font-mono overflow-x-auto">
                        {step.error}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* AI Analysis and Screenshot */}
        <div className="flex flex-col gap-6">
          {!isPassed && result.reasoning && (
            <div className="glass-card overflow-hidden border-red-500/30 shadow-red-500/5">
              <div className="p-4 border-b border-red-500/20 bg-red-500/5 flex items-center gap-2">
                <span className="text-xl">🤖</span>
                <h3 className="font-semibold text-white">AI Root Cause Analysis</h3>
              </div>
              <div className="p-5 text-slate-300 text-sm leading-relaxed">
                {result.reasoning}
              </div>
            </div>
          )}

          {!isPassed && result.step_results.find(s => s.screenshot_b64) && (
            <div className="glass-card overflow-hidden flex-1">
              <div className="p-4 border-b border-slate-700/50 bg-slate-900/50">
                <h3 className="font-semibold text-white">Failure Screenshot</h3>
              </div>
              <div className="p-4 bg-slate-950 flex items-center justify-center">
                <img 
                  src={`data:image/png;base64,${result.step_results.find(s => s.screenshot_b64).screenshot_b64}`}
                  alt="Failure point"
                  className="max-w-full rounded border border-slate-800 shadow-2xl"
                />
              </div>
            </div>
          )}
          
          {isPassed && (
            <div className="glass-card p-12 flex flex-col items-center justify-center text-center h-full border-emerald-500/20 bg-emerald-500/5">
              <div className="w-20 h-20 bg-emerald-500/20 rounded-full flex items-center justify-center mb-6 text-emerald-400 text-4xl shadow-[0_0_30px_rgba(16,185,129,0.2)]">
                ✓
              </div>
              <h3 className="text-2xl font-bold text-white mb-2">Execution Successful</h3>
              <p className="text-emerald-400/80">All steps completed without errors.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
