"""
Database configuration for the AI  Agentic Testing Tool.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./poc.db")

engine_kwargs = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create registered tables and apply small SQLite compatibility migrations."""
    from models import (  # noqa: F401
        Artifact,
        AuditLog,
        Environment,
        Event,
        Job,
        Project,
        RecordingSession,
        StepResult,
        SuiteRun,
        TestCase,
        TestResult,
        TestRun,
    )

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns():
    """Add new pilot columns to existing local SQLite databases."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    additions = {
        "sessions": {
            "project_id": "VARCHAR",
            "environment_id": "VARCHAR",
        },
        "test_cases": {
            "readiness_status": "VARCHAR DEFAULT 'ready_to_run'",
            "readiness_reason": "TEXT",
            "locator_candidates": "JSON",
            "evidence_source": "JSON",
        },
        "test_results": {
            "suite_run_id": "VARCHAR",
            "reasoning_json": "JSON",
            "failure_category": "VARCHAR",
            "confidence": "FLOAT",
            "artifact_paths": "JSON",
        },
        "step_results": {
            "selector_used": "VARCHAR",
            "healing_applied": "BOOLEAN DEFAULT 0",
            "healing_reason": "TEXT",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in additions.items():
            existing = {
                row[1]
                for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            }
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    conn.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    )
