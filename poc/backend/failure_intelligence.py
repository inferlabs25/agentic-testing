"""
Structured failure classification for execution results.
"""

import json
from typing import List, Optional

FAILURE_CATEGORIES = {
    "app_bug",
    "selector_issue",
    "assertion_mismatch",
    "test_data_issue",
    "environment_issue",
    "auth_issue",
    "network_issue",
    "flow_construction_issue",
}


def classify_failure(
    failed_step: dict,
    reasoning_text: Optional[str] = None,
    network_logs: Optional[List[dict]] = None,
    test_steps: Optional[List[dict]] = None,
) -> dict:
    error = str(failed_step.get("error") or "").lower()
    action = str(failed_step.get("action") or "").lower()
    reasoning = str(reasoning_text or "")
    reasoning_lower = reasoning.lower()

    # 1. Flow Construction Issue Heuristics
    is_flow_issue = False
    if "flow_construction" in reasoning_lower or "missing_login" in reasoning_lower or "flow construction" in reasoning_lower:
        is_flow_issue = True
    elif test_steps:
        # Check if the test is short (fewer than 3 steps) or has no navigate/login steps
        has_login = any(
            "password" in str(s.get("selector") or "").lower() or 
            any(t in str(s.get("value") or "").lower() for t in ("login", "signin", "auth"))
            for s in test_steps
        )
        if not has_login:
            # If a locator timeout occurs (indicated by selector/locator/timeout)
            if any(token in error for token in ("selector", "locator", "strict mode", "element", "timeout")):
                is_flow_issue = True

    category = "app_bug"
    confidence = 0.55
    if is_flow_issue:
        category, confidence = "flow_construction_issue", 0.85
    elif any(token in error for token in ("selector", "locator", "strict mode", "element")):
        category, confidence = "selector_issue", 0.82
    elif action.startswith("assert") or "expected" in error or "to_have_text" in error:
        category, confidence = "assertion_mismatch", 0.8
    elif "secret value" in error or "credential" in reasoning_lower or "invalid email" in reasoning_lower:
        category, confidence = "test_data_issue", 0.72
    elif "timeout" in error or "net::" in error or "navigation" in error:
        category, confidence = "environment_issue", 0.68
    elif "401" in reasoning_lower or "403" in reasoning_lower or "unauthorized" in reasoning_lower:
        category, confidence = "auth_issue", 0.82
    elif _has_network_failure(network_logs):
        category, confidence = "network_issue", 0.78

    return {
        "category": category,
        "confidence": confidence,
        "root_cause": reasoning or str(failed_step.get("error") or "Execution failed."),
        "evidence": {
            "step_index": failed_step.get("step_index"),
            "action": failed_step.get("action"),
            "selector": failed_step.get("selector"),
            "error": failed_step.get("error"),
        },
        "recommended_fix": _recommended_fix(category),
    }


def reasoning_to_text(reasoning: object) -> str:
    if isinstance(reasoning, dict):
        return reasoning.get("root_cause") or json.dumps(reasoning)
    return str(reasoning or "")


def _has_network_failure(network_logs: Optional[List[dict]]) -> bool:
    for entry in network_logs or []:
        try:
            status = int(entry.get("status", 200))
        except Exception:
            status = 200
        if status == 0 or status >= 500:
            return True
    return False


def _recommended_fix(category: str) -> str:
    return {
        "selector_issue": "Refresh selector candidates from the latest recording or use a stable data-testid/role locator.",
        "assertion_mismatch": "Update the expected assertion to match verified product behavior, or raise a product bug if the UI is wrong.",
        "test_data_issue": "Provide valid pilot test data and configure required TEST_SECRET_* environment values.",
        "environment_issue": "Check application availability, login state, timeouts, and network stability before rerunning.",
        "auth_issue": "Refresh credentials or session setup before executing this suite.",
        "network_issue": "Inspect failing API calls and backend/service health around the failed step.",
        "app_bug": "Review the captured screenshot, network evidence, and failing step with the product team.",
        "flow_construction_issue": "Regenerate the test with login and module navigation steps prepended, or attach a reusable authenticated setup fixture. The test attempted to interact with a protected page without completing the authentication flow.",
    }.get(category, "Review the failing step evidence and rerun after fixing the root cause.")
