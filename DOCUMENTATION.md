# AI Agentic Testing Tool — Complete Documentation

**Version:** 0.1.0  
**Last Updated:** 2026-05-25  
**Purpose:** Automated test generation and execution through AI-powered session analysis

---

## Client-Pilot Implementation Update

This repository now includes the enterprise client-pilot hardening layer. The current implementation uses the OpenAI SDK with `gpt-4o`, job-based analysis/execution endpoints, ready-vs-review test classification, suite runs, structured failure categories, artifact capture, explicit CORS configuration, optional pilot API-key authentication, and report/export endpoints.

Use these current API routes for the upgraded pilot:
- `POST /api/sessions/{session_id}/analyse` returns `{ job_id, status }`
- `GET /api/jobs/{job_id}` polls analysis, execution, and suite progress
- `POST /api/testcases/{test_id}/execute` returns `{ job_id, status }`
- `POST /api/sessions/{session_id}/run-suite`
- `POST /api/suite-runs/{run_id}/retry-failed`
- `GET /api/suite-runs/{run_id}/report`
- `GET /api/sessions/{session_id}/export/playwright`

Older references below to Claude/Anthropic or `/api/test/...` are legacy POC notes and should be treated as superseded by this section.

---

## Table of Contents

1. [Product Overview](#product-overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [System Components](#system-components)
5. [Setup & Installation](#setup--installation)
6. [API Reference](#api-reference)
7. [Database Schema](#database-schema)
8. [Frontend Guide](#frontend-guide)
9. [Browser Extension Guide](#browser-extension-guide)
10. [Usage Workflows](#usage-workflows)
11. [Development Guide](#development-guide)
12. [Troubleshooting](#troubleshooting)

---

## Product Overview

### What is AI Agentic Testing Tool?

A proof-of-concept (POC) platform that automates test case generation from real user interactions. The system records browser sessions, uses Claude AI to understand the application flow, generates test cases covering multiple scenarios, and executes them using Playwright with AI-powered failure analysis.

### Core Value Proposition

**Record → Understand → Generate → Execute → Reason**

1. **Record:** Chrome extension captures all user interactions (clicks, form fills, navigation)
2. **Understand:** Claude AI analyzes the recording to comprehend application behavior
3. **Generate:** AI generates multiple test cases (happy path, negative, edge cases, security)
4. **Execute:** Playwright runs tests in a real browser environment with automatic overlay dismissal
5. **Reason:** AI provides plain-language explanations for test failures

### Target Users

- QA Engineers looking to automate test case creation
- Product teams needing rapid test coverage during development
- Developers validating application behavior across multiple scenarios

### Key Capabilities

- 🎯 **Intelligent Recording:** Captures DOM events, network calls, screenshots, and page snapshots
- 🤖 **AI-Powered Analysis:** Claude understands user flow and application intent
- 📝 **Auto Test Generation:** Creates diverse test scenarios (happy path, negative, edge, security)
- ▶️ **Real Browser Execution:** Playwright-based execution with self-healing selectors
- 🔍 **Failure Analysis:** AI explains why tests failed in plain language
- 🎨 **Intuitive UI:** React-based dashboard for session management and result review

---

## Architecture

### System Overview

```
┌─────────────────────┐
│  User Browser       │
│  ┌───────────────┐  │
│  │   Webpage     │  │
│  │   Under Test  │  │
│  └────────┬──────┘  │
│           │         │
│  ┌────────▼──────┐  │
│  │  Chrome Ext   │  │
│  │  (Recorder)   │  │
│  └────────┬──────┘  │
└───────────┼──────────┘
            │ (HTTP POST)
            │ Event batches
            ▼
┌─────────────────────────────────────────┐
│      FastAPI Backend (Port 8000)        │
├─────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────────┐  │
│  │   Database  │  │  Session Builder │  │
│  │  (SQLite)   │  │  & Validator     │  │
│  └─────────────┘  └──────────────────┘  │
│                                          │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │   Analyser  │  │  Executor        │  │
│  │  (Claude AI)│  │  (Playwright)    │  │
│  └─────────────┘  └──────────────────┘  │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Reasoning Engine (Claude AI)    │   │
│  │  (Failure Analysis)              │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
            │ (HTTP GET/POST)
            │ JSON responses
            ▼
┌─────────────────────────────────────────┐
│   React Frontend (Port 5173)            │
├─────────────────────────────────────────┤
│  ┌──────────────┐  ┌─────────────────┐  │
│  │   Sessions   │  │   Test Cases    │  │
│  │   List View  │  │   Management    │  │
│  └──────────────┘  └─────────────────┘  │
│  ┌──────────────────────────────────┐   │
│  │      Result Detail View          │   │
│  │   (Step-by-step execution)       │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Data Flow

1. **Recording Phase:**
   - Extension captures events in batches every 2 seconds
   - Events include: clicks, form fills, navigation, network calls, DOM snapshots, screenshots
   - Events are sent to backend `/api/session/events` endpoint
   - Backend stores events in SQLite and updates session step count

2. **Analysis Phase:**
   - Frontend triggers `/api/sessions/{session_id}/analyse` endpoint
   - Backend builds structured session from raw events using SessionBuilder
   - Claude AI "understands" the session (multimodal: text + screenshots)
   - Claude AI generates test cases with different coverage types
   - Test cases are validated and stored in database

3. **Execution Phase:**
   - User approves test cases from frontend
   - Frontend triggers `/api/test/{test_case_id}/execute` endpoint
   - Playwright executes each step in a real browser
   - Screenshots captured on each step for evidence
   - Results recorded with pass/fail status and detailed step results

4. **Reasoning Phase:**
   - If a test fails, Claude AI analyzes failure context
   - Analyzes failed step, screenshot, network logs
   - Provides plain-language root cause explanation
   - Results displayed in frontend with actionable insights

---

## Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Browser Extension** | Chrome MV3 (Manifest V3) | Latest | Event capture & recording |
| **Frontend** | React | 19.2.6 | Web UI for dashboard |
| **Frontend Builder** | Vite | 8.0.12 | Fast build tooling |
| **Frontend Styling** | Tailwind CSS | 4.3.0 | Utility-first CSS |
| **Frontend Routing** | React Router | 7.15.1 | Client-side navigation |
| **Backend** | Python FastAPI | Latest | REST API server |
| **Backend Server** | Uvicorn | Latest (via fastapi) | ASGI server |
| **Database** | SQLite | Latest | Data persistence |
| **ORM** | SQLAlchemy | Latest | Database abstraction |
| **Validation** | Pydantic | Latest | Request/response schemas |
| **Test Execution** | Playwright Python | Latest | Browser automation |
| **AI Integration** | OpenAI SDK (Claude via Anthropic) | 1.40.0+ | LLM integration |
| **HTTP Client** | Axios | 1.16.1 | Frontend API requests |

### Why These Choices?

- **Chrome MV3:** Future-proof extension development, zero dependencies
- **FastAPI:** Async support, clean Pythonic API, excellent for AI/ML
- **SQLite:** Zero-setup persistence, easy migration to PostgreSQL later
- **Playwright:** Cross-browser support, Python API consistency with backend
- **React + Vite:** Rapid development, hot module replacement, minimal bundle size
- **Claude/Anthropic:** Superior multimodal understanding, better at explaining failures

---

## System Components

### 1. Browser Extension (Chrome MV3)

#### Purpose
Captures user interactions and page state to record testing workflows.

#### Files
- `manifest.json` — Extension configuration and permissions
- `content.js` — DOM observer and event capture logic
- `background.js` — Event batching and backend communication
- `popup.html` / `popup.js` — Recording control UI

#### Permissions
```json
{
  "permissions": ["activeTab", "tabs", "storage", "scripting"],
  "host_permissions": ["<all_urls>"]
}
```

#### Events Captured

| Event Type | Description |
|-----------|-------------|
| `click` | User clicks on elements (buttons, links, etc.) |
| `fill` | Text input into form fields |
| `input` | Input field value changes |
| `change` | Select/checkbox changes |
| `submit` | Form submission |
| `navigate` | Page navigation |
| `select` | Dropdown selection |
| `hover` | Mouse hover over interactive elements |
| `dom_snapshot` | Full DOM tree state (text representation) |
| `screenshot` | Page screenshot (base64 encoded) |
| `network` | HTTP requests with method, URL, status |

#### Event Data Structure

```javascript
{
  event_type: "click",           // Type of event
  timestamp: 1234567890.123,     // Milliseconds since start
  url: "https://app.example.com", // Current page URL
  selector: "button#submit",      // CSS selector of target element
  value: "Submit Order",          // Text value (for form inputs, button text)
  dom_snapshot: "...",            // HTML/text snapshot of page
  screenshot_b64: "...",          // Base64-encoded PNG
  network_data: {                 // For network events
    method: "POST",
    url: "https://api.example.com/orders",
    status: 200
  },
  meta: {                         // Element metadata
    accessibleName: "...",
    ariaLabel: "...",
    role: "button",
    tag: "button",
    dataTestId: "submit-btn"
  }
}
```

#### Recording Workflow

1. Extension waits for user to trigger recording (via popup)
2. Content script attaches event listeners to page
3. Events are captured and queued in memory
4. Every 2 seconds, background script batches events and POSTs to backend
5. Batching continues until user stops recording
6. Session marked as complete, ready for analysis

#### Self-Healing Features

- Attempts to generate multiple selector variations (ID, data-testid, name, path)
- Captures element metadata for AI-assisted selector repair
- Records network calls to correlate with page state changes

---

### 2. Backend API Server

#### Purpose
Processes recorded sessions, orchestrates AI analysis, executes tests, and serves data to frontend.

#### Technology
- **Framework:** FastAPI (Python)
- **Server:** Uvicorn (ASGI)
- **Port:** 8000
- **CORS:** Enabled for localhost:5173 (React frontend) and localhost:3000

#### Key Modules

##### `main.py` — FastAPI Application
Central API server with all route handlers.

**Lifecycle:**
- On startup: Creates database tables via SQLAlchemy
- CORS middleware: Allows cross-origin requests from frontend

##### `database.py` — SQLite Setup
SQLAlchemy engine and session configuration.

**Features:**
- SQLite database at workspace root
- SQLAlchemy ORM for object-relational mapping
- Session management via dependency injection

##### `models.py` — Data Models
SQLAlchemy ORM models representing database tables.

**Tables:**
1. **RecordingSession** — Top-level recording session
2. **Event** — Individual captured event
3. **TestCase** — Generated test case
4. **TestResult** — Test execution result
5. **StepResult** — Individual step within test result

##### `schemas.py` — Request/Response Validation
Pydantic models for API contract definition.

**Key Schemas:**
- `EventBatch` — Incoming events from extension
- `SessionSummary` — Session list view data
- `SessionDetail` — Full session with all steps
- `TestCaseResponse` — Test case details
- `TestResultResponse` — Execution results with reasoning

##### `session_builder.py` — Session Reconstruction
Converts raw events into structured session steps.

**Logic:**
- Groups events chronologically into user actions
- Attaches latest DOM snapshot and screenshot to each step
- Buffers network calls and associates with steps
- Coalesces multiple input events into single "fill" action
- Filters out non-action events (metadata only)

##### `analyser.py` — AI Understanding & Test Generation
Claude AI integration for session analysis and test case generation.

**Two-Phase Process:**

**Phase 1: Understand Session**
- Input: Session detail (steps, screenshots, network calls)
- Claude multimodal analysis: text descriptions + up to 5 screenshots
- Output: JSON understanding including:
  - Application purpose and user flow
  - Key interactions identified
  - Expected behaviors
  
**Phase 2: Generate Test Cases**
- Input: Session understanding
- Claude generates diverse test cases:
  - **Happy path:** Exact recreation of recorded flow
  - **Negative tests:** Invalid inputs, error handling
  - **Edge cases:** Boundary conditions, special inputs
  - **Security tests:** SQL injection, XSS attempts
- Output: Test cases with:
  - Steps (action, selector, value)
  - Expected results
  - Reason for test (why it matters)

**Normalization:**
- Validates generated selectors against recorded session
- Replaces text selectors with actual recorded CSS selectors
- Fixes malformed assertions (e.g., assert_text with null value)

##### `executor.py` — Playwright Test Execution
Python Playwright wrapper for real browser test execution.

**Execution Flow:**
1. Launch browser instance (Chrome/Firefox/WebKit)
2. Navigate to test start URL
3. For each step:
   - Execute action (click, fill, navigate, assert)
   - Dismiss overlay popups automatically (cookies, consent, etc.)
   - Capture screenshot
   - Record success/failure
4. On failure: Capture screenshot and error message
5. Return step-by-step results

**Features:**
- **Automatic Overlay Dismissal:** Detects and closes cookie banners, consent dialogs
- **Self-Healing Selectors:** Falls back to alternative selectors if primary fails
- **Screenshot Evidence:** Captures page state at each step
- **Network Logging:** Records HTTP calls during execution
- **Timeouts:** Configurable via environment variables
- **Cross-Platform:** Windows ProactorPolicy handling for Windows compatibility

**Actions Supported:**

| Action | Description |
|--------|-------------|
| `navigate` | Go to URL |
| `click` | Click element |
| `fill` | Clear and type text in field |
| `select` | Choose option from dropdown |
| `hover` | Hover over element |
| `assert_text` | Verify text appears |
| `assert_visible` | Verify element is visible |
| `submit` | Submit form |

##### `reasoning.py` — Failure Analysis
Claude AI for plain-language failure root cause analysis.

**Input:**
- Test title and expected result
- Failed step details (action, selector, error)
- Screenshot at failure (multimodal)
- Network logs around failure

**Output:**
- 2-3 sentence plain-language explanation
- Actionable root cause
- Examples: "Button not found because page is still loading", "Form validation blocked due to empty required field"

##### `step_validation.py` — Test Step Validation
Validates generated test steps against recorded session for feasibility.

**Checks:**
- Can selectors be found on recorded pages?
- Do actions make sense in sequence?
- Are text values reasonable?

---

### 3. Frontend Dashboard

#### Purpose
User interface for managing sessions, approving test cases, and reviewing results.

#### Technology
- **Framework:** React 19.2.6
- **Builder:** Vite 8.0.12
- **Styling:** Tailwind CSS 4.3.0
- **Routing:** React Router 7.15.1
- **HTTP Client:** Axios 1.16.1
- **Port:** 5173 (dev) / 5000 (prod)

#### Pages/Components

##### 1. **Sessions Page** (`Sessions.jsx`)
List of all recorded sessions with filtering and navigation.

**Features:**
- Display all sessions in table/card format
- Show: Name, URL, Status, Step count, Created date
- Filter by status (recording, completed, analysed)
- Click to view session details
- Delete session option
- Start new recording option

**Actions:**
- View session → Navigate to details
- Analyse session → Trigger AI analysis
- Download recording → Export session data
- Delete session → Remove from database

**Status Indicators:**
- `recording` — Session still capturing events
- `completed` — Recording finished, ready for analysis
- `analysing` — AI currently analyzing
- `analysed` — Analysis complete, test cases generated

##### 2. **Test Cases Page** (`TestCases.jsx`)
View and manage test cases for a session.

**Features:**
- List all generated test cases
- Show: Title, Type, Status, Created date
- Filter by type (happy path, negative, edge, security)
- Filter by status (draft, approved, running, passed, failed)

**Actions:**
- **Approve:** Move test from draft to approved status
- **Run Test:** Execute single test case
- **Run All:** Execute all approved tests
- **View Details:** See full test step breakdown
- **Delete:** Remove test case
- **Duplicate:** Clone test for modification

**Test Case Display:**
- Title (auto-generated by AI)
- Type badge (happy path, negative, edge, security)
- Expected result description
- Reason (why this test is important)
- Step count
- Latest result (passed/failed)

##### 3. **Result Detail Page** (`ResultDetail.jsx`)
Detailed view of test execution results.

**Features:**
- Overall test status (passed/failed)
- Test metadata (title, type, expected result)
- Step-by-step breakdown:
  - Step index and action
  - Selector and value
  - Status (passed/failed)
  - Screenshot at step
  - Error message (if failed)
  - Duration
- AI Reasoning:
  - Plain-language failure explanation (if test failed)
  - Root cause analysis
  - Actionable insights

**Visualizations:**
- Timeline of step execution with duration
- Screenshot carousel to review page state
- Diff highlighting for assertion failures
- Network call timeline

##### 4. **Sidebar Navigation** (`App.jsx`)
Persistent navigation and status indicator.

**Features:**
- Brand logo and product name
- Navigation links:
  - Sessions (main list)
  - Test Management (if session selected)
  - Results (if result selected)
- System status indicator:
  - Connected/disconnected to backend
  - Playwright execution engine status
  - Active session indicator

**Styling:**
- Dark theme (Slate 900 background)
- Blue accent colors for active/hover states
- Responsive design with hamburger menu on mobile

#### API Integration

All API calls use Axios with base URL `http://localhost:8000`:

```javascript
import axios from 'axios';
const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' }
});
```

**Frontend → Backend Communication:**
1. GET `/api/sessions` — Fetch all sessions
2. GET `/api/sessions/{session_id}` — Fetch session detail
3. POST `/api/sessions/{session_id}/analyse` — Trigger analysis
4. POST `/api/sessions/{session_id}/approve-tests` — Approve test cases
5. POST `/api/test/{test_case_id}/execute` — Execute single test
6. GET `/api/test/{test_case_id}/result` — Fetch test result
7. POST `/api/sessions/{session_id}/complete` — Mark recording complete

---

## Setup & Installation

### Prerequisites

- **Node.js** 18+ (for frontend)
- **Python** 3.11+ (for backend)
- **Chrome Browser** (for extension testing and Playwright)
- **OpenAI API Key** (for Claude via Anthropic SDK)
- **Git** (for cloning repository)

### Step 1: Clone Repository

```bash
cd /path/to/agentic-testing
git clone <repo-url> .
```

### Step 2: Backend Setup

#### Install Python Dependencies

```bash
cd poc/backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

#### Download Playwright Browsers

```bash
playwright install
```

#### Configure Environment Variables

Create `.env` file in `poc/backend/`:

```env
# OpenAI/Anthropic API Configuration
OPENAI_API_KEY=sk-...  # Your Claude API key
OPENAI_MODEL=gpt-4o    # Model to use

# Playwright Configuration
PLAYWRIGHT_ACTION_TIMEOUT_MS=5000
PLAYWRIGHT_POST_CLICK_SETTLE_MS=300
PLAYWRIGHT_POST_CLICK_NAVIGATION_TIMEOUT_MS=5000

# AI Configuration
AI_MAX_STEPS=10
AI_FIELD_CHAR_LIMIT=200
AI_MAX_NETWORK_CALLS_PER_STEP=3
AI_REASONING_TIMEOUT_SECONDS=20
AI_REASONING_MAX_RETRIES=0

# Database (optional, defaults to SQLite in current directory)
DATABASE_URL=sqlite:///./test.db

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

#### Start Backend Server

```bash
cd poc/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Frontend Setup

#### Install Dependencies

```bash
cd poc/frontend
npm install
```

#### Start Development Server

```bash
npm run dev
```

**Expected Output:**
```
  VITE v8.0.12  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

### Step 4: Chrome Extension Setup

#### Load Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (top right toggle)
3. Click "Load unpacked"
4. Navigate to `poc/extension/` folder and select
5. Extension appears in toolbar as "AI Testing Agent - Recorder"

#### Grant Permissions

When prompted, allow the extension:
- Access current tab and URL
- Script access to pages
- Storage access for session data

#### Verify Extension is Working

1. Click extension icon in toolbar
2. Popup shows "Start Recording" button
3. Navigate to any website and click "Start Recording"
4. Perform actions (clicks, form fills)
5. Verify events appear in backend logs:
   ```
   INFO: Received event batch from extension
   INFO: Saved 15 events for session abc123...
   ```

### Step 5: Verify Full Stack

1. **Backend Running:** `http://localhost:8000/docs` (SwaggerUI API docs)
2. **Frontend Running:** `http://localhost:5173/` (Sessions page)
3. **Extension Active:** Icon visible in Chrome toolbar
4. **Network Communication:** All services can reach each other

### Docker Option (Optional)

Create `docker-compose.yml` in root:

```yaml
version: '3.8'
services:
  backend:
    build: ./poc/backend
    ports:
      - "8000:8000"
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    volumes:
      - ./poc/backend:/app

  frontend:
    build: ./poc/frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
    volumes:
      - ./poc/frontend:/app
```

Then:
```bash
docker-compose up
```

---

## API Reference

### Base URL
```
http://localhost:8000
```

### Authentication
Current POC has no authentication. All endpoints are public.

### Common Response Format

**Success (2xx):**
```json
{
  "status": "ok",
  "data": { ... }
}
```

**Error (4xx/5xx):**
```json
{
  "detail": "Error message"
}
```

---

### 1. Event Ingestion

#### POST `/api/session/events`
Receive batch of captured events from browser extension.

**Request:**
```json
{
  "session_id": "abc-123-def",
  "events": [
    {
      "event_type": "click",
      "timestamp": 1234567890.123,
      "url": "https://example.com",
      "selector": "button#submit",
      "value": "Click Me",
      "dom_snapshot": "...",
      "screenshot_b64": "iVBORw0KGgoAAAANSUhEUgAAAA...",
      "network_data": null,
      "meta": { "role": "button", "tag": "button" }
    }
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "events_saved": 15
}
```

**Status Codes:**
- `200` — Events saved successfully
- `400` — Invalid request format
- `500` — Server error

---

### 2. Session Management

#### POST `/api/sessions/{session_id}/complete`
Mark recording session as completed.

**Response:**
```json
{
  "status": "ok",
  "session_id": "abc-123-def"
}
```

**Status Codes:**
- `200` — Session marked complete
- `404` — Session not found
- `400` — Session already completed

---

#### GET `/api/sessions`
List all recorded sessions.

**Query Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `status` | string | Filter by status (recording/completed/analysed) |
| `limit` | integer | Max results (default: 50) |
| `offset` | integer | Pagination offset (default: 0) |

**Response:**
```json
[
  {
    "session_id": "abc-123-def",
    "name": "Session abc123",
    "url": "https://example.com",
    "status": "analysed",
    "steps_count": 12,
    "created_at": "2026-05-25T10:30:00Z"
  }
]
```

**Status Codes:**
- `200` — Sessions retrieved
- `500` — Server error

---

#### GET `/api/sessions/{session_id}`
Get full session detail with all steps.

**Response:**
```json
{
  "session_id": "abc-123-def",
  "name": "Session abc123",
  "url": "https://example.com",
  "status": "analysed",
  "created_at": "2026-05-25T10:30:00Z",
  "steps": [
    {
      "step_index": 0,
      "action": "navigate",
      "url": "https://example.com",
      "selector": null,
      "value": "Home Page",
      "meta": null,
      "dom_snapshot": "<!DOCTYPE html>...",
      "screenshot_b64": "iVBORw0KGgoAAAANSUhEUgAAAA...",
      "network_calls": [
        {
          "method": "GET",
          "url": "https://api.example.com/config",
          "status": 200
        }
      ]
    },
    {
      "step_index": 1,
      "action": "click",
      "url": "https://example.com",
      "selector": "button.login-btn",
      "value": "Login",
      "meta": {
        "role": "button",
        "tag": "button",
        "ariaLabel": "Sign in to account"
      },
      "dom_snapshot": "...",
      "screenshot_b64": "...",
      "network_calls": []
    }
  ]
}
```

**Status Codes:**
- `200` — Session retrieved
- `404` — Session not found
- `500` — Server error

---

### 3. AI Analysis

#### POST `/api/sessions/{session_id}/analyse`
Trigger Claude AI to analyze session and generate test cases.

**Request Body:** (empty)

**Response:**
```json
{
  "status": "ok",
  "test_cases_generated": 12,
  "understanding": {
    "application_purpose": "E-commerce checkout system",
    "user_flow": "User logs in, adds product to cart, completes checkout",
    "key_interactions": [
      "Login form submission",
      "Product selection",
      "Cart update",
      "Checkout form with payment"
    ],
    "identified_validations": [
      "Email format validation",
      "Password strength check",
      "Card number validation"
    ]
  }
}
```

**Timing:** This is a long-running operation (30-60 seconds)
- For production, consider async job processing

**Status Codes:**
- `200` — Analysis complete
- `400` — Session not ready or missing data
- `404` — Session not found
- `500` — AI service error

---

### 4. Test Case Management

#### GET `/api/sessions/{session_id}/test-cases`
List test cases for a session.

**Query Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `status` | string | Filter by status (draft/approved/running/passed/failed) |
| `type` | string | Filter by type (happy/negative/edge/security) |

**Response:**
```json
[
  {
    "id": "tc-001",
    "session_id": "abc-123-def",
    "title": "Successful User Login",
    "test_type": "happy",
    "status": "approved",
    "steps": [
      {
        "step_index": 0,
        "action": "navigate",
        "selector": null,
        "value": "https://example.com/login"
      },
      {
        "step_index": 1,
        "action": "fill",
        "selector": "input#email",
        "value": "user@example.com"
      }
    ],
    "expected_result": "User should be logged in and redirected to dashboard",
    "reason": "Validates core login functionality",
    "created_at": "2026-05-25T10:35:00Z"
  }
]
```

**Status Codes:**
- `200` — Test cases retrieved
- `404` — Session not found
- `500` — Server error

---

#### POST `/api/test/{test_case_id}/approve`
Mark test case as approved for execution.

**Response:**
```json
{
  "status": "ok",
  "test_id": "tc-001",
  "updated_status": "approved"
}
```

**Status Codes:**
- `200` — Test approved
- `404` — Test not found
- `400` — Already approved or invalid state

---

### 5. Test Execution

#### POST `/api/test/{test_case_id}/execute`
Execute a single approved test case.

**Request:**
```json
{
  "headless": true,
  "browser": "chromium"
}
```

**Response:**
```json
{
  "test_id": "tc-001",
  "overall_status": "failed",
  "duration_seconds": 12.5,
  "reasoning": "The login button was not found on the page. The 'Sign In' button was replaced with a 'Continue with SSO' button, which requires a different selector.",
  "step_results": [
    {
      "step_index": 0,
      "action": "navigate",
      "status": "passed",
      "duration_ms": 2500
    },
    {
      "step_index": 1,
      "action": "fill",
      "selector": "input#email",
      "status": "passed",
      "duration_ms": 500,
      "screenshot_b64": "iVBORw0KGgoAAAANSUhEUgAAAA..."
    },
    {
      "step_index": 2,
      "action": "click",
      "selector": "button.login-btn",
      "status": "failed",
      "duration_ms": 200,
      "error": "Timeout: Could not find element matching 'button.login-btn'",
      "screenshot_b64": "iVBORw0KGgoAAAANSUhEUgAAAA...",
      "reasoning": "The login button selector changed..."
    }
  ],
  "created_at": "2026-05-25T10:40:00Z"
}
```

**Status Codes:**
- `200` — Test executed (regardless of pass/fail)
- `400` — Test not approved or invalid state
- `404` — Test not found
- `500` — Execution engine error

---

#### POST `/api/sessions/{session_id}/execute-all`
Execute all approved test cases for a session.

**Response:**
```json
{
  "status": "started",
  "total_tests": 12,
  "job_id": "job-abc-123"
}
```

Use `job_id` to poll for results:
```
GET /api/job/{job_id}/status
```

---

### 6. Result Retrieval

#### GET `/api/test/{test_case_id}/result`
Get latest result for a test case.

**Response:**
```json
{
  "test_id": "tc-001",
  "result_id": "result-xyz",
  "overall_status": "passed",
  "duration_seconds": 8.3,
  "reasoning": null,
  "created_at": "2026-05-25T10:40:00Z",
  "step_results": [...]
}
```

**Status Codes:**
- `200` — Result retrieved
- `404` — Test or result not found

---

#### GET `/api/result/{result_id}`
Get full result details.

**Response:** (same as above)

---

### 7. Health Check

#### GET `/api/health`
Check if backend is running and connected to database.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "api_version": "0.1.0"
}
```

**Status Codes:**
- `200` — All systems operational
- `503` — Backend degraded (e.g., database connection failed)

---

## Database Schema

### Overview

SQLite database with 5 main tables: `sessions`, `events`, `test_cases`, `test_results`, `step_results`

### Table: `sessions`

Represents a recorded user session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID String | PK | Unique session identifier |
| `session_id` | String | UNIQUE, INDEX | Client-generated session ID |
| `name` | String | | Human-readable session name |
| `url` | String | NULLABLE | Starting URL of session |
| `status` | String | | recording/completed/analysing/analysed |
| `steps_count` | Integer | | Number of user action steps |
| `created_at` | DateTime | | Session creation timestamp |
| `updated_at` | DateTime | | Last update timestamp |

**Relationships:**
- Has many `Event` (cascade delete)
- Has many `TestCase` (cascade delete)

---

### Table: `events`

Raw captured events from the browser extension.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, AUTO | Auto-incrementing ID |
| `session_id` | String | FK, INDEX | Foreign key to session |
| `event_type` | String | | click/fill/navigate/network/dom_snapshot/screenshot |
| `timestamp` | Float | | Milliseconds since session start |
| `url` | String | NULLABLE | Page URL at time of event |
| `selector` | String | NULLABLE | CSS selector of target element |
| `value` | Text | NULLABLE | Value associated with event |
| `dom_snapshot` | Text | NULLABLE | Page HTML/text snapshot |
| `screenshot_b64` | Text | NULLABLE | Base64-encoded PNG screenshot |
| `network_data` | JSON | NULLABLE | Network call details |
| `meta` | JSON | NULLABLE | Additional element metadata |
| `created_at` | DateTime | | Event creation timestamp |

**Relationships:**
- Belongs to `Session`

---

### Table: `test_cases`

Generated test cases from AI analysis.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID String | PK | Unique test case ID |
| `session_id` | String | FK, INDEX | Foreign key to session |
| `title` | String | | Test case name (AI-generated) |
| `test_type` | String | | happy/negative/edge/security |
| `steps` | JSON | | Array of step objects |
| `expected_result` | Text | NULLABLE | Expected outcome description |
| `reason` | Text | NULLABLE | Why this test is important |
| `status` | String | | draft/approved/running/passed/failed |
| `created_at` | DateTime | | Creation timestamp |

**Step Object Structure:**
```json
{
  "step_index": 0,
  "action": "navigate|click|fill|select|hover|assert_text|assert_visible|submit",
  "selector": "CSS selector or text= selector",
  "value": "For fill/navigate actions"
}
```

**Relationships:**
- Belongs to `Session`
- Has many `TestResult` (cascade delete)

---

### Table: `test_results`

Results from test execution.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID String | PK | Unique result ID |
| `test_case_id` | String | FK, INDEX | Foreign key to test case |
| `overall_status` | String | | passed/failed |
| `reasoning` | Text | NULLABLE | AI-generated failure explanation |
| `duration_seconds` | Float | NULLABLE | Total execution time |
| `created_at` | DateTime | | Execution timestamp |

**Relationships:**
- Belongs to `TestCase`
- Has many `StepResult` (cascade delete)

---

### Table: `step_results`

Individual step results within a test execution.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, AUTO | Auto-incrementing ID |
| `result_id` | String | FK, INDEX | Foreign key to test result |
| `step_index` | Integer | | Step number (0-indexed) |
| `action` | String | NULLABLE | Action performed |
| `selector` | String | NULLABLE | Selector used |
| `status` | String | | passed/failed |
| `duration_ms` | Float | NULLABLE | Step execution time in ms |
| `error` | Text | NULLABLE | Error message if failed |
| `screenshot_b64` | Text | NULLABLE | Screenshot at step execution |

**Relationships:**
- Belongs to `TestResult`

---

### Sample Queries

#### Get all sessions with test counts
```sql
SELECT 
  s.id, 
  s.name, 
  COUNT(tc.id) as test_count
FROM sessions s
LEFT JOIN test_cases tc ON s.id = tc.session_id
GROUP BY s.id
ORDER BY s.created_at DESC;
```

#### Get failed tests with reasoning
```sql
SELECT 
  tc.title, 
  tr.overall_status, 
  tr.reasoning,
  tr.duration_seconds
FROM test_cases tc
JOIN test_results tr ON tc.id = tr.test_case_id
WHERE tr.overall_status = 'failed'
ORDER BY tr.created_at DESC;
```

#### Get most recent session with all test details
```sql
SELECT 
  s.id as session_id,
  s.name,
  tc.id as test_id,
  tc.title,
  tr.overall_status,
  COUNT(sr.id) as step_count
FROM sessions s
LEFT JOIN test_cases tc ON s.id = tc.session_id
LEFT JOIN test_results tr ON tc.id = tr.test_case_id
LEFT JOIN step_results sr ON tr.id = sr.result_id
WHERE s.id = (SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1)
GROUP BY tc.id;
```

---

## Frontend Guide

### Project Structure

```
poc/frontend/
├── src/
│   ├── App.jsx              # Main app component with routing
│   ├── App.css              # Global styles
│   ├── index.css            # Reset and base styles
│   ├── main.jsx             # Entry point
│   ├── Sessions.jsx         # Sessions list view
│   ├── TestCases.jsx        # Test management view
│   ├── ResultDetail.jsx     # Test execution results
│   └── assets/              # Images, fonts, etc.
├── public/                  # Static assets
├── package.json
├── vite.config.js
├── eslint.config.js
└── README.md
```

### Key Components

#### App.jsx

Main application component with routing and layout.

**Structure:**
```
┌─────────────────────────────────────────┐
│         Browser Window                  │
├──────────┬──────────────────────────────┤
│ Sidebar  │         Main Content         │
│          │                              │
│ Sessions │ ┌────────────────────────┐   │
│ - List   │ │   Session List View   │   │
│ - Status │ │   OR Test Cases View   │   │
│          │ │   OR Result Detail    │   │
│          │ └────────────────────────┘   │
└──────────┴──────────────────────────────┘
```

**Router Setup:**
- `/` — Sessions list
- `/sessions/:id` — Session details → Test cases
- `/test/:id` → Result detail
- `/result/:id` → Full result view

#### Sessions.jsx

Displays paginated list of recorded sessions.

**Features:**
```jsx
// Session card shows:
- Session name / title
- Starting URL
- Status badge (recording / completed / analysed)
- Step count
- Date created
- Action buttons: View | Analyse | Run | Delete

// Filters:
- Status dropdown
- Date range picker
- URL search

// Bulk actions:
- Run all tests
- Export sessions
- Archive old sessions
```

**Key Functions:**
```javascript
// Fetch sessions from API
const fetchSessions = async () => {
  const response = await api.get('/api/sessions');
  setSessions(response.data);
};

// Trigger analysis
const analyseSession = async (sessionId) => {
  setLoading(true);
  await api.post(`/api/sessions/${sessionId}/analyse`);
  fetchSessions(); // Refresh list
  setLoading(false);
};

// Navigate to session
const viewSession = (sessionId) => {
  navigate(`/sessions/${sessionId}`);
};
```

#### TestCases.jsx

Manages test cases for a selected session.

**Features:**
```jsx
// Test case display:
- Title (AI-generated)
- Type badge (happy path / negative / edge / security)
- Status (draft / approved / running / passed / failed)
- Step count
- Last result (if executed)

// Filters:
- By type
- By status
- By last result

// Actions on each test:
- View steps
- Approve
- Execute
- Delete
- Clone
- Edit (in future)

// Bulk actions:
- Approve all
- Run all
- Delete all passed/failed
```

**Workflow Example:**
```javascript
// 1. Load test cases for session
const loadTestCases = async (sessionId) => {
  const response = await api.get(`/api/sessions/${sessionId}/test-cases`);
  setTestCases(response.data);
};

// 2. Approve test
const approveTest = async (testId) => {
  await api.post(`/api/test/${testId}/approve`);
  loadTestCases(sessionId); // Refresh
};

// 3. Execute test
const executeTest = async (testId) => {
  setExecuting(testId);
  const result = await api.post(`/api/test/${testId}/execute`, {
    headless: true,
    browser: 'chromium'
  });
  setResults(prev => ({ ...prev, [testId]: result.data }));
  setExecuting(null);
};
```

#### ResultDetail.jsx

Shows step-by-step execution results of a test.

**Components:**
```
┌─────────────────────────────────────┐
│  Test Result Header                 │
│  - Title, Type, Status              │
│  - Duration, Date                   │
├─────────────────────────────────────┤
│  Overall Result Section             │
│  - Passed / Failed indicator        │
│  - Expected vs Actual               │
├─────────────────────────────────────┤
│  Step-by-Step Breakdown             │
│  ┌───────────────────────────────┐  │
│  │ Step 0: Navigate              │  │
│  │ Status: ✓ Passed              │  │
│  │ Duration: 2.5s                │  │
│  │ [Screenshot]                  │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Step 1: Fill [input#email]    │  │
│  │ Status: ✓ Passed              │  │
│  │ Duration: 0.5s                │  │
│  │ Value: user@example.com       │  │
│  │ [Screenshot]                  │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Step 2: Click [button.submit] │  │
│  │ Status: ✗ Failed              │  │
│  │ Duration: 0.2s                │  │
│  │ Error: Timeout                │  │
│  │ [Screenshot]                  │  │
│  └───────────────────────────────┘  │
├─────────────────────────────────────┤
│  AI Analysis / Reasoning            │
│  "The submit button was not found   │
│   because the form had client-side  │
│   validation errors. Check the      │
│   email format or required fields." │
├─────────────────────────────────────┤
│  Network Calls                      │
│  - POST /api/login → 401            │
│  - GET /api/user → 404              │
└─────────────────────────────────────┘
```

### Styling System

**Tailwind CSS v4** with custom configuration:

```javascript
// Key utilities used:
- Colors: slate, blue, green, red (for status)
- Spacing: px-4, py-3, gap-2 (consistent padding/margins)
- Typography: text-sm, font-bold, uppercase
- Layout: flex, grid, w-64 (sidebar)
- Shadows: shadow-lg, shadow-blue-500/20 (depth)
- Transitions: transition-colors, duration-200 (smooth)
- Dark mode: dark: prefix (future support)
```

**Theme Colors:**
- **Primary:** Blue (#3B82F6)
- **Success:** Green (#10B981)
- **Error:** Red (#EF4444)
- **Warning:** Yellow (#F59E0B)
- **Background:** Slate-900 (#0F172A)
- **Text:** Slate-300 (#CBD5E1)

### State Management

Currently using React hooks (useState, useContext):

```javascript
// Session management
const [sessions, setSessions] = useState([]);
const [selectedSession, setSelectedSession] = useState(null);
const [loading, setLoading] = useState(false);

// Test management
const [testCases, setTestCases] = useState([]);
const [results, setResults] = useState({});
const [executing, setExecuting] = useState(null);

// UI state
const [filter, setFilter] = useState('all');
const [sortBy, setSortBy] = useState('date');
```

**For future scaling, consider:**
- Redux for complex state
- TanStack Query for server state
- Zustand for lightweight state

### API Communication

All requests use Axios with interceptors:

```javascript
// api.js
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
});

// Response interceptor for error handling
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data?.detail || error.message);
    return Promise.reject(error);
  }
);

export default api;
```

### Deployment

#### Development
```bash
npm run dev    # Starts Vite dev server on port 5173
```

#### Production Build
```bash
npm run build  # Builds to dist/ folder
npm run preview # Preview production build locally
```

#### Docker Build
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 5000
CMD ["npm", "run", "preview"]
```

---

## Browser Extension Guide

### Architecture

The extension has two main components:

1. **Content Script** (`content.js`) — Runs on every page
   - Captures user interactions
   - Observes DOM changes
   - Records network activity
   - Generates CSS selectors
   - Buffers events for batching

2. **Background Service Worker** (`background.js`) — Runs persistently
   - Receives events from content script
   - Batches events every 2 seconds
   - Sends to backend API
   - Manages recording state
   - Handles popup communication

### Manifest Configuration

```json
{
  "manifest_version": 3,
  "name": "AI Testing Agent - Recorder",
  "version": "1.0.0",
  "permissions": ["activeTab", "tabs", "storage", "scripting"],
  "host_permissions": ["<all_urls>"],
  "background": { "service_worker": "background.js" },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content.js"],
    "run_at": "document_idle"
  }],
  "action": { "default_popup": "popup.html" }
}
```

### Content Script (`content.js`)

**Responsibilities:**
1. Inject monitoring code into page
2. Capture DOM interactions
3. Generate element selectors
4. Collect page metadata
5. Intercept network calls
6. Send batches to background script

**Key Functions:**

```javascript
// Initialize on page load
function beginRecording() {
  isRecording = true;
  eventQueue = [];
  capturePageSnapshot();
  attachEventListeners();
}

// Generate CSS selector for element
function getCSSSelector(element) {
  // Priority: ID → data-testid → name → path
  // Returns: "button#submit" or "[data-testid='login']"
}

// Capture page snapshot
function capturePageSnapshot() {
  const dom = document.documentElement.outerHTML;
  const screenshot = captureScreenshot(); // Via canvas API
  queueEvent({
    event_type: "dom_snapshot",
    dom_snapshot: dom,
    screenshot_b64: screenshot
  });
}

// Intercept network calls
function setupNetworkInterception() {
  // Wrap fetch
  const originalFetch = window.fetch;
  window.fetch = function(...args) {
    const [resource, config] = args;
    const startTime = performance.now();
    
    return originalFetch.apply(this, args).then(response => {
      queueEvent({
        event_type: "network",
        network_data: {
          method: config?.method || 'GET',
          url: resource,
          status: response.status,
          duration: performance.now() - startTime
        }
      });
      return response;
    });
  };
  
  // Wrap XMLHttpRequest (similar pattern)
}

// Debounced event queuing
function queueEvent(event) {
  event.timestamp = performance.now() - sessionStart;
  eventQueue.push(event);
  
  if (eventQueue.length > BATCH_SIZE || 
      Date.now() - lastBatchTime > BATCH_INTERVAL) {
    flushEvents();
  }
}
```

**Event Types Captured:**

| Event | Trigger | Data Captured |
|-------|---------|---------------|
| `click` | Mouse click on element | Selector, element text, position |
| `fill` | User types in input field | Selector, text value (length only, not content for security) |
| `input` | Programmatic input change | Selector, new value |
| `change` | Select/checkbox change | Selector, selected value |
| `submit` | Form submission | Form selector, submission method |
| `navigate` | Page navigation | New URL, page title |
| `select` | Dropdown option selection | Selector, selected option value |
| `hover` | Mouse hovers over element | Selector (throttled) |
| `dom_snapshot` | Periodic or on navigation | Full page HTML as text |
| `screenshot` | Periodic or on key events | Page screenshot as base64 PNG |
| `network` | XHR/fetch completion | Method, URL, status code |

### Background Script (`background.js`)

**Responsibilities:**
1. Manage recording lifecycle
2. Batch and send events to backend
3. Coordinate with content script
4. Store session metadata

**Key Functions:**

```javascript
// Message listener for content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'EVENT_BATCH') {
    handleEventBatch(message.events, sender.tab.id);
  }
  if (message.type === 'START_RECORDING') {
    startRecording();
  }
  if (message.type === 'STOP_RECORDING') {
    stopRecording();
  }
});

// Send events to backend
async function sendEventBatch(events) {
  const batch = {
    session_id: getCurrentSessionId(),
    events: events
  };
  
  try {
    const response = await fetch('http://localhost:8000/api/session/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(batch)
    });
    
    if (response.ok) {
      console.log(`Sent ${events.length} events`);
      return true;
    } else {
      console.error('Backend error:', response.statusText);
      return false;
    }
  } catch (error) {
    console.error('Network error:', error);
    // Retry logic here
    return false;
  }
}

// Batch events periodically
setInterval(() => {
  if (isRecording && eventBuffer.length > 0) {
    sendEventBatch(eventBuffer);
    eventBuffer = [];
  }
}, BATCH_INTERVAL_MS);
```

### Popup UI (`popup.html` / `popup.js`)

Simple control interface:

```html
<div class="popup">
  <h1>AI Testing Agent</h1>
  <button id="recordBtn">Start Recording</button>
  <div id="status">Ready</div>
  <input id="sessionName" placeholder="Session name">
</div>
```

```javascript
// Toggle recording
document.getElementById('recordBtn').addEventListener('click', () => {
  chrome.runtime.sendMessage({
    type: isRecording ? 'STOP_RECORDING' : 'START_RECORDING'
  });
  updateUI();
});

// Update UI
function updateUI() {
  const status = isRecording ? 'Recording...' : 'Ready';
  document.getElementById('status').textContent = status;
  document.getElementById('recordBtn').textContent = 
    isRecording ? 'Stop Recording' : 'Start Recording';
}
```

### Security Considerations

**Sensitive Data Handling:**
- Never capture password field values (detect via type="password")
- Truncate long text values in events
- Mark sensitive fields with `sensitive: true` flag
- Don't capture credit card numbers (detect pattern)

**Privacy:**
- User can see what's being captured
- User can pause recording anytime
- Sessions stored locally until approved
- No automatic data transmission

**Extension Permissions:**
- `activeTab` — Only access current tab
- `tabs` — Query tab info only
- `storage` — Local storage only
- `scripting` — Content script injection only
- `<all_urls>` — Network access to any domain (required for session recording)

### Testing the Extension

1. **Install in Chrome:**
   ```
   chrome://extensions → Load unpacked → Select poc/extension/
   ```

2. **Verify in Background Worker:**
   ```
   chrome://extensions → Details → Inspect views → service_worker
   Open DevTools to see console logs
   ```

3. **Test Recording:**
   - Navigate to https://example.com
   - Click extension icon → Start Recording
   - Perform actions (click, fill, navigate)
   - Check backend logs: `INFO: Saved X events`
   - Verify events in database: `sqlite3 test.db "SELECT COUNT(*) FROM events;"`

4. **Debugging:**
   - Right-click → Inspect to see content script console
   - Service worker console for background script logs
   - Network tab to see POST requests to backend

---

## Usage Workflows

### Workflow 1: Record a User Journey

**Duration:** 5-10 minutes

**Steps:**

1. **Start Recording**
   - Open Chrome and navigate to application URL
   - Click AI Testing Agent extension icon
   - Click "Start Recording"
   - Status shows "Recording..." and timer starts

2. **Perform User Actions**
   - Navigate through application
   - Fill out forms
   - Click buttons
   - Perform complete user journey (e.g., login → search → purchase)
   - Wait 2-3 seconds on each page for snapshots

3. **Stop Recording**
   - Click "Stop Recording" button
   - Extension uploads final event batch to backend
   - Status shows "Completed"
   - Copy or note session ID

4. **Verify in Frontend**
   - Open browser to http://localhost:5173
   - Click "Sessions" in sidebar
   - New session appears in list with step count
   - Note the number of steps recorded

**Example Journey:**
```
Navigate to https://app.example.com/login
  ↓
Fill email: user@example.com
  ↓
Fill password: ••••••
  ↓
Click Login button
  ↓
Wait for dashboard load
  ↓
Navigate to Products page
  ↓
Search for "blue shirt"
  ↓
Click first result
  ↓
Click Add to Cart
  ↓
Click Checkout
```

**Events Captured:**
- 1 navigate (initial page load)
- 2 fill events (email, password)
- 1 click event (Login)
- 1 navigate (to Products)
- 1 fill (search)
- 4 click events (product, cart, checkout)
- Multiple DOM snapshots and screenshots
- Network calls on each page load

---

### Workflow 2: Analyze Session & Generate Tests

**Duration:** 1-2 minutes (AI processing)

**Steps:**

1. **Select Session**
   - In frontend, click on session in list
   - Page navigates to Session Details
   - Shows complete step-by-step breakdown with screenshots

2. **Trigger AI Analysis**
   - Click "Analyze with AI" button
   - Status changes to "Analysing..."
   - Backend sends session to Claude AI
   - Processing can take 30-60 seconds

3. **View Results**
   - Status changes to "Analysed"
   - Test Cases tab updates with generated tests
   - Shows count of tests by type:
     - Happy path: 1 test
     - Negative: 3 tests
     - Edge cases: 2 tests
     - Security: 2 tests

4. **Review Generated Tests**
   - Click on test to expand and view steps
   - Each test has:
     - Title (auto-generated)
     - Type indicator
     - Steps breakdown
     - Expected result
     - Reason (why test matters)

**Example Generated Tests:**

Test 1 — Happy Path
```
Title: "Complete successful user login and dashboard access"
Type: Happy Path
Steps:
  1. Navigate to login page
  2. Fill email with "test@example.com"
  3. Fill password with valid value
  4. Click Login button
  5. Wait for Dashboard page load
Expected: User sees dashboard with greeting
Reason: Validates core authentication and success path
```

Test 2 — Negative (Invalid Email)
```
Title: "Reject login with invalid email format"
Type: Negative
Steps:
  1. Navigate to login page
  2. Fill email with "invalid-email"
  3. Fill password with value
  4. Click Login button
Expected: Error message appears, user stays on login page
Reason: Email validation is critical security control
```

Test 3 — Edge Case (Very Long Password)
```
Title: "Handle very long password input"
Type: Edge Case
Steps:
  1. Navigate to login page
  2. Fill email with "user@example.com"
  3. Fill password with 500-character string
  4. Click Login button
Expected: Either accept or show "password too long" error
Reason: Boundary testing for input validation
```

---

### Workflow 3: Approve & Execute Tests

**Duration:** 2-5 minutes (execution)

**Steps:**

1. **Review Tests**
   - View all generated tests
   - Read descriptions and expected results
   - Click checkboxes to select which to run

2. **Approve Tests**
   - Click "Approve Selected" or approve individual tests
   - Status changes from "draft" to "approved"
   - Tests now eligible for execution

3. **Execute Tests**
   - Option A: Execute individual test
     - Click "Run" on specific test
     - Execution begins
   - Option B: Execute all approved tests
     - Click "Run All Approved"
     - Tests execute sequentially

4. **Monitor Execution**
   - Progress bar shows which test is running
   - Live feedback: "Running step 3 of 5..."
   - Test status badge updates in real-time

5. **View Results**
   - Once complete, results appear below each test
   - Green checkmark for passed, red X for failed
   - Overall statistics: "8 Passed, 2 Failed out of 10"

**Example Execution Results:**

```
TEST: Complete successful user login
Status: ✓ PASSED (8.3 seconds)

Step 1: Navigate to https://app.example.com/login
  Status: ✓ Passed (2.5s)
  [Screenshot of login page]

Step 2: Fill email with "test@example.com"
  Status: ✓ Passed (0.3s)
  [Screenshot showing filled email field]

Step 3: Fill password
  Status: ✓ Passed (0.2s)
  [Screenshot with masked password field]

Step 4: Click Login button
  Status: ✓ Passed (0.5s)
  [Screenshot of login button clicked]

Step 5: Wait for Dashboard
  Status: ✓ Passed (4.8s)
  [Screenshot of dashboard page]
```

---

### Workflow 4: Debug Failed Tests

**Duration:** 5-10 minutes

**Steps:**

1. **Identify Failed Test**
   - In Test Results view, filter to show "Failed" tests
   - Click on failed test to view detail
   - Red X marks failed step

2. **Review Failure Context**
   - Screenshot at failure point
   - Error message (e.g., "Timeout: Could not find selector")
   - Comparison with recorded session

3. **Read AI Analysis**
   - Backend automatically ran Claude analysis
   - Section titled "Why This Test Failed:"
   - Example analysis:
     ```
     "The login button selector changed from 'button.login-btn' 
      to 'button[data-testid="login-btn"]' in the latest build. 
      The DOM structure was updated but the test wasn't. Update 
      the selector in step 4 or re-record the session."
     ```

4. **Options to Fix**
   - **Quick Fix:** Edit test step selector manually
     - Click "Edit Test"
     - Update selector for failed step
     - Re-run test
   
   - **Regenerate:** Delete test and re-analyze session
     - Click "Delete Test"
     - Click "Analyze Session" again
     - AI generates new tests with current selectors
   
   - **Re-Record:** Record new session if app changed significantly
     - Start new recording session
     - Perform updated user journey
     - Generate fresh tests

5. **Verify Fix**
   - Re-run test
   - Confirm all steps now pass
   - Mark test as "regression tested" for future reference

**Common Failure Reasons:**

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| "Timeout: Could not find selector" | DOM changed, selector no longer valid | Update selector or re-record |
| "AssertionError: Expected 'Success' but got ''" | Page state different than expected | Check async operations, add waits |
| "Navigation timeout" | Page slow to load | Increase timeout in executor config |
| "Invalid selector syntax" | Generated selector malformed | Claude issue, manually fix |
| "Element not visible" | Overlays blocking element | Check overlay dismissal config |

---

### Workflow 5: Export Results & Report

**Duration:** 10 minutes

**Steps:**

1. **Generate Report**
   - In Session view, click "Export Report"
   - Choose format: PDF / JSON / CSV / HTML

2. **Review Report Contents**
   - Session metadata (date, duration, URL)
   - Test summary (total, passed, failed)
   - Detailed results for each test:
     - Title and type
     - Step count
     - Overall result
     - AI reasoning for failures
   - Screenshots and evidence
   - Execution timeline

3. **Share with Team**
   - Export test results as JSON
   - Share PDF report with stakeholders
   - Link to specific test results in dashboard

4. **Archive Session**
   - Mark session as archived
   - Move to historical records
   - Can still be referenced for regression testing

---

## Development Guide

### Setting Up Development Environment

#### Prerequisites
- VS Code or preferred IDE
- Python 3.11+ with venv
- Node.js 18+ with npm
- Chrome browser with developer tools
- Git version control

#### Initial Setup

```bash
# Clone repository
git clone <repo-url>
cd agentic-testing

# Backend setup
cd poc/backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install

# Create .env
echo "OPENAI_API_KEY=sk-..." > .env

# Frontend setup
cd ../frontend
npm install

# Extension setup (no dependencies)
cd ../extension
# Ready to go, just open chrome://extensions
```

#### Start All Services

**Terminal 1 — Backend:**
```bash
cd poc/backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd poc/frontend
npm run dev
```

**Terminal 3 — Load Extension:**
```bash
# In Chrome
1. Navigate to chrome://extensions
2. Enable Developer mode
3. Click Load unpacked
4. Select poc/extension folder
5. Extension appears in toolbar
```

### Project Structure & File Organization

```
poc/
├── backend/
│   ├── main.py               # ← API routes here
│   ├── models.py             # ← Database models
│   ├── schemas.py            # ← Request/response schemas
│   ├── database.py           # ← DB setup
│   ├── session_builder.py    # ← Session reconstruction
│   ├── analyser.py           # ← Claude analysis & test gen
│   ├── executor.py           # ← Playwright test runner
│   ├── reasoning.py          # ← Failure analysis
│   ├── step_validation.py    # ← Test validation
│   ├── requirements.txt      # ← Dependencies
│   ├── test.db              # ← SQLite database (generated)
│   ├── .env                 # ← API keys (local only)
│   └── tests/
│       └── test_*.py        # ← Unit tests
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # ← Main component
│   │   ├── Sessions.jsx     # ← Sessions list
│   │   ├── TestCases.jsx    # ← Test management
│   │   ├── ResultDetail.jsx # ← Result viewer
│   │   ├── main.jsx         # ← Entry point
│   │   └── index.css        # ← Global styles
│   ├── package.json
│   ├── vite.config.js
│   └── public/
│
└── extension/
    ├── manifest.json        # ← MV3 config
    ├── content.js           # ← Page event capture
    ├── background.js        # ← Event batching
    ├── popup.html           # ← UI
    └── popup.js             # ← UI logic
```

### Common Development Tasks

#### Adding a New API Endpoint

1. **Define Request/Response Schema** in `schemas.py`:
```python
from pydantic import BaseModel

class MyRequestSchema(BaseModel):
    parameter1: str
    parameter2: int

class MyResponseSchema(BaseModel):
    status: str
    data: dict
```

2. **Add Database Model** (if needed) in `models.py`:
```python
class MyModel(Base):
    __tablename__ = "my_models"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
```

3. **Create Route Handler** in `main.py`:
```python
@app.post("/api/my-endpoint", response_model=MyResponseSchema)
def my_endpoint(req: MyRequestSchema, db: DBSession = Depends(get_db)):
    """Description of what this endpoint does."""
    # Implement logic
    return MyResponseSchema(status="ok", data={})
```

4. **Test Endpoint:**
```bash
# Using curl
curl -X POST http://localhost:8000/api/my-endpoint \
  -H "Content-Type: application/json" \
  -d '{"parameter1": "value", "parameter2": 42}'

# Or visit Swagger UI: http://localhost:8000/docs
```

#### Adding Frontend Component

1. **Create Component File** `src/MyComponent.jsx`:
```jsx
import { useState, useEffect } from 'react';
import api from './api';  // Import API client

export default function MyComponent() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.get('/api/endpoint');
        setData(response.data);
      } catch (error) {
        console.error('Error:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      {data.map(item => (
        <div key={item.id}>{item.name}</div>
      ))}
    </div>
  );
}
```

2. **Add to Routing** in `App.jsx`:
```jsx
import MyComponent from './MyComponent';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/my-component" element={<MyComponent />} />
      </Routes>
    </BrowserRouter>
  );
}
```

3. **Add Navigation Link** in `Sidebar`:
```jsx
<Link to="/my-component" className={`...`}>
  My Component
</Link>
```

#### Debugging Backend

**Using Python debugger:**
```python
# In main.py or any module
import pdb; pdb.set_trace()  # Program stops here

# Or better: use breakpoints in VS Code
# Add breakpoint, press F5 to start debugging
```

**Using Logging:**
```python
import logging
logger = logging.getLogger(__name__)

# In endpoint
logger.info(f"Processing session {session_id}")
logger.error(f"Failed to analyse: {error}")
```

**Using FastAPI Swagger UI:**
- Visit http://localhost:8000/docs
- Try out endpoints with interactive UI
- See request/response examples

#### Debugging Extension

**Content Script Console:**
- Right-click on page → Inspect
- Switch to Console tab
- Extension logs appear here

**Background Service Worker:**
- Visit chrome://extensions
- Find "AI Testing Agent - Recorder"
- Click "service_worker" under "Inspect views"
- Logs appear in DevTools console

**Network Tab:**
- Right-click → Inspect → Network tab
- Watch for POST requests to http://localhost:8000/api/session/events
- See request payload and response

#### Running Tests

**Backend Unit Tests:**
```bash
cd poc/backend
pytest tests/ -v
```

**Frontend Tests (if configured):**
```bash
cd poc/frontend
npm test
```

**Manual Testing Checklist:**
- [ ] Record session with 5+ events
- [ ] Verify events appear in database
- [ ] Run analysis, get test cases
- [ ] Execute at least one test
- [ ] Verify results display correctly
- [ ] Check for any console errors

---

### Making Code Changes

#### Python Backend

1. **Make changes** to `.py` files
2. Uvicorn auto-reloads on save (--reload flag)
3. **No restart needed** (usually)
4. Check backend logs for errors

#### React Frontend

1. **Make changes** to `.jsx` / `.css` files
2. Vite auto-refreshes on save (HMR)
3. **Browser updates instantly** (usually)
4. Check browser console for errors

#### Chrome Extension

1. **Make changes** to `.js` / `.json` files
2. Go to chrome://extensions
3. Click refresh icon on extension
4. Reload page to test changes

### Performance Optimization

**Backend:**
- Use database indexes for frequent queries
- Cache session detail in memory
- Implement pagination for large result sets
- Consider async processing for AI operations

**Frontend:**
- Lazy load components using React.lazy()
- Implement virtual scrolling for long lists
- Memoize expensive computations
- Use React Router lazy loading

**Extension:**
- Batch events efficiently (current: every 2s)
- Debounce input events
- Compress screenshots before transmission
- Use IndexedDB for local event buffering

### Security Considerations

**Backend:**
- Always validate input via Pydantic schemas
- Sanitize file paths before disk access
- Rate limit API endpoints (future)
- Add authentication & authorization (future)

**Frontend:**
- Never store sensitive data in localStorage
- Validate responses from API
- Implement CSRF protection (future)
- Add input sanitization (future)

**Extension:**
- Don't capture password fields
- Sanitize before sending network data
- Request minimal necessary permissions
- Keep API key secure (environment variable)

---

## Troubleshooting

### Common Issues & Solutions

#### Backend Won't Start

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

---

**Error:** `Address already in use: ('0.0.0.0', 8000)`

**Solution:**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9  # macOS/Linux

# Or use different port
uvicorn main:app --port 8001
```

---

#### Frontend Won't Load

**Error:** `Module not found: axios`

**Solution:**
```bash
cd poc/frontend
npm install
npm run dev
```

---

**Error:** `Cannot find module './api'`

**Solution:**
- Check that `src/api.js` or API client is properly imported
- Verify path in import statement
- Create `src/api.js` if missing:
```javascript
import axios from 'axios';
export default axios.create({
  baseURL: 'http://localhost:8000'
});
```

---

#### Extension Not Capturing Events

**Problem:** Extension installed but events not reaching backend

**Troubleshooting:**

1. **Check extension is running:**
   - chrome://extensions → Find "AI Testing Agent"
   - Should show "Enabled"
   - Click extension icon → Should show popup

2. **Check popup shows recording status:**
   - Click extension → Popup appears
   - "Start Recording" button present
   - Status shows "Ready"

3. **Verify backend is running:**
   - Terminal should show: `INFO: Application startup complete`
   - Visit http://localhost:8000/docs → Should load SwaggerUI

4. **Check network requests:**
   - Open DevTools (F12) → Network tab
   - Look for POST requests to `localhost:8000/api/session/events`
   - If no requests appear, extension isn't communicating

5. **Check service worker logs:**
   - chrome://extensions → Details on extension
   - Click "Inspect views: service_worker"
   - Should see logs like: "Sent 15 events to backend"

**Solution if still not working:**

```javascript
// In background.js, add detailed logging
console.log('Event batch:', batch);
console.log('Sending to:', 'http://localhost:8000/api/session/events');

// In content.js
console.log('Event queued:', event);

// Reload extension
// Re-test
```

---

#### Playwright Tests Timeout

**Error:** `Timeout: Could not find selector 'button.submit'`

**Solution:**

1. **Increase timeout:**
   - Edit `.env`: `PLAYWRIGHT_ACTION_TIMEOUT_MS=10000` (was 5000)
   - Restart backend

2. **Check selector is valid:**
   - Open page in browser
   - Right-click target element → Inspect
   - Copy CSS selector from DevTools
   - Verify it matches selector in test

3. **Check page is fully loaded:**
   - Add wait in test: `await page.waitForNavigation();`
   - Increase `POST_CLICK_NAVIGATION_TIMEOUT_MS` in `.env`

4. **Disable overlay dismissal if interfering:**
   - Edit `executor.py`: Comment out `_dismiss_overlays()` call
   - Re-run test

---

#### AI Analysis Failing

**Error:** `OpenAI API key invalid or quota exceeded`

**Solution:**

1. **Verify API key:**
   - Check `.env` file: `OPENAI_API_KEY=sk-...`
   - Log in to OpenAI dashboard
   - Verify key hasn't been revoked
   - Check account has credit available

2. **Check for typos:**
   - Copy key directly from dashboard
   - No extra spaces or quotes

3. **Test API connection:**
```bash
python -c "from openai import OpenAI; client = OpenAI(); print('OK')"
```

---

**Error:** `Timeout: Claude analysis took longer than 60 seconds`

**Solution:**

1. **Increase timeout:**
   - Edit `.env`: `AI_REASONING_TIMEOUT_SECONDS=30` → `120`
   - Try again

2. **Reduce session size:**
   - Some sessions too complex for analysis
   - Record shorter user journey (5-10 steps instead of 20+)
   - Re-analyze

3. **Check OpenAI status:**
   - Visit https://status.openai.com
   - See if service is degraded

---

#### Database Errors

**Error:** `sqlite3.OperationalError: database is locked`

**Solution:**

```bash
# SQLite only allows one writer at a time
# If multiple processes accessing DB:

# Option 1: Kill other processes
ps aux | grep python
kill -9 <pid>

# Option 2: Use connection pooling
# Already in database.py, but increase pool size if needed

# Option 3: Check for stuck transactions
# Restart backend service
```

---

**Error:** `Column 'new_column' does not exist`

**Solution:**

```bash
# Likely database schema mismatch
# Delete SQLite file to rebuild with new schema
rm poc/backend/test.db

# Restart backend
# New empty database created with correct schema
```

---

#### CORS Issues

**Error:** `Access to XMLHttpRequest blocked by CORS policy`

**Problem:** Frontend can't reach backend

**Solution:**

1. **Verify backend CORS config:**
```python
# In main.py, should have:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

2. **Check frontend API URL:**
```javascript
// In frontend code
const api = axios.create({
  baseURL: 'http://localhost:8000'  // Should match backend address
});
```

3. **Verify both services running:**
- Backend: http://localhost:8000/docs (should load)
- Frontend: http://localhost:5173 (should load)

---

#### Memory Issues

**Error:** `MemoryError` when recording large sessions

**Solution:**

1. **Limit events processed:**
   - In `.env`: `AI_MAX_STEPS=10` (limits to 10 steps)
   - Split large sessions into multiple recordings

2. **Reduce screenshot resolution:**
   - Add to `executor.py`: Compress screenshots before storing
   - Clear old test results regularly

3. **Monitor system resources:**
```bash
# Check memory usage
free -h  # Linux
wmic OS get totalvisiblememorys size  # Windows
```

---

### Getting Help

**For Issues With:**

**Backend API:**
- Check FastAPI docs: http://localhost:8000/docs
- Check FastAPI logs in terminal
- Review code in relevant `.py` file

**Frontend React:**
- Open browser DevTools (F12)
- Check Console tab for errors
- Check Network tab for API call failures

**Chrome Extension:**
- Right-click on page → Inspect → Console
- Visit chrome://extensions → Details → Inspect service_worker
- Check Background logs

**Database/Data:**
- Open SQLite directly:
  ```bash
  sqlite3 poc/backend/test.db
  SELECT COUNT(*) FROM sessions;
  ```

**AI/Claude:**
- Verify API key in `.env`
- Check OpenAI account has credits
- Review API response in backend logs

---

## Appendix

### Environment Variables Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | (required) | Claude API key |
| `OPENAI_MODEL` | `gpt-4o` | AI model to use |
| `AI_MAX_STEPS` | `10` | Max steps to process |
| `AI_FIELD_CHAR_LIMIT` | `200` | Max characters per field |
| `AI_MAX_NETWORK_CALLS_PER_STEP` | `3` | Network calls per step |
| `AI_REASONING_TIMEOUT_SECONDS` | `20` | Timeout for AI analysis |
| `AI_REASONING_MAX_RETRIES` | `0` | Retry attempts for AI |
| `PLAYWRIGHT_ACTION_TIMEOUT_MS` | `5000` | Action timeout in ms |
| `PLAYWRIGHT_POST_CLICK_SETTLE_MS` | `300` | Post-click wait in ms |
| `PLAYWRIGHT_POST_CLICK_NAVIGATION_TIMEOUT_MS` | `5000` | Navigation timeout |
| `DATABASE_URL` | `sqlite:///./test.db` | Database connection |

### API Response Codes Reference

| Code | Meaning | Example |
|------|---------|---------|
| `200` | Success | Session retrieved |
| `201` | Created | Test case generated |
| `400` | Bad Request | Invalid schema |
| `404` | Not Found | Session doesn't exist |
| `409` | Conflict | Duplicate session ID |
| `500` | Server Error | Unhandled exception |
| `503` | Service Unavailable | AI service down |

### Glossary

- **Session** — Recorded user interaction on a website
- **Event** — Individual user action (click, fill, navigate)
- **Step** — Grouped collection of related events
- **Test Case** — Automated test scenario generated from session
- **Test Type** — Category of test (happy path, negative, edge, security)
- **Selector** — CSS selector to target DOM element
- **Playwright** — Browser automation framework
- **Claude** — AI model from Anthropic (via OpenAI API)
- **MV3** — Chrome Manifest V3 (extension specification)
- **CORS** — Cross-Origin Resource Sharing (security policy)
- **SQLAlchemy** — Python ORM for databases
- **Pydantic** — Python data validation library
- **Vite** — Frontend build tool
- **HMR** — Hot Module Replacement (live reload)

---

## Summary

This AI Agentic Testing Tool represents a significant advancement in automated testing. By combining:

1. **Intelligent Recording** — Captures comprehensive user interactions and page context
2. **AI Understanding** — Claude AI understands user flows and application behavior
3. **Test Generation** — Automatically creates diverse test scenarios
4. **Automated Execution** — Playwright runs tests in real browsers with self-healing
5. **Failure Analysis** — AI explains why tests failed in plain language

The platform enables QA teams to move from manual test creation to AI-assisted test generation, dramatically reducing QA effort while improving test coverage.

### Future Enhancements

- Multi-session correlation (find bugs across multiple flows)
- Learning layer with LoRA fine-tuning
- Mobile and ERP application support
- Multi-tenancy and role-based access control
- Production CI/CD integration
- Test case versioning and diff tracking
- Result analytics and trend reporting
- API contract testing
- Performance testing capabilities

---

**Document Version:** 1.0  
**Last Updated:** 2026-05-25  
**Status:** Production-Ready (POC)
