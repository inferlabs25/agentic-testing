"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# ── Event ingestion ──────────────────────────────────────────────

class EventItem(BaseModel):
    event_type: str
    timestamp: float
    url: Optional[str] = None
    selector: Optional[str] = None
    value: Optional[str] = None
    dom_snapshot: Optional[str] = None
    screenshot_b64: Optional[str] = None
    network_data: Optional[dict] = None
    meta: Optional[dict] = None


class EventBatch(BaseModel):
    session_id: str
    events: List[EventItem]


class EventBatchResponse(BaseModel):
    status: str
    events_saved: int


# ── Session responses ────────────────────────────────────────────

class SessionSummary(BaseModel):
    session_id: str
    name: str
    url: Optional[str] = None
    status: str
    steps_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class SessionStep(BaseModel):
    step_index: int
    url: Optional[str] = None
    action: str
    selector: Optional[str] = None
    value: Optional[str] = None
    meta: Optional[dict] = None
    dom_snapshot: Optional[str] = None
    screenshot_b64: Optional[str] = None
    network_calls: List[dict] = []


class SessionDetail(BaseModel):
    session_id: str
    name: str
    url: Optional[str] = None
    status: str
    steps: List[SessionStep]
    created_at: datetime
    auth_context: Optional[dict] = None


# ── Test case responses ──────────────────────────────────────────

class TestStepSchema(BaseModel):
    step_index: int
    action: str
    selector: Optional[str] = None
    value: Optional[str] = None


class TestCaseResponse(BaseModel):
    id: str
    session_id: str
    title: str
    test_type: str
    steps: List[dict]
    expected_result: Optional[str] = None
    reason: Optional[str] = None
    readiness_status: str = "ready_to_run"
    readiness_reason: Optional[str] = None
    locator_candidates: Optional[list] = None
    evidence_source: Optional[dict] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TestCaseUpdateRequest(BaseModel):
    title: Optional[str] = None
    test_type: Optional[str] = None
    steps: Optional[List[dict]] = None
    expected_result: Optional[str] = None
    reason: Optional[str] = None


class AnalyseResponse(BaseModel):
    status: str
    job_id: Optional[str] = None
    test_cases_generated: int = 0
    understanding: Optional[dict] = None


class JobResponse(BaseModel):
    id: str
    job_type: str
    target_id: Optional[str] = None
    status: str
    progress_current: int = 0
    progress_total: int = 0
    message: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ── Result responses ─────────────────────────────────────────────

class StepResultResponse(BaseModel):
    step_index: int
    action: Optional[str] = None
    selector: Optional[str] = None
    selector_used: Optional[str] = None
    status: str
    error: Optional[str] = None
    screenshot_b64: Optional[str] = None
    duration_ms: Optional[float] = None
    healing_applied: bool = False
    healing_reason: Optional[str] = None

    class Config:
        from_attributes = True


class TestResultResponse(BaseModel):
    id: str
    test_case_id: str
    test_case_title: Optional[str] = None
    test_case_type: Optional[str] = None
    overall_status: str
    reasoning: Optional[str] = None
    reasoning_json: Optional[dict] = None
    failure_category: Optional[str] = None
    confidence: Optional[float] = None
    artifact_paths: Optional[list] = None
    duration_seconds: Optional[float] = None
    step_results: List[StepResultResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ExecuteResponse(BaseModel):
    status: str
    job_id: Optional[str] = None
    result_id: Optional[str] = None
    overall_status: Optional[str] = None


class ApproveResponse(BaseModel):
    status: str
    test_case_id: str


class SuiteRunResponse(BaseModel):
    id: str
    session_id: str
    job_id: Optional[str] = None
    status: str
    total_count: int
    passed_count: int
    failed_count: int
    current_test_case_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class DashboardMetrics(BaseModel):
    sessions_recorded: int
    tests_generated: int
    ready_to_run: int
    suggested_review: int
    suite_pass_rate: float
    failure_categories: dict
    estimated_minutes_saved: int
