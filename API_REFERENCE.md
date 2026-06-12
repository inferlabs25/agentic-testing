# API Quick Reference

Quick lookup for all API endpoints.

---

## Client-Pilot API Update

The current implementation uses job-based APIs for long-running work:
- `POST /api/sessions/{session_id}/analyse` -> `{ job_id, status }`
- `GET /api/jobs/{job_id}`
- `POST /api/testcases/{test_id}/execute` -> `{ job_id, status }`
- `POST /api/sessions/{session_id}/run-suite`
- `POST /api/suite-runs/{run_id}/retry-failed`
- `GET /api/suite-runs/{run_id}`
- `GET /api/suite-runs/{run_id}/report`
- `GET /api/sessions/{session_id}/export/playwright`

Legacy `/api/test/...` and `/api/result/...` examples below are superseded by `/api/testcases/...`, `/api/results/...`, `/api/jobs/...`, and `/api/suite-runs/...`.

---

## Base URL
```
http://localhost:8000
```

---

## Session Management

### List All Sessions
```
GET /api/sessions
```
**Response:** Array of session objects

```json
[
  {
    "session_id": "abc-123",
    "name": "Session abc123",
    "url": "https://example.com",
    "status": "analysed",
    "steps_count": 12,
    "created_at": "2026-05-25T10:30:00Z"
  }
]
```

---

### Get Session Details
```
GET /api/sessions/{session_id}
```
**Response:** Full session with all steps and events

```json
{
  "session_id": "abc-123",
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
      "meta": {},
      "dom_snapshot": "<!DOCTYPE html>...",
      "screenshot_b64": "iVBORw0KGgo...",
      "network_calls": []
    }
  ]
}
```

---

### Mark Session Complete
```
POST /api/sessions/{session_id}/complete
```
**Body:** (empty)

**Response:**
```json
{
  "status": "ok",
  "session_id": "abc-123"
}
```

---

### Delete Session
```
DELETE /api/sessions/{session_id}
```
**Response:**
```json
{
  "status": "ok",
  "deleted": true
}
```

---

## Event Management

### Submit Event Batch
```
POST /api/session/events
```
**Body:**
```json
{
  "session_id": "abc-123",
  "events": [
    {
      "event_type": "click",
      "timestamp": 1234567890.123,
      "url": "https://example.com",
      "selector": "button#submit",
      "value": "Submit",
      "dom_snapshot": "...",
      "screenshot_b64": "iVBORw0KGgo...",
      "network_data": null,
      "meta": { "role": "button" }
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

---

## AI Analysis

### Analyze Session & Generate Tests
```
POST /api/sessions/{session_id}/analyse
```
**Body:** (empty)

**Response:**
```json
{
  "status": "ok",
  "test_cases_generated": 12,
  "understanding": {
    "application_purpose": "E-commerce checkout",
    "user_flow": "Login → Search → Purchase",
    "key_interactions": ["Login form", "Product selection"],
    "identified_validations": ["Email format", "Password strength"]
  }
}
```

---

## Test Case Management

### Get Test Cases for Session
```
GET /api/sessions/{session_id}/test-cases
```
**Query params:**
- `status` — draft | approved | running | passed | failed
- `type` — happy | negative | edge | security

**Response:**
```json
[
  {
    "id": "tc-001",
    "session_id": "abc-123",
    "title": "Successful user login",
    "test_type": "happy",
    "status": "draft",
    "steps": [
      {
        "step_index": 0,
        "action": "navigate",
        "selector": null,
        "value": "https://example.com/login"
      }
    ],
    "expected_result": "User logged in and sees dashboard",
    "reason": "Validates core login flow",
    "created_at": "2026-05-25T10:35:00Z"
  }
]
```

---

### Get Single Test Case
```
GET /api/test/{test_case_id}
```
**Response:** Test case object (same structure as above)

---

### Approve Test Case
```
POST /api/test/{test_case_id}/approve
```
**Body:** (empty)

**Response:**
```json
{
  "status": "ok",
  "test_id": "tc-001",
  "updated_status": "approved"
}
```

---

### Delete Test Case
```
DELETE /api/test/{test_case_id}
```
**Response:**
```json
{
  "status": "ok",
  "deleted": true
}
```

---

## Test Execution

### Execute Single Test
```
POST /api/test/{test_case_id}/execute
```
**Body:**
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
  "overall_status": "passed",
  "duration_seconds": 8.3,
  "reasoning": null,
  "step_results": [
    {
      "step_index": 0,
      "action": "navigate",
      "status": "passed",
      "duration_ms": 2500
    }
  ],
  "created_at": "2026-05-25T10:40:00Z"
}
```

---

### Execute All Tests for Session
```
POST /api/sessions/{session_id}/execute-all
```
**Body:**
```json
{
  "headless": true,
  "approved_only": true
}
```

**Response:**
```json
{
  "status": "started",
  "total_tests": 12,
  "job_id": "job-abc-123"
}
```

---

### Get Job Status
```
GET /api/job/{job_id}/status
```
**Response:**
```json
{
  "job_id": "job-abc-123",
  "status": "running",
  "progress": "5 of 12 completed",
  "results": [...]
}
```

---

## Results

### Get Latest Result for Test
```
GET /api/test/{test_case_id}/result
```
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

---

### Get Specific Result
```
GET /api/result/{result_id}
```
**Response:** Same as above

---

### Get All Results for Test
```
GET /api/test/{test_case_id}/results
```
**Query params:**
- `limit` — Number of results (default: 10)
- `offset` — Pagination offset (default: 0)

**Response:** Array of result objects

---

## Health & Status

### Health Check
```
GET /api/health
```
**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "api_version": "0.1.0"
}
```

---

### API Version
```
GET /api/version
```
**Response:**
```json
{
  "version": "0.1.0",
  "environment": "development"
}
```

---

## Error Responses

### Bad Request (400)
```json
{
  "detail": "Invalid request format"
}
```

### Not Found (404)
```json
{
  "detail": "Session not found"
}
```

### Server Error (500)
```json
{
  "detail": "Internal server error"
}
```

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 404 | Not Found |
| 409 | Conflict (e.g., duplicate) |
| 500 | Server Error |
| 503 | Service Unavailable |

---

## cURL Examples

### List Sessions
```bash
curl http://localhost:8000/api/sessions
```

### Get Session Detail
```bash
curl http://localhost:8000/api/sessions/abc-123
```

### Submit Events
```bash
curl -X POST http://localhost:8000/api/session/events \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123",
    "events": [{
      "event_type": "click",
      "timestamp": 1234567890.123,
      "url": "https://example.com",
      "selector": "button#submit",
      "value": "Submit"
    }]
  }'
```

### Analyze Session
```bash
curl -X POST http://localhost:8000/api/sessions/abc-123/analyse \
  -H "Content-Type: application/json"
```

### Execute Test
```bash
curl -X POST http://localhost:8000/api/test/tc-001/execute \
  -H "Content-Type: application/json" \
  -d '{
    "headless": true,
    "browser": "chromium"
  }'
```

---

## Python Examples

```python
import requests

BASE_URL = "http://localhost:8000"

# List sessions
response = requests.get(f"{BASE_URL}/api/sessions")
sessions = response.json()

# Get session detail
response = requests.get(f"{BASE_URL}/api/sessions/abc-123")
detail = response.json()

# Analyze session
response = requests.post(f"{BASE_URL}/api/sessions/abc-123/analyse")
result = response.json()

# Execute test
response = requests.post(
    f"{BASE_URL}/api/test/tc-001/execute",
    json={"headless": True, "browser": "chromium"}
)
result = response.json()
```

---

## JavaScript Examples

```javascript
const BASE_URL = "http://localhost:8000";

// List sessions
const response = await fetch(`${BASE_URL}/api/sessions`);
const sessions = await response.json();

// Get session detail
const response = await fetch(`${BASE_URL}/api/sessions/abc-123`);
const detail = await response.json();

// Analyze session
const response = await fetch(
  `${BASE_URL}/api/sessions/abc-123/analyse`,
  { method: "POST" }
);
const result = await response.json();

// Execute test
const response = await fetch(
  `${BASE_URL}/api/test/tc-001/execute`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ headless: true, browser: "chromium" })
  }
);
const result = await response.json();
```

---

## WebSocket (Future)

For real-time test execution updates:
```
ws://localhost:8000/ws/job/{job_id}
```

Receives:
```json
{
  "type": "progress",
  "test": 5,
  "total": 12,
  "message": "Running test 5 of 12..."
}
```

---

**Need more details?** See [Full API Reference](./DOCUMENTATION.md#api-reference)
