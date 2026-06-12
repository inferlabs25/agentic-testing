"""
SQLAlchemy ORM models for the AI Agentic Testing Tool.
"""

import datetime
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Float,
)
from sqlalchemy.orm import relationship
from database import Base


def _uuid():
    return str(uuid.uuid4())


class RecordingSession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True, index=True)
    environment_id = Column(String, ForeignKey("environments.id"), nullable=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, default="Untitled Session")
    url = Column(String, nullable=True)
    status = Column(String, default="recording")  # recording | completed | analysing | analysed
    steps_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    events = relationship("Event", back_populates="session", cascade="all, delete-orphan")
    test_cases = relationship("TestCase", back_populates="session", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)  # click, fill, navigate, network, dom_snapshot, screenshot
    timestamp = Column(Float, nullable=False)
    url = Column(String, nullable=True)
    selector = Column(String, nullable=True)
    value = Column(Text, nullable=True)
    dom_snapshot = Column(Text, nullable=True)
    screenshot_b64 = Column(Text, nullable=True)
    network_data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)  # extra metadata
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("RecordingSession", back_populates="events")


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    test_type = Column(String, nullable=False)  # happy | negative | edge | security
    steps = Column(JSON, nullable=False)  # list of step dicts
    expected_result = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)  # why this test matters
    readiness_status = Column(String, default="ready_to_run")  # ready_to_run | suggested_review
    readiness_reason = Column(Text, nullable=True)
    locator_candidates = Column(JSON, nullable=True)
    evidence_source = Column(JSON, nullable=True)
    status = Column(String, default="draft")  # draft | approved | running | passed | failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("RecordingSession", back_populates="test_cases")
    results = relationship("TestResult", back_populates="test_case", cascade="all, delete-orphan")


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(String, primary_key=True, default=_uuid)
    test_case_id = Column(String, ForeignKey("test_cases.id"), nullable=False, index=True)
    suite_run_id = Column(String, ForeignKey("suite_runs.id"), nullable=True, index=True)
    overall_status = Column(String, nullable=False)  # passed | failed
    reasoning = Column(Text, nullable=True)  # AI root cause analysis
    reasoning_json = Column(JSON, nullable=True)
    failure_category = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    artifact_paths = Column(JSON, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    test_case = relationship("TestCase", back_populates="results")
    step_results = relationship("StepResult", back_populates="result", cascade="all, delete-orphan")


class StepResult(Base):
    __tablename__ = "step_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(String, ForeignKey("test_results.id"), nullable=False, index=True)
    step_index = Column(Integer, nullable=False)
    action = Column(String, nullable=True)
    selector = Column(String, nullable=True)
    selector_used = Column(String, nullable=True)
    status = Column(String, nullable=False)  # passed | failed
    error = Column(Text, nullable=True)
    screenshot_b64 = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
    healing_applied = Column(Boolean, default=False)
    healing_reason = Column(Text, nullable=True)

    result = relationship("TestResult", back_populates="step_results")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False, default="Default Project")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Environment(Base):
    __tablename__ = "environments"

    id = Column(String, primary_key=True, default=_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True, index=True)
    name = Column(String, nullable=False, default="Local")
    base_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=_uuid)
    job_type = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="queued")  # queued | running | completed | failed | cancelled
    progress_current = Column(Integer, default=0)
    progress_total = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class SuiteRun(Base):
    __tablename__ = "suite_runs"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.session_id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=True, index=True)
    status = Column(String, default="queued")
    total_count = Column(Integer, default=0)
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    current_test_case_id = Column(String, ForeignKey("test_cases.id"), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(String, primary_key=True, default=_uuid)
    suite_run_id = Column(String, ForeignKey("suite_runs.id"), nullable=False, index=True)
    test_case_id = Column(String, ForeignKey("test_cases.id"), nullable=False, index=True)
    result_id = Column(String, ForeignKey("test_results.id"), nullable=True, index=True)
    status = Column(String, default="queued")
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True, default=_uuid)
    result_id = Column(String, ForeignKey("test_results.id"), nullable=True, index=True)
    artifact_type = Column(String, nullable=False)  # screenshot | trace | video | report
    path = Column(Text, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=_uuid)
    actor = Column(String, nullable=True)
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=True)
    target_id = Column(String, nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
