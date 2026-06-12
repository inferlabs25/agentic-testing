"""
FastAPI application for the AI Agentic Testing Tool client-pilot build.
"""

import datetime
import html
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session as DBSession

import config
from analyser import analyse_session
from database import SessionLocal, create_tables, get_db
from executor import execute_test_case
from failure_intelligence import classify_failure, reasoning_to_text
from models import (
    Artifact,
    AuditLog,
    Event,
    Job,
    RecordingSession,
    StepResult,
    SuiteRun,
    TestCase,
    TestResult,
    TestRun,
)
from reasoning import analyse_failure
from redaction import redact_event_payload
from schemas import (
    AnalyseResponse,
    ApproveResponse,
    DashboardMetrics,
    EventBatch,
    EventBatchResponse,
    ExecuteResponse,
    JobResponse,
    SessionSummary,
    StepResultResponse,
    SuiteRunResponse,
    TestCaseResponse,
    TestCaseUpdateRequest,
    TestResultResponse,
)
from session_builder import SessionBuilder
from step_validation import validate_steps_against_session, validation_reason
from test_readiness import auto_repair_test_case, prepare_generated_test_case

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables...")
    create_tables()
    for warning in config.validate_startup_config():
        logger.warning("Configuration warning: %s", warning)
    logger.info("Database ready.")
    yield


app = FastAPI(
    title="AI Agentic Testing Tool",
    description="Record -> Understand -> Generate -> Execute -> Reason",
    version="0.2.0-client-pilot",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_actor(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    x_actor: Optional[str] = Header(default=None),
) -> str:
    if not config.PILOT_AUTH_REQUIRED:
        return x_actor or "local"

    bearer = ""
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization.split(" ", 1)[1].strip()
    supplied = x_api_key or bearer
    if not config.PILOT_API_KEY or supplied != config.PILOT_API_KEY:
        raise HTTPException(status_code=401, detail="Valid pilot API key required")
    return x_actor or "pilot-user"


def _audit(db: DBSession, actor: str, action: str, target_type: str, target_id: str, meta=None):
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            meta=meta or {},
        )
    )


def _job_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        target_id=job.target_id,
        status=job.status,
        progress_current=job.progress_current or 0,
        progress_total=job.progress_total or 0,
        message=job.message,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _suite_response(suite: SuiteRun) -> SuiteRunResponse:
    return SuiteRunResponse(
        id=suite.id,
        session_id=suite.session_id,
        job_id=suite.job_id,
        status=suite.status,
        total_count=suite.total_count or 0,
        passed_count=suite.passed_count or 0,
        failed_count=suite.failed_count or 0,
        current_test_case_id=suite.current_test_case_id,
        duration_seconds=suite.duration_seconds,
        created_at=suite.created_at,
        completed_at=suite.completed_at,
    )


def _test_case_response(tc: TestCase) -> TestCaseResponse:
    return TestCaseResponse(
        id=tc.id,
        session_id=tc.session_id,
        title=tc.title,
        test_type=tc.test_type,
        steps=tc.steps,
        expected_result=tc.expected_result,
        reason=tc.reason,
        readiness_status=tc.readiness_status or "ready_to_run",
        readiness_reason=tc.readiness_reason,
        locator_candidates=tc.locator_candidates,
        evidence_source=tc.evidence_source,
        status=tc.status,
        created_at=tc.created_at,
    )


def _result_response(db: DBSession, result: TestResult, tc: Optional[TestCase] = None) -> TestResultResponse:
    tc = tc or db.query(TestCase).filter(TestCase.id == result.test_case_id).first()
    steps = (
        db.query(StepResult)
        .filter(StepResult.result_id == result.id)
        .order_by(StepResult.step_index.asc())
        .all()
    )
    return TestResultResponse(
        id=result.id,
        test_case_id=result.test_case_id,
        test_case_title=tc.title if tc else None,
        test_case_type=tc.test_type if tc else None,
        overall_status=result.overall_status,
        reasoning=result.reasoning,
        reasoning_json=result.reasoning_json,
        failure_category=result.failure_category,
        confidence=result.confidence,
        artifact_paths=result.artifact_paths,
        duration_seconds=result.duration_seconds,
        step_results=[
            StepResultResponse(
                step_index=sr.step_index,
                action=sr.action,
                selector=sr.selector,
                selector_used=sr.selector_used,
                status=sr.status,
                error=sr.error,
                screenshot_b64=sr.screenshot_b64,
                duration_ms=sr.duration_ms,
                healing_applied=bool(sr.healing_applied),
                healing_reason=sr.healing_reason,
            )
            for sr in steps
        ],
        created_at=result.created_at,
    )


def _create_job(db: DBSession, job_type: str, target_id: str, total: int = 1, message: str = "") -> Job:
    job = Job(
        job_type=job_type,
        target_id=target_id,
        status="queued",
        progress_current=0,
        progress_total=total,
        message=message,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _mark_job(job: Job, status: str, message: str = None, error: str = None, result: dict = None):
    now = datetime.datetime.utcnow()
    job.status = status
    if status == "running" and not job.started_at:
        job.started_at = now
    if status in {"completed", "failed", "cancelled"}:
        job.completed_at = now
    if message is not None:
        job.message = message
    if error is not None:
        job.error = error
    if result is not None:
        job.result = result


def _analysis_job(job_id: str, session_id: str, actor: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        session = db.query(RecordingSession).filter(RecordingSession.session_id == session_id).first()
        if not job or not session:
            return

        _mark_job(job, "running", "Analysing recorded session")
        session.status = "analysing"
        db.commit()

        builder = SessionBuilder(db)
        detail = builder.build(session_id)
        if not detail:
            raise ValueError("Session not found")

        session_dict = detail.model_dump()
        for step in session_dict.get("steps", []):
            snapshot = step.get("dom_snapshot")
            if snapshot and len(snapshot) > 5000:
                step["dom_snapshot"] = snapshot[:5000] + "... [truncated]"

        result = analyse_session(session_dict)
        saved = 0
        ready = 0
        suggested = 0
        for tc_data in result.get("test_cases", []):
            prepared = prepare_generated_test_case(tc_data, session_dict)
            ready += 1 if prepared["readiness_status"] == "ready_to_run" else 0
            suggested += 1 if prepared["readiness_status"] == "suggested_review" else 0
            db.add(
                TestCase(
                    session_id=session_id,
                    title=prepared["title"],
                    test_type=prepared["test_type"],
                    steps=prepared["steps"],
                    expected_result=prepared["expected_result"],
                    reason=prepared["reason"],
                    readiness_status=prepared["readiness_status"],
                    readiness_reason=prepared["readiness_reason"],
                    locator_candidates=prepared["locator_candidates"],
                    evidence_source=prepared["evidence_source"],
                    status=prepared["status"],
                )
            )
            saved += 1

        session.status = "analysed"
        job.progress_current = 1
        _mark_job(
            job,
            "completed",
            "Analysis complete",
            result={
                "test_cases_generated": saved,
                "ready_to_run": ready,
                "suggested_review": suggested,
                "understanding": result.get("understanding"),
            },
        )
        _audit(db, actor, "analyse", "session", session_id, job.result)
        db.commit()
    except Exception as exc:
        logger.exception("Analysis job failed")
        job = db.query(Job).filter(Job.id == job_id).first()
        session = db.query(RecordingSession).filter(RecordingSession.session_id == session_id).first()
        if session:
            session.status = "analysis_failed"
        if job:
            _mark_job(job, "failed", "Analysis failed", error=str(exc))
        db.commit()
    finally:
        db.close()


def _execute_case(db: DBSession, tc: TestCase, suite_run_id: str = None) -> TestResult:
    tc.status = "running"
    db.commit()
    builder = SessionBuilder(db)
    session = db.query(RecordingSession).filter(RecordingSession.session_id == tc.session_id).first()
    base_url = session.url if session else None
    detail = builder.build(tc.session_id)
    session_dict = detail.model_dump() if detail else {"steps": []}
    prepared = prepare_generated_test_case(
        {
            "title": tc.title,
            "type": tc.test_type,
            "steps": tc.steps,
            "expected_result": tc.expected_result,
            "reason": tc.reason,
        },
        session_dict,
    )
    tc.steps = prepared["steps"]
    tc.expected_result = prepared["expected_result"]
    tc.reason = prepared["reason"]
    tc.readiness_status = prepared["readiness_status"]
    tc.readiness_reason = prepared["readiness_reason"]
    tc.locator_candidates = prepared["locator_candidates"]
    tc.evidence_source = prepared["evidence_source"]
    validation_issues = validate_steps_against_session(
        tc.steps,
        session_dict,
    )
    if prepared["readiness_status"] == "suggested_review":
        validation_issues = prepared["evidence_source"].get("validation_issues", validation_issues)

    if validation_issues:
        issue = validation_issues[0]
        exec_result = {
            "overall_status": "failed",
            "duration_seconds": 0,
            "artifact_paths": [],
            "step_results": [{
                "step_index": issue.get("step_index", 0),
                "action": issue.get("action"),
                "selector": issue.get("selector"),
                "selector_used": issue.get("selector"),
                "status": "failed",
                "error": issue.get("error"),
                "screenshot_b64": None,
                "duration_ms": 0,
                "healing_applied": False,
                "healing_reason": None,
            }],
        }
    else:
        exec_result = execute_test_case(
            tc.steps,
            base_url,
            artifact_dir=config.ARTIFACT_DIR,
            record_trace=config.PLAYWRIGHT_RECORD_TRACE,
            record_video=config.PLAYWRIGHT_RECORD_VIDEO,
        )

    test_result = TestResult(
        test_case_id=tc.id,
        suite_run_id=suite_run_id,
        overall_status=exec_result["overall_status"],
        duration_seconds=exec_result["duration_seconds"],
        artifact_paths=exec_result.get("artifact_paths", []),
    )
    db.add(test_result)
    db.flush()

    for path in exec_result.get("artifact_paths", []):
        db.add(Artifact(result_id=test_result.id, artifact_type="trace_or_screenshot", path=path))

    for sr_data in exec_result["step_results"]:
        db.add(
            StepResult(
                result_id=test_result.id,
                step_index=sr_data["step_index"],
                action=sr_data.get("action"),
                selector=sr_data.get("selector"),
                selector_used=sr_data.get("selector_used"),
                status=sr_data["status"],
                error=sr_data.get("error"),
                screenshot_b64=sr_data.get("screenshot_b64"),
                duration_ms=sr_data.get("duration_ms"),
                healing_applied=bool(sr_data.get("healing_applied")),
                healing_reason=sr_data.get("healing_reason"),
            )
        )

    if exec_result["overall_status"] == "failed":
        failed_step = next(
            (step for step in exec_result["step_results"] if step["status"] == "failed"),
            {},
        )
        network_logs = builder.get_all_network_calls(tc.session_id)[:10]
        if validation_issues:
            reasoning_text = validation_reason(validation_issues)
        else:
            reasoning_text = analyse_failure(
                test_title=tc.title,
                expected_result=tc.expected_result or "",
                failed_step=failed_step,
                screenshot_b64=failed_step.get("screenshot_b64"),
                network_logs=network_logs,
                test_steps=tc.steps,
            )
        structured = classify_failure(failed_step, reasoning_text, network_logs, test_steps=tc.steps)
        test_result.reasoning = reasoning_to_text(structured)
        test_result.reasoning_json = structured
        test_result.failure_category = structured["category"]
        test_result.confidence = structured["confidence"]

    tc.status = exec_result["overall_status"]
    db.commit()
    db.refresh(test_result)
    return test_result


def _execute_job(job_id: str, test_id: str, actor: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        tc = db.query(TestCase).filter(TestCase.id == test_id).first()
        if not job or not tc:
            return
        _mark_job(job, "running", f"Executing {tc.title}")
        db.commit()
        result = _execute_case(db, tc)
        job.progress_current = 1
        _mark_job(
            job,
            "completed",
            "Execution complete",
            result={"result_id": result.id, "overall_status": result.overall_status},
        )
        _audit(db, actor, "execute", "test_case", test_id, job.result)
        db.commit()
    except Exception as exc:
        logger.exception("Execution job failed")
        job = db.query(Job).filter(Job.id == job_id).first()
        tc = db.query(TestCase).filter(TestCase.id == test_id).first()
        if tc:
            tc.status = "failed"
        if job:
            _mark_job(job, "failed", "Execution failed", error=str(exc))
        db.commit()
    finally:
        db.close()


def _suite_job(job_id: str, suite_run_id: str, test_ids: List[str], actor: str):
    db = SessionLocal()
    start = time.time()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        suite = db.query(SuiteRun).filter(SuiteRun.id == suite_run_id).first()
        if not job or not suite:
            return
        _mark_job(job, "running", "Running approved suite")
        suite.status = "running"
        suite.total_count = len(test_ids)
        db.commit()

        for index, test_id in enumerate(test_ids, start=1):
            tc = db.query(TestCase).filter(TestCase.id == test_id).first()
            if not tc:
                continue
            suite.current_test_case_id = tc.id
            job.progress_current = index - 1
            job.message = f"Running {tc.title}"
            test_run = TestRun(suite_run_id=suite.id, test_case_id=tc.id, status="running")
            db.add(test_run)
            db.commit()
            result = _execute_case(db, tc, suite_run_id=suite.id)
            test_run.result_id = result.id
            test_run.status = result.overall_status
            test_run.duration_seconds = result.duration_seconds
            if result.overall_status == "passed":
                suite.passed_count += 1
            else:
                suite.failed_count += 1
            job.progress_current = index
            db.commit()

        suite.status = "completed"
        suite.current_test_case_id = None
        suite.duration_seconds = round(time.time() - start, 2)
        suite.completed_at = datetime.datetime.utcnow()
        _mark_job(
            job,
            "completed",
            "Suite complete",
            result={
                "suite_run_id": suite.id,
                "passed_count": suite.passed_count,
                "failed_count": suite.failed_count,
                "total_count": suite.total_count,
            },
        )
        _audit(db, actor, "run_suite", "suite_run", suite.id, job.result)
        db.commit()
    except Exception as exc:
        logger.exception("Suite job failed")
        job = db.query(Job).filter(Job.id == job_id).first()
        suite = db.query(SuiteRun).filter(SuiteRun.id == suite_run_id).first()
        if suite:
            suite.status = "failed"
            suite.completed_at = datetime.datetime.utcnow()
            suite.duration_seconds = round(time.time() - start, 2)
        if job:
            _mark_job(job, "failed", "Suite failed", error=str(exc))
        db.commit()
    finally:
        db.close()


@app.post("/api/session/events", response_model=EventBatchResponse)
def receive_events(
    batch: EventBatch,
    db: DBSession = Depends(get_db),
    actor: str = Depends(require_actor),
):
    session_id = batch.session_id
    session = db.query(RecordingSession).filter(RecordingSession.session_id == session_id).first()
    if not session:
        url = next((ev.url for ev in batch.events if ev.url), None)
        session = RecordingSession(
            session_id=session_id,
            name=f"Session {session_id[:8]}",
            url=url,
            status="recording",
            steps_count=0,
        )
        db.add(session)
        db.flush()

    saved = 0
    for ev in batch.events:
        clean = redact_event_payload(ev)
        db.add(Event(session_id=session_id, **clean))
        saved += 1

    action_types = {"click", "fill", "input", "change", "submit", "navigate", "select", "hover"}
    session.steps_count = (
        db.query(Event)
        .filter(Event.session_id == session_id, Event.event_type.in_(action_types))
        .count()
    )
    if not session.url:
        session.url = next((ev.url for ev in batch.events if ev.url), None)
    db.commit()
    return EventBatchResponse(status="ok", events_saved=saved)


@app.post("/api/sessions/{session_id}/complete")
def complete_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    actor: str = Depends(require_actor),
):
    session = db.query(RecordingSession).filter(RecordingSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "completed"
    _audit(db, actor, "complete", "session", session_id)
    db.commit()
    return {"status": "ok", "session_id": session_id}


@app.get("/api/sessions", response_model=List[SessionSummary])
def list_sessions(db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    sessions = db.query(RecordingSession).order_by(RecordingSession.created_at.desc()).all()
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


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    detail = SessionBuilder(db).build(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@app.post("/api/sessions/{session_id}/analyse", response_model=AnalyseResponse)
def analyse_session_endpoint(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
    actor: str = Depends(require_actor),
):
    session = db.query(RecordingSession).filter(RecordingSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    job = _create_job(db, "analyse_session", session_id, message="Queued analysis")
    background_tasks.add_task(_analysis_job, job.id, session_id, actor)
    return AnalyseResponse(status="queued", job_id=job.id)


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(job)


@app.get("/api/sessions/{session_id}/testcases", response_model=List[TestCaseResponse])
def list_test_cases(session_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.session_id == session_id)
        .order_by(TestCase.created_at.asc())
        .all()
    )
    return [_test_case_response(tc) for tc in test_cases]


@app.post("/api/testcases/{test_id}/approve", response_model=ApproveResponse)
def approve_test_case(test_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    tc = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    if tc.readiness_status == "suggested_review":
        raise HTTPException(status_code=400, detail="Suggested tests require review before approval")
    tc.status = "approved"
    _audit(db, actor, "approve", "test_case", test_id)
    db.commit()
    return ApproveResponse(status="ok", test_case_id=test_id)


@app.patch("/api/testcases/{test_id}", response_model=TestCaseResponse)
def update_test_case(
    test_id: str,
    payload: TestCaseUpdateRequest,
    db: DBSession = Depends(get_db),
    actor: str = Depends(require_actor),
):
    tc = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    detail = SessionBuilder(db).build(tc.session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")

    candidate = {
        "title": payload.title if payload.title is not None else tc.title,
        "type": payload.test_type if payload.test_type is not None else tc.test_type,
        "steps": payload.steps if payload.steps is not None else tc.steps,
        "expected_result": payload.expected_result if payload.expected_result is not None else tc.expected_result,
        "reason": payload.reason if payload.reason is not None else tc.reason,
    }
    prepared = prepare_generated_test_case(candidate, detail.model_dump())

    tc.title = prepared["title"]
    tc.test_type = prepared["test_type"]
    tc.steps = prepared["steps"]
    tc.expected_result = prepared["expected_result"]
    tc.reason = prepared["reason"]
    tc.readiness_status = prepared["readiness_status"]
    tc.readiness_reason = prepared["readiness_reason"]
    tc.locator_candidates = prepared["locator_candidates"]
    tc.evidence_source = prepared["evidence_source"]
    tc.status = "draft" if prepared["readiness_status"] == "ready_to_run" else "suggested_review"

    _audit(
        db,
        actor,
        "review_update",
        "test_case",
        test_id,
        {
            "readiness_status": tc.readiness_status,
            "readiness_reason": tc.readiness_reason,
        },
    )
    db.commit()
    db.refresh(tc)
    return _test_case_response(tc)


@app.post("/api/testcases/{test_id}/auto-review", response_model=TestCaseResponse)
def auto_review_test_case(
    test_id: str,
    db: DBSession = Depends(get_db),
    actor: str = Depends(require_actor),
):
    tc = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    detail = SessionBuilder(db).build(tc.session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")

    repaired = auto_repair_test_case(
        {
            "title": tc.title,
            "type": tc.test_type,
            "steps": tc.steps,
            "expected_result": tc.expected_result,
            "reason": tc.reason,
        },
        detail.model_dump(),
    )

    tc.title = repaired["title"]
    tc.test_type = repaired["test_type"]
    tc.steps = repaired["steps"]
    tc.expected_result = repaired["expected_result"]
    tc.reason = repaired["reason"]
    tc.readiness_status = repaired["readiness_status"]
    tc.readiness_reason = repaired["readiness_reason"]
    tc.locator_candidates = repaired["locator_candidates"]
    tc.evidence_source = repaired["evidence_source"]
    tc.status = "draft" if repaired["readiness_status"] == "ready_to_run" else "suggested_review"

    _audit(
        db,
        actor,
        "auto_review",
        "test_case",
        test_id,
        {
            "readiness_status": tc.readiness_status,
            "readiness_reason": tc.readiness_reason,
            "auto_review_notes": repaired.get("auto_review_notes", []),
        },
    )
    db.commit()
    db.refresh(tc)
    return _test_case_response(tc)


@app.post("/api/sessions/{session_id}/approve-all")
def approve_all_test_cases(session_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    updated = (
        db.query(TestCase)
        .filter(
            TestCase.session_id == session_id,
            TestCase.status == "draft",
            TestCase.readiness_status == "ready_to_run",
        )
        .update({"status": "approved"})
    )
    _audit(db, actor, "approve_all", "session", session_id, {"approved_count": updated})
    db.commit()
    return {"status": "ok", "approved_count": updated}


@app.post("/api/testcases/{test_id}/execute", response_model=ExecuteResponse)
def execute_test_case_endpoint(
    test_id: str,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
    actor: str = Depends(require_actor),
):
    tc = db.query(TestCase).filter(TestCase.id == test_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")
    if tc.readiness_status == "suggested_review":
        raise HTTPException(status_code=400, detail="Suggested tests are not executable until reviewed")
    job = _create_job(db, "execute_test_case", test_id, message="Queued execution")
    background_tasks.add_task(_execute_job, job.id, test_id, actor)
    return ExecuteResponse(status="queued", job_id=job.id)


@app.post("/api/sessions/{session_id}/run-suite")
def run_suite(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
    actor: str = Depends(require_actor),
):
    test_ids = [
        tc.id
        for tc in db.query(TestCase)
        .filter(
            TestCase.session_id == session_id,
            TestCase.status == "approved",
            TestCase.readiness_status == "ready_to_run",
        )
        .order_by(TestCase.created_at.asc())
        .all()
    ]
    if not test_ids:
        raise HTTPException(status_code=400, detail="No approved ready-to-run tests found")
    job = _create_job(db, "run_suite", session_id, total=len(test_ids), message="Queued suite")
    suite = SuiteRun(session_id=session_id, job_id=job.id, status="queued", total_count=len(test_ids))
    db.add(suite)
    db.commit()
    db.refresh(suite)
    background_tasks.add_task(_suite_job, job.id, suite.id, test_ids, actor)
    return {"status": "queued", "job_id": job.id, "suite_run_id": suite.id}


@app.post("/api/suite-runs/{run_id}/retry-failed")
def retry_failed_suite(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
    actor: str = Depends(require_actor),
):
    failed_runs = (
        db.query(TestRun)
        .filter(TestRun.suite_run_id == run_id, TestRun.status == "failed")
        .all()
    )
    test_ids = [run.test_case_id for run in failed_runs]
    if not test_ids:
        raise HTTPException(status_code=400, detail="No failed tests found to retry")
    original = db.query(SuiteRun).filter(SuiteRun.id == run_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Suite run not found")
    job = _create_job(db, "retry_failed_suite", run_id, total=len(test_ids), message="Queued retry")
    suite = SuiteRun(session_id=original.session_id, job_id=job.id, status="queued", total_count=len(test_ids))
    db.add(suite)
    db.commit()
    db.refresh(suite)
    background_tasks.add_task(_suite_job, job.id, suite.id, test_ids, actor)
    _audit(db, actor, "retry_failed", "suite_run", run_id, {"new_suite_run_id": suite.id})
    db.commit()
    return {"status": "queued", "job_id": job.id, "suite_run_id": suite.id}


@app.get("/api/suite-runs/{run_id}", response_model=SuiteRunResponse)
def get_suite_run(run_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    suite = db.query(SuiteRun).filter(SuiteRun.id == run_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite run not found")
    return _suite_response(suite)


@app.get("/api/results/{result_id}", response_model=TestResultResponse)
def get_result(result_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    result = db.query(TestResult).filter(TestResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return _result_response(db, result)


@app.get("/api/testcases/{test_id}/results", response_model=List[TestResultResponse])
def list_results_for_test(test_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    results = (
        db.query(TestResult)
        .filter(TestResult.test_case_id == test_id)
        .order_by(TestResult.created_at.desc())
        .all()
    )
    tc = db.query(TestCase).filter(TestCase.id == test_id).first()
    return [_result_response(db, result, tc) for result in results]


@app.get("/api/suite-runs/{run_id}/report", response_class=HTMLResponse)
def suite_report(run_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    suite = db.query(SuiteRun).filter(SuiteRun.id == run_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Suite run not found")
    runs = db.query(TestRun).filter(TestRun.suite_run_id == run_id).all()
    rows = []
    for run in runs:
        tc = db.query(TestCase).filter(TestCase.id == run.test_case_id).first()
        result = db.query(TestResult).filter(TestResult.id == run.result_id).first() if run.result_id else None
        rows.append(
            "<tr>"
            f"<td>{html.escape(tc.title if tc else run.test_case_id)}</td>"
            f"<td>{html.escape(run.status)}</td>"
            f"<td>{html.escape(result.failure_category if result and result.failure_category else '-')}</td>"
            f"<td>{html.escape(result.reasoning if result and result.reasoning else '-')}</td>"
            "</tr>"
        )
    return HTMLResponse(
        "<html><head><title>AI Testing Suite Report</title>"
        "<style>body{font-family:Arial,sans-serif;margin:32px}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #ddd;padding:8px}th{background:#f4f4f4}</style></head><body>"
        f"<h1>Suite Report</h1><p>Status: {html.escape(suite.status)} | "
        f"Passed: {suite.passed_count} | Failed: {suite.failed_count} | Total: {suite.total_count}</p>"
        "<table><thead><tr><th>Test</th><th>Status</th><th>Failure Category</th><th>Reasoning</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></body></html>"
    )


@app.get("/api/sessions/{session_id}/export/playwright", response_class=PlainTextResponse)
def export_playwright(session_id: str, db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.session_id == session_id, TestCase.readiness_status == "ready_to_run")
        .order_by(TestCase.created_at.asc())
        .all()
    )
    lines = ["import { test, expect } from '@playwright/test';", ""]
    for tc in test_cases:
        lines.append(f"test({json.dumps(tc.title)}, async ({{ page }}) => {{")
        for step in tc.steps:
            action = step.get("action")
            selector = step.get("selector")
            value = step.get("value")
            if action == "navigate":
                lines.append(f"  await page.goto({json.dumps(value)});")
            elif action == "click":
                lines.append(f"  await page.locator({json.dumps(selector)}).click();")
            elif action == "fill":
                lines.append(f"  await page.locator({json.dumps(selector)}).fill({json.dumps(value)});")
            elif action == "assert_visible":
                lines.append(f"  await expect(page.locator({json.dumps(selector)})).toBeVisible();")
            elif action == "assert_text":
                lines.append(f"  await expect(page.locator({json.dumps(selector)})).toHaveText({json.dumps(value)});")
            elif action == "wait":
                lines.append(f"  await page.waitForTimeout({int(value or 1000)});")
        lines.append("});")
        lines.append("")
    _audit(db, actor, "export_playwright", "session", session_id, {"count": len(test_cases)})
    db.commit()
    return PlainTextResponse("\n".join(lines), media_type="text/plain")


@app.get("/api/dashboard/metrics", response_model=DashboardMetrics)
def dashboard_metrics(db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    sessions = db.query(RecordingSession).count()
    tests = db.query(TestCase).count()
    ready = db.query(TestCase).filter(TestCase.readiness_status == "ready_to_run").count()
    suggested = db.query(TestCase).filter(TestCase.readiness_status == "suggested_review").count()
    results = db.query(TestResult).count()
    passed = db.query(TestResult).filter(TestResult.overall_status == "passed").count()
    categories = {}
    for result in db.query(TestResult).filter(TestResult.failure_category.isnot(None)).all():
        categories[result.failure_category] = categories.get(result.failure_category, 0) + 1
    return DashboardMetrics(
        sessions_recorded=sessions,
        tests_generated=tests,
        ready_to_run=ready,
        suggested_review=suggested,
        suite_pass_rate=round((passed / results) * 100, 1) if results else 0,
        failure_categories=categories,
        estimated_minutes_saved=tests * 8,
    )


@app.get("/api/admin/retention/preview")
def retention_preview(db: DBSession = Depends(get_db), actor: str = Depends(require_actor)):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=config.DATA_RETENTION_DAYS)
    old_sessions = db.query(RecordingSession).filter(RecordingSession.created_at < cutoff).count()
    old_results = db.query(TestResult).filter(TestResult.created_at < cutoff).count()
    return {
        "retention_days": config.DATA_RETENTION_DAYS,
        "cutoff": cutoff.isoformat(),
        "sessions_older_than_cutoff": old_sessions,
        "results_older_than_cutoff": old_results,
    }


@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "AI Agentic Testing Tool", "version": "0.2.0-client-pilot"}
