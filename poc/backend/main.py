"""
FastAPI application — main entry point.
All API routes for the AI Agentic Testing Tool POC.
"""

import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session as DBSession

from database import get_db, create_tables
from models import RecordingSession, Event, TestCase, TestResult, StepResult
from schemas import (
    EventBatch,
    EventBatchResponse,
    SessionSummary,
    SessionDetail,
    TestCaseResponse,
    AnalyseResponse,
    ApproveResponse,
    ExecuteResponse,
    TestResultResponse,
    StepResultResponse,
)
from session_builder import SessionBuilder
from analyser import analyse_session
from executor import execute_test_case
from reasoning import analyse_failure
from step_validation import validate_steps_against_session, validation_reason

# ── Logging ─────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── App lifecycle ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables...")
    create_tables()
    logger.info("Database ready.")
    yield


app = FastAPI(
    title="AI Agentic Testing Tool",
    description="Record → Understand → Generate → Execute → Reason",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 1. Event ingestion from Chrome extension ────────────────────

@app.post("/api/session/events", response_model=EventBatchResponse)
def receive_events(batch: EventBatch, db: DBSession = Depends(get_db)):
    """Receive a batch of captured events from the browser extension."""
    session_id = batch.session_id

    # Get or create the session
    session = (
        db.query(RecordingSession)
        .filter(RecordingSession.session_id == session_id)
        .first()
    )
    if not session:
        # Determine URL from the first event that has one
        url = None
        for ev in batch.events:
            if ev.url:
                url = ev.url
                break

        session = RecordingSession(
            session_id=session_id,
            name=f"Session {session_id[:8]}",
            url=url,
            status="recording",
            steps_count=0,
        )
        db.add(session)
        db.flush()

    # Save each event
    saved = 0
    for ev in batch.events:
        event = Event(
            session_id=session_id,
            event_type=ev.event_type,
            timestamp=ev.timestamp,
            url=ev.url,
            selector=ev.selector,
            value=ev.value,
            dom_snapshot=ev.dom_snapshot,
            screenshot_b64=ev.screenshot_b64,
            network_data=ev.network_data,
            meta=ev.meta,
        )
        db.add(event)
        saved += 1

    # Update step count (count action events)
    action_types = {"click", "fill", "input", "change", "submit", "navigate", "select", "hover"}
    action_count = (
        db.query(Event)
        .filter(
            Event.session_id == session_id,
            Event.event_type.in_(action_types),
        )
        .count()
    )
    session.steps_count = action_count

    # Update URL if we didn't have one
    if not session.url:
        for ev in batch.events:
            if ev.url:
                session.url = ev.url
                break

    db.commit()
    logger.info(f"Saved {saved} events for session {session_id}")

    return EventBatchResponse(status="ok", events_saved=saved)


# ── 2. Mark session as completed ────────────────────────────────

@app.post("/api/sessions/{session_id}/complete")
def complete_session(session_id: str, db: DBSession = Depends(get_db)):
    """Mark a recording session as completed."""
    session = (
        db.query(RecordingSession)
        .filter(RecordingSession.session_id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "completed"
    db.commit()
    return {"status": "ok", "session_id": session_id}


# ── 3. List sessions ───────────────────────────────────────────

@app.get("/api/sessions", response_model=List[SessionSummary])
def list_sessions(db: DBSession = Depends(get_db)):
    """Return all recorded sessions."""
    sessions = (
        db.query(RecordingSession)
        .order_by(RecordingSession.created_at.desc())
        .all()
    )
    return [
        SessionSummary(
            session_id=s.session_id,
            name=s.name,
            url=s.url,
            status=s.status,
            steps_count=s.steps_count,
            created_at=s.created_at,
        )
        for s in sessions
    ]


# ── 4. Get session detail ──────────────────────────────────────

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    """Return the structured session object with steps."""
    builder = SessionBuilder(db)
    detail = builder.build(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


# ── 5. Trigger AI analysis ─────────────────────────────────────

@app.post("/api/sessions/{session_id}/analyse", response_model=AnalyseResponse)
def analyse_session_endpoint(session_id: str, db: DBSession = Depends(get_db)):
    """Trigger GPT-4o analysis: understand session → generate test cases."""
    # Get structured session
    builder = SessionBuilder(db)
    detail = builder.build(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")

    # Update status
    session = (
        db.query(RecordingSession)
        .filter(RecordingSession.session_id == session_id)
        .first()
    )
    session.status = "analysing"
    db.commit()

    # Run analysis
    session_dict = detail.model_dump()
    # Strip large DOM snapshots to save tokens
    for step in session_dict.get("steps", []):
        if step.get("dom_snapshot") and len(step["dom_snapshot"]) > 5000:
            step["dom_snapshot"] = step["dom_snapshot"][:5000] + "... [truncated]"

    result = analyse_session(session_dict)

    # Save test cases to DB
    test_cases_data = result.get("test_cases", [])
    saved_count = 0

    for tc_data in test_cases_data:
        # Ensure steps have proper structure
        steps = tc_data.get("steps", [])
        for i, step in enumerate(steps):
            if "step_index" not in step:
                step["step_index"] = i + 1

        tc = TestCase(
            session_id=session_id,
            title=tc_data.get("title", "Untitled Test"),
            test_type=tc_data.get("type", "happy"),
            steps=steps,
            expected_result=tc_data.get("expected_result", ""),
            reason=tc_data.get("reason", ""),
            status="draft",
        )
        db.add(tc)
        saved_count += 1

    session.status = "analysed"
    db.commit()
    logger.info(f"Analysis complete: {saved_count} test cases generated for session {session_id}")

    return AnalyseResponse(
        status="ok",
        test_cases_generated=saved_count,
        understanding=result.get("understanding"),
    )


# ── 6. List test cases for a session ───────────────────────────

@app.get("/api/sessions/{session_id}/testcases", response_model=List[TestCaseResponse])
def list_test_cases(session_id: str, db: DBSession = Depends(get_db)):
    """Return all test cases for a given session."""
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.session_id == session_id)
        .order_by(TestCase.created_at.asc())
        .all()
    )
    return [
        TestCaseResponse(
            id=tc.id,
            session_id=tc.session_id,
            title=tc.title,
            test_type=tc.test_type,
            steps=tc.steps,
            expected_result=tc.expected_result,
            reason=tc.reason,
            status=tc.status,
            created_at=tc.created_at,
        )
        for tc in test_cases
    ]


# ── 7. Approve a test case ─────────────────────────────────────

@app.post("/api/testcases/{test_id}/approve", response_model=ApproveResponse)
def approve_test_case(test_id: str, db: DBSession = Depends(get_db)):
    """Mark a test case as approved for execution."""
    tc = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    tc.status = "approved"
    db.commit()
    return ApproveResponse(status="ok", test_case_id=test_id)


# ── 8. Bulk approve all test cases for a session ───────────────

@app.post("/api/sessions/{session_id}/approve-all")
def approve_all_test_cases(session_id: str, db: DBSession = Depends(get_db)):
    """Approve all draft test cases for a session."""
    updated = (
        db.query(TestCase)
        .filter(TestCase.session_id == session_id, TestCase.status == "draft")
        .update({"status": "approved"})
    )
    db.commit()
    return {"status": "ok", "approved_count": updated}


# ── 9. Execute a test case ─────────────────────────────────────

@app.post("/api/testcases/{test_id}/execute", response_model=ExecuteResponse)
def execute_test_case_endpoint(test_id: str, db: DBSession = Depends(get_db)):
    """Execute a test case using Playwright and save results."""
    tc = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    tc.status = "running"
    db.commit()

    # Determine base URL from the session
    session = (
        db.query(RecordingSession)
        .filter(RecordingSession.session_id == tc.session_id)
        .first()
    )
    base_url = session.url if session else None

    builder = SessionBuilder(db)
    detail = builder.build(tc.session_id)
    validation_issues = validate_steps_against_session(
        tc.steps,
        detail.model_dump() if detail else {"steps": []},
    )

    # Execute only after generated interaction steps match recording evidence.
    if validation_issues:
        issue = validation_issues[0]
        exec_result = {
            "overall_status": "failed",
            "duration_seconds": 0,
            "step_results": [{
                "step_index": issue.get("step_index", 0),
                "action": issue.get("action"),
                "selector": issue.get("selector"),
                "status": "failed",
                "error": issue.get("error"),
                "screenshot_b64": None,
                "duration_ms": 0,
            }],
        }
    else:
        exec_result = execute_test_case(tc.steps, base_url)

    # Save result
    test_result = TestResult(
        test_case_id=test_id,
        overall_status=exec_result["overall_status"],
        duration_seconds=exec_result["duration_seconds"],
    )
    db.add(test_result)
    db.flush()

    # Save step results
    for sr_data in exec_result["step_results"]:
        sr = StepResult(
            result_id=test_result.id,
            step_index=sr_data["step_index"],
            action=sr_data.get("action"),
            selector=sr_data.get("selector"),
            status=sr_data["status"],
            error=sr_data.get("error"),
            screenshot_b64=sr_data.get("screenshot_b64"),
            duration_ms=sr_data.get("duration_ms"),
        )
        db.add(sr)

    # If failed, run AI reasoning
    if validation_issues:
        test_result.reasoning = validation_reason(validation_issues)
    elif exec_result["overall_status"] == "failed":
        failed_step = None
        failed_screenshot = None
        for sr_data in exec_result["step_results"]:
            if sr_data["status"] == "failed":
                failed_step = sr_data
                failed_screenshot = sr_data.get("screenshot_b64")
                break

        if failed_step:
            # Get network logs from the session
            network_logs = builder.get_all_network_calls(tc.session_id)

            reasoning = analyse_failure(
                test_title=tc.title,
                expected_result=tc.expected_result or "",
                failed_step=failed_step,
                screenshot_b64=failed_screenshot,
                network_logs=network_logs[:10],
            )
            test_result.reasoning = reasoning

    # Update test case status
    tc.status = exec_result["overall_status"]
    db.commit()

    logger.info(f"Test {test_id} executed: {exec_result['overall_status']}")

    return ExecuteResponse(
        status="ok",
        result_id=test_result.id,
        overall_status=exec_result["overall_status"],
    )


# ── 10. Get result detail ──────────────────────────────────────

@app.get("/api/results/{result_id}", response_model=TestResultResponse)
def get_result(result_id: str, db: DBSession = Depends(get_db)):
    """Return a test result with step-by-step details and AI reasoning."""
    result = db.query(TestResult).filter(TestResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    step_results = (
        db.query(StepResult)
        .filter(StepResult.result_id == result_id)
        .order_by(StepResult.step_index.asc())
        .all()
    )

    # Get test case info for context
    tc = db.query(TestCase).filter(TestCase.id == result.test_case_id).first()

    return TestResultResponse(
        id=result.id,
        test_case_id=result.test_case_id,
        test_case_title=tc.title if tc else None,
        test_case_type=tc.test_type if tc else None,
        overall_status=result.overall_status,
        reasoning=result.reasoning,
        duration_seconds=result.duration_seconds,
        step_results=[
            StepResultResponse(
                step_index=sr.step_index,
                action=sr.action,
                selector=sr.selector,
                status=sr.status,
                error=sr.error,
                screenshot_b64=sr.screenshot_b64,
                duration_ms=sr.duration_ms,
            )
            for sr in step_results
        ],
        created_at=result.created_at,
    )


# ── 11. List results for a test case ───────────────────────────

@app.get("/api/testcases/{test_id}/results", response_model=List[TestResultResponse])
def list_results_for_test(test_id: str, db: DBSession = Depends(get_db)):
    """Return all results for a test case."""
    results = (
        db.query(TestResult)
        .filter(TestResult.test_case_id == test_id)
        .order_by(TestResult.created_at.desc())
        .all()
    )
    tc = db.query(TestCase).filter(TestCase.id == test_id).first()

    response = []
    for result in results:
        step_results = (
            db.query(StepResult)
            .filter(StepResult.result_id == result.id)
            .order_by(StepResult.step_index.asc())
            .all()
        )
        response.append(
            TestResultResponse(
                id=result.id,
                test_case_id=result.test_case_id,
                test_case_title=tc.title if tc else None,
                test_case_type=tc.test_type if tc else None,
                overall_status=result.overall_status,
                reasoning=result.reasoning,
                duration_seconds=result.duration_seconds,
                step_results=[
                    StepResultResponse(
                        step_index=sr.step_index,
                        action=sr.action,
                        selector=sr.selector,
                        status=sr.status,
                        error=sr.error,
                        screenshot_b64=sr.screenshot_b64,
                        duration_ms=sr.duration_ms,
                    )
                    for sr in step_results
                ],
                created_at=result.created_at,
            )
        )
    return response


# ── Health check ────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "AI Agentic Testing Tool"}
