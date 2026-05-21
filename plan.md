# AI Agentic Testing Tool — 1-Week POC Implementation Plan

## Goal

Build the core loop in one week to demonstrate to investors and architects:
**Record a web session → AI understands it → Generates test cases → Executes them → Shows pass/fail with plain-language reasoning.**

---

## What You Build (and What You Skip)

### Build this week
- Chrome browser extension (capture agent)
- Python FastAPI backend
- Claude AI understanding and test generation
- Playwright Python execution engine
- Claude reasoning engine (why did it fail)
- React frontend UI (3 screens)

### Skip this week
- Mobile / ERP proxy
- Multi-tenancy and RBAC
- Billing and secrets management
- Learning layer and LoRA fine-tuning
- Production hardening and CI/CD
- Authentication

---

## Tech Stack

| Component | Technology | Reason |
|---|---|---|
| Browser extension | Chrome MV3, vanilla JS | Zero dependencies, ships in 1 day |
| Backend | Python 3.11 + FastAPI + Uvicorn | Async, clean, best AI/ML ecosystem |
| Database | SQLite via SQLAlchemy | Zero setup, swap to Postgres later with no code change |
| AI | Anthropic Python SDK (`anthropic`) | Official SDK, async support, multimodal |
| Test execution | Playwright Python | Same Playwright, Python API — consistent stack |
| Frontend | React + Vite + Tailwind CSS | Fast to build, clean UI |

---

## Repository Structure

```
/poc
  /extension
    manifest.json          ← Chrome MV3 manifest
    content.js             ← DOM observer + event capture
    background.js          ← batches and sends to backend

  /backend
    main.py                ← FastAPI app + all routes
    models.py              ← SQLAlchemy DB models
    schemas.py             ← Pydantic request/response schemas
    database.py            ← SQLite engine + session setup
    session_builder.py     ← groups raw events into session object
    analyser.py            ← Claude understanding + test generation
    executor.py            ← Playwright Python execution engine
    reasoning.py           ← Claude failure root cause analysis
    requirements.txt

  /frontend
    src/
      App.jsx
      Sessions.jsx
      TestCases.jsx
      ResultDetail.jsx
    vite.config.js
    tailwind.config.js
```

---

## Day-by-Day Plan

---

### Day 1 — Project Setup + Browser Capture Agent

**Goal:** Extension installed, events arriving in backend terminal.

**Extension tasks:**
- Create `manifest.json` with MV3 permissions: `activeTab`, `tabs`, `storage`, `scripting`
- Write `content.js` with:
  - `MutationObserver` watching DOM changes
  - `fetch` and `XHR` interceptors for network calls
  - Click, input, and navigation event listeners
  - Full DOM snapshot on each page navigation
- Write `background.js` to:
  - Receive events from content script via `chrome.runtime`
  - Batch events and POST to `http://localhost:8000/api/session/events` every 2 seconds

**Backend tasks:**
- Set up FastAPI app in `main.py`
- Create `database.py` with SQLite engine and SQLAlchemy session
- Create `models.py` with `Session` and `Event` tables
- Create `schemas.py` with Pydantic `EventBatch` model
- Implement `POST /api/session/events` endpoint — validates and saves to SQLite
- Add CORS middleware for React on `localhost:5173`

**End of day check:** Install extension in Chrome, browse any website, confirm timestamped structured events appear in the backend.

---

### Day 2 — Screenshot Capture + Session Packaging

**Goal:** Clean structured session JSON object ready to feed to Claude.

**Extension tasks:**
- Add `chrome.tabs.captureVisibleTab()` — triggered on every navigation and significant DOM mutation
- Send base64 PNG screenshot alongside each DOM snapshot

**Backend tasks:**
- Write `session_builder.py` — `SessionBuilder` class that groups raw events by `session_id` into structured steps:

```python
{
  "session_id": "abc123",
  "url": "https://example.com",
  "steps": [
    {
      "step_index": 1,
      "url": "https://example.com/login",
      "action": "fill",
      "selector": "#username",
      "value": "admin",
      "dom_snapshot": "<html>...</html>",
      "screenshot_b64": "iVBORw0KGgo...",
      "network_calls": [...]
    }
  ]
}
```

- Expose `GET /api/sessions` to list all sessions
- Expose `GET /api/sessions/{session_id}` to return the full packaged session object

**End of day check:** Record a 5-step login flow, call `GET /api/sessions/{id}`, confirm clean structured JSON with screenshots.

---

### Day 3 — Claude AI Understanding + Test Generation

**Goal:** AI-generated test cases written to database from a real recorded session.

**Backend tasks — `analyser.py`:**

Two sequential Claude API calls.

**Call 1 — Application understanding:**
```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot_b64
                }
            },
            {
                "type": "text",
                "text": """You are a senior QA engineer. Analyse this recorded user session.
                Identify:
                1. What type of application this is
                2. What the user was doing (the flow)
                3. All form fields and their validation rules
                4. All API endpoints called and their purpose
                5. What constitutes success and failure for this flow
                Return as structured JSON only."""
            }
        ]
    }]
)
```

**Call 2 — Test case generation:**
```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    messages=[{
        "role": "user",
        "content": f"""Based on this application understanding:
        {understanding_json}

        Generate test cases. For each test case provide:
        - title
        - type: happy / negative / edge / security
        - steps as Playwright actions (selector, action, value)
        - expected_result
        - reason (why this test matters)

        Return as a JSON array of test cases only."""
    }]
)
```

- Add `TestCase` table to `models.py` with `status` column defaulting to `draft`
- Save all generated test cases to SQLite
- Expose `GET /api/sessions/{session_id}/testcases` endpoint

**End of day check:** Record a login flow, call the analyser, see 8–15 AI-generated test cases of mixed types in the database.

---

### Day 4 — Playwright Execution Engine

**Goal:** Execute a single approved test case, record step-by-step results.

**Backend tasks — `executor.py`:**

```python
from playwright.sync_api import sync_playwright
import base64

def execute_test_case(test_case):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible for demo
        page = browser.new_page()

        for step in test_case.steps:
            try:
                if step["action"] == "navigate":
                    page.goto(step["value"])
                elif step["action"] == "click":
                    page.click(step["selector"])
                elif step["action"] == "fill":
                    page.fill(step["selector"], step["value"])
                elif step["action"] == "assert_text":
                    expect(page.locator(step["selector"])).to_have_text(step["value"])
                elif step["action"] == "assert_visible":
                    expect(page.locator(step["selector"])).to_be_visible()

                results.append({"step": step["step_index"], "status": "passed"})

            except Exception as e:
                # capture screenshot on failure
                screenshot = page.screenshot()
                screenshot_b64 = base64.b64encode(screenshot).decode()
                results.append({
                    "step": step["step_index"],
                    "status": "failed",
                    "error": str(e),
                    "screenshot_b64": screenshot_b64
                })
                break  # stop on first failure

        browser.close()
    return results
```

- Basic self-healing fallback: if selector fails, retry using `page.get_by_text()` or `page.get_by_role()`
- Add `Result` and `StepResult` tables to `models.py`
- Expose `POST /api/testcases/{test_id}/approve` — changes status to `approved`
- Expose `POST /api/testcases/{test_id}/execute` — runs executor, saves results

**End of day check:** Approve one test case, click execute, see step-by-step pass/fail in database with failure screenshot.

---

### Day 5 — Reasoning Engine + Results API

**Goal:** Full backend loop complete — execution result includes plain-language root cause.

**Backend tasks — `reasoning.py`:**

```python
def analyse_failure(test_case, failed_step, screenshot_b64, network_logs):
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_b64
                    }
                },
                {
                    "type": "text",
                    "text": f"""A test case failed. Analyse and explain the root cause.

                    Test: {test_case.title}
                    Expected: {test_case.expected_result}
                    Failed at step: {failed_step.description}
                    Error message: {failed_step.error}
                    Network calls at failure: {network_logs}

                    In 2-3 sentences, explain exactly why it failed.
                    Be specific — mention field names, values, and HTTP status codes.
                    Do not be generic. Do not say 'the test failed because of an error'."""
                }
            ]
        }]
    )
    return response.content[0].text
```

**All API endpoints (final list):**

```
GET  /api/sessions                          — list all recorded sessions
GET  /api/sessions/{session_id}             — get session detail
GET  /api/sessions/{session_id}/testcases   — list generated test cases
POST /api/sessions/{session_id}/analyse     — trigger Claude analysis
POST /api/testcases/{test_id}/approve       — approve for execution
POST /api/testcases/{test_id}/execute       — execute test case
GET  /api/results/{result_id}               — get result with reasoning
```

**End of day check:** Run full loop end to end — record → analyse → approve → execute → get result with reasoning paragraph.

---

### Day 6 — React Frontend

**Goal:** Working UI with 3 screens, wired to backend.

**Screen 1 — Sessions list (`Sessions.jsx`):**
- Table of all recorded sessions
- Columns: session name, URL, date recorded, steps captured, status
- Button: "Analyse with AI" → calls `POST /api/sessions/{id}/analyse`
- Click row → navigate to test cases screen

**Screen 2 — Test cases (`TestCases.jsx`):**
- Table of AI-generated test cases for selected session
- Columns: title, type (colour-coded badge: green=happy, red=negative, orange=edge, purple=security), steps count, status
- Per row: "Approve" button and "Execute" button
- Bulk approve all button

**Screen 3 — Result detail (`ResultDetail.jsx`):**
- Test case title and type at top
- Step-by-step list — each step with pass ✓ or fail ✗ icon and duration
- On failed step: show screenshot inline
- At bottom: Claude reasoning in a highlighted box with label "AI root cause analysis"

**Vite proxy config** (to avoid CORS issues in dev):
```js
// vite.config.js
export default {
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
}
```

**End of day check:** Full UI working — can record, trigger analysis, see test cases, approve, execute, and see result with reasoning — all from the browser.

---

### Day 7 — Integration, Polish + Demo Preparation

**Goal:** Reliable end-to-end demo ready to present.

**Tasks:**
- Run the full loop 4–5 times on different public demo apps (see below)
- Fix any selector issues, Claude output parsing errors, or UI rough edges
- Make one test case deliberately fail to showcase the reasoning engine
- Add a loading spinner in React while Claude is analysing
- Add a "New Recording" button that opens the extension
- Test on a clean machine to confirm setup instructions work

**Demo apps to use:**
- `https://the-internet.herokuapp.com` — login, form authentication, checkboxes
- `https://demoqa.com` — rich forms, date pickers, tables
- `https://opensource-demo.orangehrmlive.com` — HR ERP-style app with login and dashboards

**Demo script (10 minutes):**
1. Open Chrome with extension installed, navigate to demo app
2. Record a login + form submission flow (60 seconds)
3. Stop recording, open UI — show session captured
4. Click "Analyse with AI" — show test cases appearing (happy, negative, edge, security)
5. Approve test cases, click Execute
6. Show step-by-step execution in browser (headless=False so it is visible)
7. Show result screen — pass/fail per step, screenshot on failure
8. Show AI reasoning paragraph — "it failed because..."
9. Show architecture diagram — explain the full product vision

---

## How to Run

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
playwright install chromium
cp .env.example .env          # add your ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000

# 2. Frontend
cd frontend
npm install
npm run dev                   # runs on localhost:5173

# 3. Extension
# Chrome → Settings → Extensions → Developer mode ON
# Click "Load unpacked" → select the /extension folder
```

**`.env` file:**
```
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=sqlite:///./poc.db
```

---

## `requirements.txt`

```
fastapi
uvicorn[standard]
sqlalchemy
alembic
pydantic
anthropic
playwright
python-dotenv
pillow
```

---

## What This POC Proves

| Claim | Demonstrated by |
|---|---|
| Zero-setup capture | Extension installs in 30 seconds, no config needed |
| AI understands any app | Analyse button works on any website without training |
| Automatic test generation | 8–15 test cases appear from a single recorded session |
| All test types covered | Happy, negative, edge, and security cases generated |
| Real execution | Playwright runs tests visibly in the browser |
| Better than pass/fail | Claude explains exactly why each failure happened |

---

## Next Steps After POC

Once the POC is validated, the next phase adds:

1. ERP proxy for Oracle Apex and SAP Fiori
2. Mobile capture via Appium
3. Multi-tenancy with PostgreSQL and row-level security
4. Human review layer with approval workflow
5. Flow graph reconstruction in Neo4j
6. Self-healing selector engine with pgvector
7. Learning layer and app-specific fine-tuning
8. Full platform layer — RBAC, billing, integrations
