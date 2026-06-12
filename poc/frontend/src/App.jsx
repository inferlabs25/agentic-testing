import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import Sessions from './Sessions';
import TestCases from './TestCases';
import ResultDetail from './ResultDetail';
import SuiteRunDetail from './SuiteRunDetail';

function Sidebar() {
  const location = useLocation();
  
  const isActive = (path) => {
    return location.pathname === path || (path !== '/' && location.pathname.startsWith(path));
  };

  return (
    <div className="w-64 bg-slate-900 border-r border-slate-800 h-screen flex flex-col">
      <div className="p-6 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-blue-500/20">
          A
        </div>
        <div>
          <h1 className="text-lg font-bold text-white leading-tight">AI Testing</h1>
          <p className="text-xs text-slate-400">Agentic QA Platform</p>
        </div>
      </div>
      
      <nav className="flex-1 px-4 mt-6">
        <Link 
          to="/" 
          className={`flex items-center gap-3 px-4 py-3 rounded-lg mb-2 transition-colors ${
            isActive('/') 
              ? 'bg-blue-600/10 text-blue-400 border border-blue-500/20' 
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
          Sessions
        </Link>
      </nav>
      
      <div className="p-4 m-4 rounded-xl bg-slate-800/50 border border-slate-700">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          <span className="text-xs font-medium text-slate-300">System Online</span>
        </div>
        <p className="text-xs text-slate-500">Connected to Playwright execution engine</p>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-slate-950 text-slate-200 font-sans overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto p-8">
            <Routes>
              <Route path="/" element={<Sessions />} />
              <Route path="/sessions/:sessionId/testcases" element={<TestCases />} />
              <Route path="/results/:resultId" element={<ResultDetail />} />
              <Route path="/suite-runs/:runId" element={<SuiteRunDetail />} />
            </Routes>
          </div>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
