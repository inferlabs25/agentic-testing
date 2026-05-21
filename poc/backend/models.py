"""
SQLAlchemy ORM models for the AI Agentic Testing Tool.
Tables: RecordingSession, Event, TestCase, TestResult, StepResult
"""

import datetime
import uuid
from sqlalchemy import (
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
    status = Column(String, default="draft")  # draft | approved | running | passed | failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    session = relationship("RecordingSession", back_populates="test_cases")
    results = relationship("TestResult", back_populates="test_case", cascade="all, delete-orphan")


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(String, primary_key=True, default=_uuid)
    test_case_id = Column(String, ForeignKey("test_cases.id"), nullable=False, index=True)
    overall_status = Column(String, nullable=False)  # passed | failed
    reasoning = Column(Text, nullable=True)  # AI root cause analysis
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
    status = Column(String, nullable=False)  # passed | failed
    error = Column(Text, nullable=True)
    screenshot_b64 = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)

    result = relationship("TestResult", back_populates="step_results")
