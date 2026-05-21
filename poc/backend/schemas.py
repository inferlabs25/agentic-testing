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
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyseResponse(BaseModel):
    status: str
    test_cases_generated: int
    understanding: Optional[dict] = None


# ── Result responses ─────────────────────────────────────────────

class StepResultResponse(BaseModel):
    step_index: int
    action: Optional[str] = None
    selector: Optional[str] = None
    status: str
    error: Optional[str] = None
    screenshot_b64: Optional[str] = None
    duration_ms: Optional[float] = None

    class Config:
        from_attributes = True


class TestResultResponse(BaseModel):
    id: str
    test_case_id: str
    test_case_title: Optional[str] = None
    test_case_type: Optional[str] = None
    overall_status: str
    reasoning: Optional[str] = None
    duration_seconds: Optional[float] = None
    step_results: List[StepResultResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ExecuteResponse(BaseModel):
    status: str
    result_id: str
    overall_status: str


class ApproveResponse(BaseModel):
    status: str
    test_case_id: str
