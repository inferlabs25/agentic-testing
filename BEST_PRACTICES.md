# Best Practices & Developer Handbook

Guidelines for using and extending the AI Agentic Testing Tool.

---

## Table of Contents

1. [Recording Best Practices](#recording-best-practices)
2. [Test Design Principles](#test-design-principles)
3. [Code Standards](#code-standards)
4. [Performance Guidelines](#performance-guidelines)
5. [Security Best Practices](#security-best-practices)
6. [Testing Strategy](#testing-strategy)
7. [Debugging Techniques](#debugging-techniques)
8. [Common Patterns](#common-patterns)
9. [Optimization Tips](#optimization-tips)

---

## Recording Best Practices

### 1. Focus & Clarity

**✅ Do:**
- Record one specific user journey at a time
- 5-10 steps per session is ideal
- Clear, intentional actions (not random clicking)
- Wait 2-3 seconds on each page for snapshots

**❌ Don't:**
- Record 30+ steps in one session (too complex for AI)
- Switch between multiple unrelated tasks
- Use the browser's back button excessively
- Record while system is slow/unresponsive

### 2. Optimal Recording Pattern

```
[Navigate to start page]
  ↓
[Wait for page load]
  ↓
[Perform primary action] (login, search, etc)
  ↓
[Wait 2-3 seconds]
  ↓
[Perform secondary action] (fill form, select item)
  ↓
[Wait 2-3 seconds]
  ↓
[Verify result] (check success message, new page)
  ↓
[Stop recording]
```

### 3. Element Interaction Best Practices

**For clicks:**
- Click on visible, interactive elements (buttons, links)
- Avoid clicking on invisible or disabled elements
- Wait for any animations to complete before clicking

**For form filling:**
- Fill required fields first
- Use realistic test data (real email format, etc)
- Don't fill fields prematurely (let validation run naturally)

**For navigation:**
- Use standard page navigation (links, buttons)
- Avoid manual URL entry when possible
- Let page fully load before proceeding

### 4. Recording Different Scenarios

**Happy Path (Primary Flow):**
```
Login → Dashboard → Find Item → Add to Cart → Checkout
Optimal: 6-8 steps, all actions successful
```

**Error Handling:**
```
Login → Enter Wrong Password → See Error Message
Optimal: 3-4 steps, demonstrates error handling
```

**Edge Cases:**
```
Search with Special Characters → Navigate Pagination → Load More
Optimal: 4-5 steps, covers boundary conditions
```

---

## Test Design Principles

### 1. Test Coverage Strategy

**AI generates 4 test types automatically:**

| Type | Purpose | Example |
|------|---------|---------|
| **Happy Path** | Successful user flow | Login with correct credentials → Dashboard |
| **Negative** | Error handling | Login with wrong password → Error message |
| **Edge Case** | Boundary conditions | Search with 500 characters → Handle gracefully |
| **Security** | Vulnerability detection | SQL injection attempt → Sanitized/rejected |

### 2. Test Assertion Strategy

Good assertions:
- ✅ "User sees dashboard after login"
- ✅ "Error message displays for invalid email"
- ✅ "Item appears in cart with correct price"

Weak assertions:
- ❌ "Page loads"
- ❌ "Something happened"
- ❌ "Button clicked"

### 3. Test Independence

**Each test should:**
- Run independently without setup
- Not depend on other tests
- Clean up after itself (implied by new browser)
- Produce predictable results

**Avoid:**
- Test data created by previous tests
- State assumptions from other tests
- Shared mutable resources

### 4. Test Maintainability

**Keep tests:**
- Focused on one behavior
- Named clearly (test name describes what it tests)
- Not brittle to minor UI changes
- Using generic selectors when possible

**Example test evolution:**

❌ Version 1 (Too specific):
```
selector: "div.login-container > form > input:nth-child(1)"
```

✅ Version 2 (Better):
```
selector: "input[name='email']"
```

✅ Version 3 (Best):
```
selector: "[data-testid='email-input']"
```

---

## Code Standards

### Backend Python

**Style Guide: PEP 8**

```python
# ✅ Good: Clear naming, proper spacing
def analyse_session(session_id: str, db: DBSession) -> AnalyseResponse:
    """Analyse session and generate test cases."""
    session = db.query(RecordingSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404)
    
    # Process session
    result = process_session(session)
    return AnalyseResponse(status="ok", data=result)


# ❌ Bad: Unclear naming, inconsistent spacing
def process(sid, database):
    s=database.query(RecordingSession).get(sid)
    if not s: raise HTTPException(status_code=404)
    return s
```

**Docstring Format:**
```python
def execute_test(test_case_id: str, headless: bool = True) -> TestResult:
    """
    Execute a test case in a real browser.
    
    Args:
        test_case_id: ID of test to run
        headless: Run in headless mode (default True)
    
    Returns:
        TestResult with step-by-step execution details
    
    Raises:
        HTTPException: 404 if test not found, 400 if not approved
    """
    pass
```

**Type Hints:**
```python
# ✅ Always use type hints
def get_session(session_id: str) -> Optional[SessionDetail]:
    ...

# ❌ Avoid bare types
def get_session(session_id):
    ...
```

### Frontend JavaScript/React

**Code Style: ESLint Config**

```javascript
// ✅ Good: Clear components, proper hooks usage
function SessionList() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchSessions = async () => {
      setLoading(true);
      try {
        const response = await api.get('/api/sessions');
        setSessions(response.data);
      } catch (error) {
        console.error('Failed to fetch sessions:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchSessions();
  }, []);

  return (
    <div className="session-list">
      {loading ? <Spinner /> : sessions.map(s => <SessionCard key={s.id} session={s} />)}
    </div>
  );
}

// ❌ Bad: No error handling, unclear naming
function List() {
  const [data, setData] = useState();
  useEffect(() => {
    fetch('/api/sessions').then(r => r.json()).then(setData);
  });
  return <div>{data?.map(d => <div key={d.id}>{d.name}</div>)}</div>;
}
```

**Component Organization:**
```javascript
// ✅ Good structure
function SessionCard({ session }) {
  // 1. Hooks
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);
  
  // 2. Handlers
  const handleClick = () => navigate(`/sessions/${session.id}`);
  const handleDelete = () => { /* ... */ };
  
  // 3. Render
  return (
    <div className="card" onClick={handleClick}>
      <div className="card-header">{session.name}</div>
      <div className="card-body">{session.url}</div>
      <div className="card-footer">
        <button onClick={handleDelete}>Delete</button>
      </div>
    </div>
  );
}
```

---

## Performance Guidelines

### Backend Optimization

**1. Database Queries**
```python
# ❌ Bad: N+1 query problem
sessions = db.query(RecordingSession).all()
for session in sessions:
    test_count = db.query(TestCase).filter_by(session_id=session.id).count()
    # Runs 1 query for sessions + N queries for tests

# ✅ Good: Single query with relationship
from sqlalchemy.orm import joinedload
sessions = db.query(RecordingSession).options(joinedload(RecordingSession.test_cases)).all()
```

**2. API Response Pagination**
```python
# ❌ Bad: Return all results
@app.get("/api/sessions")
def list_sessions(db: DBSession = Depends(get_db)):
    return db.query(RecordingSession).all()  # Could be thousands!

# ✅ Good: Paginate results
@app.get("/api/sessions")
def list_sessions(skip: int = 0, limit: int = 20, db: DBSession = Depends(get_db)):
    return db.query(RecordingSession).offset(skip).limit(limit).all()
```

**3. Caching**
```python
from functools import lru_cache

# Cache expensive operations
@lru_cache(maxsize=100)
def get_session_detail(session_id: str):
    # This result is cached for repeated calls
    return build_session_detail(session_id)
```

### Frontend Optimization

**1. Component Memoization**
```javascript
// ❌ Bad: Re-renders on every parent update
function SessionCard({ session }) {
  return <div>{session.name}</div>;
}

// ✅ Good: Only re-renders if session changes
const SessionCard = React.memo(function SessionCard({ session }) {
  return <div>{session.name}</div>;
});
```

**2. Lazy Loading**
```javascript
// ✅ Good: Load components only when needed
const ResultDetail = React.lazy(() => import('./ResultDetail'));

function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/results/:id" element={<ResultDetail />} />
      </Routes>
    </Suspense>
  );
}
```

**3. Avoiding Unnecessary Renders**
```javascript
// ❌ Bad: useCallback not used, causes re-renders
function SessionList({ onSelect }) {
  const handleSelect = (id) => onSelect(id);  // New function each render!
  return <SessionCard onSelect={handleSelect} />;
}

// ✅ Good: Memoize callback
const handleSelect = useCallback((id) => onSelect(id), [onSelect]);
return <SessionCard onSelect={handleSelect} />;
```

### Playwright Optimization

**1. Parallel Execution**
```env
# Run multiple tests simultaneously
MAX_CONCURRENT_TESTS=5
```

**2. Browser Reuse (Future Enhancement)**
```python
# Instead of launching new browser per test
# Reuse browser context between tests
browser = playwright.chromium.launch()
context1 = browser.new_context()
context2 = browser.new_context()
```

---

## Security Best Practices

### API Security

**1. Input Validation**
```python
# ✅ Always validate with Pydantic
from pydantic import BaseModel, constr

class EventBatch(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    events: List[EventItem]

# ❌ Never trust raw input
@app.post("/api/session/events")
def receive_events(session_id: str, events: list):  # Dangerous!
    ...
```

**2. SQL Injection Prevention**
```python
# ✅ Use parameterized queries (SQLAlchemy does this)
session = db.query(RecordingSession).filter(RecordingSession.id == session_id).first()

# ❌ Never construct SQL strings
result = db.execute(f"SELECT * FROM sessions WHERE id = '{session_id}'")  # SQL Injection!
```

**3. CORS Configuration**
```python
# ✅ Specific allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # NOT "*"
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ❌ Too permissive
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Unsafe!
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Data Security

**1. Sensitive Field Detection**
```python
SENSITIVE_FIELD_TYPES = {'password', 'secret', 'token', 'credit_card', 'ssn'}

def is_sensitive_field(selector: str, field_type: str) -> bool:
    return any(sensitive in selector.lower() or sensitive in field_type 
               for sensitive in SENSITIVE_FIELD_TYPES)

# Usage
if is_sensitive_field(selector, input_type):
    event.value = "[REDACTED]"  # Don't capture value
```

**2. API Key Storage**
```python
# ✅ Use environment variables
api_key = os.getenv("OPENAI_API_KEY")

# ❌ Never hardcode
api_key = "sk-ant-abc123"  # Dangerous!

# ❌ Never commit .env to git
# Add to .gitignore:
echo ".env" >> .gitignore
```

**3. Session Timeout**
```python
# Implement for production
SESSION_TIMEOUT = 3600  # 1 hour

@app.get("/api/sessions")
def list_sessions(
    current_user = Security(verify_token),  # Check token validity
    db: DBSession = Depends(get_db)
):
    return db.query(RecordingSession).all()
```

---

## Testing Strategy

### Unit Testing

**Backend Tests:**
```python
import pytest

def test_session_builder_creates_steps():
    """Test that SessionBuilder correctly groups events into steps."""
    events = [
        Event(event_type="navigate", timestamp=0),
        Event(event_type="click", timestamp=100),
        Event(event_type="fill", timestamp=200),
    ]
    
    builder = SessionBuilder(MockDB())
    steps = builder._group_into_steps(events)
    
    assert len(steps) == 2  # navigate creates 1 step, click creates 1 step
    assert steps[0].action == "navigate"
    assert steps[1].action == "click"

def test_selector_generation():
    """Test CSS selector generation for DOM elements."""
    element = MockElement(id="login-btn")
    selector = get_css_selector(element)
    assert selector == "#login-btn"
```

**Frontend Tests:**
```javascript
import { render, screen } from '@testing-library/react';
import SessionList from './Sessions';

test('displays sessions list', async () => {
  const mockSessions = [
    { id: '1', name: 'Session 1', url: 'https://example.com' }
  ];
  
  render(<SessionList sessions={mockSessions} />);
  
  expect(screen.getByText('Session 1')).toBeInTheDocument();
});
```

### Integration Testing

**API Testing:**
```python
def test_record_session_end_to_end():
    """Test complete session recording workflow."""
    client = TestClient(app)
    
    # 1. Receive events
    response = client.post("/api/session/events", json={
        "session_id": "test-123",
        "events": [{"event_type": "click", "timestamp": 0}]
    })
    assert response.status_code == 200
    
    # 2. Verify session created
    response = client.get("/api/sessions/test-123")
    assert response.status_code == 200
    assert response.json()["steps_count"] == 1
```

### Manual Testing Checklist

Before each release:
- [ ] Can record a complete session
- [ ] Session appears in dashboard
- [ ] Can trigger AI analysis
- [ ] Tests are generated correctly
- [ ] Can approve and run tests
- [ ] Test results display correctly
- [ ] Can see failure reasons
- [ ] No console errors
- [ ] No database errors
- [ ] Performance is acceptable

---

## Debugging Techniques

### Backend Debugging

**1. Using print() strategically**
```python
# ✅ Good: Informative logs
logger.info(f"Session {session_id}: received {len(events)} events")
logger.debug(f"Event: action={event.action}, selector={event.selector}")
logger.error(f"Failed to analyse: {error}", exc_info=True)

# ❌ Bad: Non-informative
print("ok")
print(session_id)
```

**2. Using Python Debugger**
```python
import pdb

# Add breakpoint where you want to pause
def analyse_session(session_id: str):
    session = get_session(session_id)
    pdb.set_trace()  # Program pauses here
    # Now you can inspect variables
    # Type 'p session' to print, 'c' to continue
    result = process(session)
```

**3. FastAPI Swagger UI**
- Visit http://localhost:8000/docs
- Try out endpoints interactively
- See request/response examples
- Easy debugging of API contracts

### Frontend Debugging

**1. Browser DevTools**
```javascript
// Console tab
console.log("Session:", session);  // View object
console.error("Error:", error);    // Red error message

// Network tab
// Watch API requests to http://localhost:8000/api/*
// See request payload and response

// React DevTools
// Inspector tab to see component tree
// Props and state values
```

**2. Using debugger statement**
```javascript
function SessionCard({ session }) {
  debugger;  // Execution pauses here when DevTools open
  
  return <div>{session.name}</div>;
}
```

**3. Conditional Logging**
```javascript
const isDev = process.env.NODE_ENV === 'development';

const debug = (...args) => {
  if (isDev) console.log(...args);
};

debug('Session loaded:', session);  // Only logs in development
```

### Extension Debugging

**1. Service Worker Console**
- chrome://extensions
- Find "AI Testing Agent"
- Click "Inspect views: service_worker"
- View background script logs

**2. Content Script Console**
- Right-click page → Inspect
- Console tab
- Add logging to content.js

**3. Network Inspection**
- DevTools Network tab
- Filter by XHR/Fetch
- Look for POST to localhost:8000/api/session/events
- Verify event payload

---

## Common Patterns

### Error Handling Pattern

**Backend:**
```python
@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    session = db.query(RecordingSession).filter_by(session_id=session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
    
    try:
        detail = SessionBuilder(db).build(session_id)
        return detail
    except Exception as e:
        logger.error(f"Error building session: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to build session"
        )
```

**Frontend:**
```javascript
const fetchSession = async (sessionId) => {
  setLoading(true);
  setError(null);
  
  try {
    const response = await api.get(`/api/sessions/${sessionId}`);
    setSession(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || 'Failed to load session';
    setError(message);
    console.error('Fetch error:', error);
  } finally {
    setLoading(false);
  }
};
```

### Async Operation Pattern

**Backend with Background Job:**
```python
# Start long-running operation
@app.post("/api/sessions/{session_id}/analyse")
def analyse_session(session_id: str, background_tasks: BackgroundTasks):
    # Validate session exists
    session = db.query(RecordingSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404)
    
    # Schedule background task
    background_tasks.add_task(run_analysis, session_id)
    
    return {"status": "analysis_started"}

async def run_analysis(session_id: str):
    """Run analysis in background without blocking response."""
    session = get_session(session_id)
    tests = analyse_session(session)
    save_tests(tests)
```

### State Management Pattern

**Frontend:**
```javascript
function SessionManager() {
  const [state, setState] = useState({
    sessions: [],
    selected: null,
    loading: false,
    error: null
  });

  const updateState = (updates) => {
    setState(prev => ({ ...prev, ...updates }));
  };

  const loadSessions = async () => {
    updateState({ loading: true, error: null });
    try {
      const data = await api.get('/api/sessions');
      updateState({ sessions: data, loading: false });
    } catch (error) {
      updateState({ error: error.message, loading: false });
    }
  };

  return (
    <div>
      {state.loading && <Spinner />}
      {state.error && <Error message={state.error} />}
      {state.sessions.map(s => <SessionCard key={s.id} session={s} />)}
    </div>
  );
}
```

---

## Optimization Tips

### Quick Wins

1. **Add database indexes** — Huge performance boost for queries
   ```bash
   sqlite3 test.db "CREATE INDEX idx_session_created ON sessions(created_at DESC);"
   ```

2. **Enable gzip compression** — Reduce API response size
   ```python
   from fastapi.middleware.gzip import GZIPMiddleware
   app.add_middleware(GZIPMiddleware, minimum_size=1000)
   ```

3. **Lazy load components** — Reduce initial page load
   ```javascript
   const ResultDetail = React.lazy(() => import('./ResultDetail'));
   ```

4. **Cache AI responses** — Avoid duplicate analysis
   ```python
   @cache.cached(timeout=3600)
   def analyse_session(session_id: str):
       return run_analysis(session_id)
   ```

### Monitoring Checklist

- [ ] API response times < 500ms (excluding AI)
- [ ] Frontend initial load < 3s
- [ ] Database queries < 100ms
- [ ] Test execution stability > 95%
- [ ] Error rate < 1%
- [ ] Memory usage stable
- [ ] CPU usage reasonable

### Profiling Tools

**Backend:**
```bash
# Profile endpoint
python -m cProfile -s cumsum main.py

# Line profiler
pip install line_profiler
kernprof -l -v executor.py
```

**Frontend:**
```javascript
// React Profiler API
performance.mark('test-start');
// ... code ...
performance.mark('test-end');
performance.measure('test', 'test-start', 'test-end');
```

---

## Production Readiness Checklist

- [ ] All endpoints documented
- [ ] Error handling complete
- [ ] Unit tests written
- [ ] Integration tests passing
- [ ] Security review done
- [ ] Performance tested
- [ ] Logging configured
- [ ] Error tracking setup
- [ ] Database backups scheduled
- [ ] API key rotated
- [ ] CORS properly configured
- [ ] Rate limiting enabled
- [ ] Database indexes created
- [ ] Deployment documented
- [ ] Rollback plan ready

---

**Questions?** Refer to main [DOCUMENTATION.md](./DOCUMENTATION.md) for comprehensive reference.
