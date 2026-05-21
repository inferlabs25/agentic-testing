"""
Database configuration — SQLite via SQLAlchemy.
Auto-creates tables on import when used with create_tables().
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./poc.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite specific
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables defined by models that inherit from Base."""
    from models import (  # noqa: F401 — import triggers table registration
        RecordingSession,
        Event,
        TestCase,
        TestResult,
        StepResult,
    )
    Base.metadata.create_all(bind=engine)
