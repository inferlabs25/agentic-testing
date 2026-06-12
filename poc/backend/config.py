"""
Pilot configuration helpers.
"""

import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _csv(name: str, default: str = "") -> List[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
CORS_ORIGINS = _csv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
PILOT_API_KEY = os.getenv("PILOT_API_KEY", "")
PILOT_AUTH_REQUIRED = _bool("PILOT_AUTH_REQUIRED", "false")
ARTIFACT_DIR = os.getenv("ARTIFACT_DIR", "artifacts")
PLAYWRIGHT_RECORD_TRACE = _bool("PLAYWRIGHT_RECORD_TRACE", "true")
PLAYWRIGHT_RECORD_VIDEO = _bool("PLAYWRIGHT_RECORD_VIDEO", "false")
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", "30"))


def validate_startup_config() -> List[str]:
    warnings = []
    if not OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY is not set; AI analysis and reasoning will fail.")
    if "*" in CORS_ORIGINS:
        warnings.append("CORS_ORIGINS contains '*'; use explicit origins for client pilots.")
    if PILOT_AUTH_REQUIRED and not PILOT_API_KEY:
        warnings.append("PILOT_AUTH_REQUIRED=true but PILOT_API_KEY is empty.")
    return warnings
