"""
Readiness classification for AI-generated test cases.
"""

from typing import Dict, List, Optional, Tuple
import re

from step_validation import (
    selector_evidence_error,
    selector_has_session_evidence,
    validate_steps_against_session,
)

ALLOWED_ACTIONS = {
    "navigate",
    "click",
    "hover",
    "fill",
    "assert_text",
    "assert_visible",
    "select",
    "wait",
}
INTERACTION_ACTIONS = {"click", "hover", "fill", "select"}
MEANINGFUL_ACTIONS = INTERACTION_ACTIONS | {"assert_text", "assert_visible"}
ASSERTION_ATTR_PATTERN = re.compile(
    r"\[\s*(data-testid|aria-label|name|placeholder)\s*[*^$|~]?=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def prepare_generated_test_case(tc_data: dict, session_detail: dict) -> dict:
    steps, schema_issues = _normalise_steps(tc_data.get("steps", []))
    steps = _ensure_prerequisite_flow(steps, session_detail)
    steps = _reconstruct_navigation_path(steps, session_detail)
    steps = _add_defensive_waits(steps)
    steps = _enrich_steps_from_recording(steps, session_detail)
    steps = _ensure_initial_navigation(steps, session_detail)
    validation_issues = validate_steps_against_session(steps, session_detail)
    assertion_issues = _validate_assertions(steps, session_detail)
    auth_issues = _detect_missing_auth_from_context(steps, session_detail)
    issues = schema_issues + validation_issues + assertion_issues + auth_issues
    readiness_status = "suggested_review" if issues else "ready_to_run"
    readiness_reason = (
        "; ".join(issue["error"] for issue in issues[:3])
        if issues
        else "Ready to run: every executable interaction is grounded in recorded evidence."
    )
    locator_candidates = _locator_candidates(steps, session_detail)
    evidence_source = {
        "session_id": session_detail.get("session_id"),
        "recorded_steps": len(session_detail.get("steps", [])),
        "validation_issues": issues,
    }

    for step in steps:
        step["readiness_status"] = readiness_status
        step["readiness_reason"] = readiness_reason
        step["locator_candidates"] = _candidates_for_selector(step.get("selector"), session_detail)
        step["evidence_source"] = {
            "source": "recorded_session" if not issues else "ai_suggestion_needs_review"
        }

    return {
        "title": tc_data.get("title", "Untitled Test"),
        "test_type": tc_data.get("type", tc_data.get("test_type", "happy")),
        "steps": steps,
        "expected_result": tc_data.get("expected_result", ""),
        "reason": tc_data.get("reason", ""),
        "readiness_status": readiness_status,
        "readiness_reason": readiness_reason,
        "locator_candidates": locator_candidates,
        "evidence_source": evidence_source,
        "status": "draft" if readiness_status == "ready_to_run" else "suggested_review",
    }


def _steps_match(gen_step: dict, rec_step: dict) -> bool:
    if gen_step.get("action") != rec_step.get("action"):
        return False
    gen_sel = gen_step.get("selector")
    rec_sel = rec_step.get("selector")
    if gen_sel == rec_sel:
        return True
    meta = rec_step.get("meta") or {}
    candidates = meta.get("selectors", [])
    if gen_sel in candidates:
        return True
    return False


def _reconstruct_navigation_path(steps: List[dict], session_detail: dict) -> List[dict]:
    first_meaningful_step = None
    for step in steps:
        if step.get("action") in MEANINGFUL_ACTIONS:
            first_meaningful_step = step
            break
            
    if not first_meaningful_step:
        return steps
        
    recorded_steps = session_detail.get("steps", [])
    first_match_idx = -1
    for idx, recorded_step in enumerate(recorded_steps):
        if _steps_match(first_meaningful_step, recorded_step):
            first_match_idx = idx
            break
            
    if first_match_idx <= 0:
        return steps
        
    auth_flow = _auth_prerequisite_flow(session_detail)
    start_idx = 0
    if auth_flow:
        start_idx = auth_flow.get("end_step_index", 0)
        
    nav_steps = []
    for i in range(start_idx, first_match_idx):
        r_step = recorded_steps[i]
        action = r_step.get("action")
        if action in ALLOWED_ACTIONS:
            nav_steps.append(_recorded_step_to_test_step(r_step))
            
    nav_steps = [s for s in nav_steps if s]
    
    if nav_steps:
        cleaned_steps = _drop_duplicate_initial_navigate(
            steps,
            nav_steps[-1].get("value") if nav_steps[-1].get("action") == "navigate" else None
        )
        return _renumber_steps(nav_steps + cleaned_steps)
        
    return steps


def _add_defensive_waits(steps: List[dict]) -> List[dict]:
    waited_steps = []
    for step in steps:
        waited_steps.append(step)
        action = step.get("action")
        
        if action in {"click", "submit"} and _is_login_submit(step):
            waited_steps.append({
                "action": "wait",
                "selector": None,
                "value": "2000"
            })
        elif action == "navigate":
            waited_steps.append({
                "action": "wait",
                "selector": None,
                "value": "1000"
            })
            
    first_assertion_idx = -1
    for idx, step in enumerate(waited_steps):
        if step.get("action") in {"assert_text", "assert_visible"}:
            first_assertion_idx = idx
            break
            
    if first_assertion_idx != -1:
        waited_steps.insert(first_assertion_idx, {
            "action": "wait",
            "selector": None,
            "value": "500"
        })
        
    return _renumber_steps(waited_steps)


def _detect_missing_auth_from_context(steps: List[dict], session_detail: dict) -> List[dict]:
    issues = []
    auth_ctx = session_detail.get("auth_context")
    if isinstance(auth_ctx, dict) and auth_ctx.get("requires_auth"):
        if not _steps_include_auth(steps):
            issues.append(_issue(
                1,
                None,
                None,
                "missing_auth_precondition: This flow requires authentication context but no login steps are present."
            ))
    return issues


def auto_repair_test_case(tc_data: dict, session_detail: dict) -> dict:
    """
    Convert a suggested test into the safest executable version possible.

    The repair is conservative: it removes unverified assertion steps and
    truncated selectors, then reruns the same readiness pipeline. It does not
    invent selectors or expected text.
    """
    steps, _ = _normalise_steps(tc_data.get("steps", []))
    steps = _ensure_initial_navigation(steps, session_detail)
    repaired_steps = []
    repair_notes = []

    for step in steps:
        action = step.get("action")
        selector = step.get("selector")
        value = step.get("value")

        if isinstance(selector, str) and "..." in selector:
            repair_notes.append(
                f"Removed step {step.get('step_index')} because its selector was truncated."
            )
            continue

        if action == "assert_text":
            if value and not _text_was_observed(value, session_detail):
                repair_notes.append(
                    f"Removed unverified text assertion '{value}'."
                )
                continue

        if action == "assert_visible" and isinstance(selector, str):
            if not selector_has_session_evidence(selector, action, session_detail):
                replacement = _replacement_assertion_for_selector(selector, session_detail)
                if replacement:
                    repaired_steps.append({**step, **replacement})
                    repair_notes.append(
                        f"Replaced unsupported visibility selector '{selector}' with '{replacement['selector']}'."
                    )
                    continue
                repair_notes.append(
                    f"Removed unsupported visibility selector '{selector}'."
                )
                continue

        repaired_steps.append(step)

    repaired_payload = {
        "title": tc_data.get("title", "Untitled Test"),
        "type": tc_data.get("type", tc_data.get("test_type", "happy")),
        "steps": _renumber_steps(repaired_steps),
        "expected_result": tc_data.get("expected_result") or "",
        "reason": tc_data.get("reason") or "",
    }

    if repair_notes:
        repaired_payload["expected_result"] = (
            "Executable smoke validation: the repaired flow should complete without "
            "selector, navigation, or runtime failures. "
            + " ".join(repair_notes)
        )
        repaired_payload["reason"] = (
            (repaired_payload["reason"] + " ") if repaired_payload["reason"] else ""
        ) + "Auto-reviewed from suggested test; unverified assertions were removed instead of guessed."

    prepared = prepare_generated_test_case(repaired_payload, session_detail)
    prepared["auto_review_notes"] = repair_notes
    if not _has_meaningful_step(prepared["steps"]):
        issue = _issue(
            1,
            None,
            None,
            "Auto-review removed all executable steps; record or keep at least one grounded action before running.",
        )
        prepared["readiness_status"] = "suggested_review"
        prepared["readiness_reason"] = issue["error"]
        prepared["status"] = "suggested_review"
        prepared["evidence_source"]["validation_issues"].append(issue)
        for step in prepared["steps"]:
            step["readiness_status"] = "suggested_review"
            step["readiness_reason"] = issue["error"]
    if repair_notes and prepared["readiness_status"] == "ready_to_run":
        prepared["readiness_reason"] = (
            "Auto-reviewed into READY by removing unverified assertions. "
            + " ".join(repair_notes)
        )
        for step in prepared["steps"]:
            step["readiness_reason"] = prepared["readiness_reason"]
    return prepared


def readiness_counts(test_cases: List[dict]) -> Dict[str, int]:
    counts = {"ready_to_run": 0, "suggested_review": 0}
    for test_case in test_cases:
        status = test_case.get("readiness_status") or "ready_to_run"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _normalise_steps(raw_steps: object) -> Tuple[List[dict], List[dict]]:
    if not isinstance(raw_steps, list) or not raw_steps:
        return [], [_issue(1, None, None, "Test case has no executable steps.")]

    steps = []
    issues = []
    for index, raw_step in enumerate(raw_steps, start=1):
        step = dict(raw_step) if isinstance(raw_step, dict) else {}
        step["step_index"] = int(step.get("step_index") or index)
        action = str(step.get("action") or "").lower()
        step["action"] = action
        selector = step.get("selector")
        value = step.get("value")
        if isinstance(value, str):
            step["value"] = _normalise_secret_placeholder(value)
            value = step["value"]

        if action not in ALLOWED_ACTIONS:
            issues.append(_issue(index, action, selector, f"Unsupported action '{action}'."))
        if isinstance(selector, str) and "..." in selector:
            issues.append(_issue(index, action, selector, "Selector is truncated and cannot be executed."))
        if action == "navigate" and not isinstance(value, str):
            issues.append(_issue(index, action, selector, "Navigate step requires URL in value."))
        if action == "assert_text" and not isinstance(value, str):
            issues.append(_issue(index, action, selector, "assert_text requires expected text in value."))
        if action in {"assert_text", "assert_visible"} and not isinstance(selector, str):
            issues.append(_issue(index, action, selector, f"{action} requires a selector."))
        if action in INTERACTION_ACTIONS and not isinstance(selector, str):
            issues.append(_issue(index, action, selector, f"{action} requires a selector."))
        steps.append(step)

    return steps, issues


def _renumber_steps(steps: List[dict]) -> List[dict]:
    renumbered = []
    for index, step in enumerate(steps, start=1):
        copy = dict(step)
        copy["step_index"] = index
        renumbered.append(copy)
    return renumbered


def _has_meaningful_step(steps: List[dict]) -> bool:
    return any(step.get("action") in MEANINGFUL_ACTIONS for step in steps)


def _normalise_secret_placeholder(value: str) -> str:
    match = re.match(r"^\{\{?secret:([A-Za-z0-9_.-]+)\}?\}$", value.strip())
    if not match:
        return value
    return "{{secret:" + match.group(1) + "}}"


def _enrich_steps_from_recording(steps: List[dict], session_detail: dict) -> List[dict]:
    enriched = []
    for step in steps:
        copy = dict(step)
        recorded = _matching_recorded_step(copy.get("selector"), session_detail)
        if recorded and copy.get("action") == "click" and not copy.get("value"):
            meta = recorded.get("meta") if isinstance(recorded.get("meta"), dict) else {}
            copy["value"] = recorded.get("value") or meta.get("text") or meta.get("accessibleName")
        if recorded and "meta" not in copy and isinstance(recorded.get("meta"), dict):
            copy["meta"] = recorded["meta"]
        enriched.append(copy)
    return enriched


def _matching_recorded_step(selector: object, session_detail: dict) -> dict:
    if not isinstance(selector, str) or not selector:
        return {}
    for recorded_step in session_detail.get("steps", []):
        meta = recorded_step.get("meta") if isinstance(recorded_step.get("meta"), dict) else {}
        candidates = meta.get("selectors", []) if isinstance(meta.get("selectors"), list) else []
        if selector == recorded_step.get("selector") or selector in candidates:
            return recorded_step
    return {}


def _ensure_prerequisite_flow(steps: List[dict], session_detail: dict) -> List[dict]:
    auth_flow = _auth_prerequisite_flow(session_detail)
    if not auth_flow or _steps_include_auth(steps):
        return steps

    if not _needs_auth_prerequisite(steps, session_detail, auth_flow["end_step_index"]):
        return steps

    generated_steps = _drop_duplicate_initial_navigate(
        steps,
        auth_flow["steps"][-1].get("value") if auth_flow["steps"] else None,
    )
    return _renumber_steps(auth_flow["steps"] + generated_steps)


def _auth_prerequisite_flow(session_detail: dict) -> dict:
    recorded_steps = session_detail.get("steps", [])
    submit_position = _login_submit_position(recorded_steps)
    if submit_position is None:
        return {}

    identity_step = _last_matching_step(recorded_steps[:submit_position], _is_identity_fill)
    password_step = _last_matching_step(recorded_steps[:submit_position], _is_password_fill)
    submit_step = recorded_steps[submit_position]
    if not identity_step or not password_step:
        return {}

    login_nav = _last_matching_step(
        recorded_steps[:submit_position],
        lambda step: step.get("action") == "navigate" and _is_auth_url(step.get("url")),
    )
    post_login_nav = next(
        (
            step
            for step in recorded_steps[submit_position + 1:]
            if step.get("action") == "navigate" and _is_protected_url(step.get("url"))
        ),
        None,
    )

    prefix = [
        _recorded_step_to_test_step(step)
        for step in (login_nav, identity_step, password_step, submit_step, post_login_nav)
        if step
    ]
    prefix = [step for step in prefix if step]
    if len(prefix) < 4:
        return {}
    return {
        "steps": _renumber_steps(prefix),
        "end_step_index": post_login_nav.get("step_index") if post_login_nav else submit_step.get("step_index"),
    }


def _login_submit_position(recorded_steps: List[dict]) -> Optional[int]:
    password_seen = False
    for index, step in enumerate(recorded_steps):
        if _is_password_fill(step):
            password_seen = True
            continue
        if not password_seen:
            continue
        if step.get("action") == "click" and _is_login_submit(step):
            return index
    return None


def _last_matching_step(steps: List[dict], predicate) -> dict:
    for step in reversed(steps):
        if predicate(step):
            return step
    return {}


def _recorded_step_to_test_step(step: dict) -> dict:
    action = step.get("action")
    if action == "navigate":
        url = step.get("url")
        if not isinstance(url, str) or not url.startswith("http"):
            return {}
        return {"action": "navigate", "selector": None, "value": url}
    if action not in ALLOWED_ACTIONS:
        return {}
    copied = {
        "action": action,
        "selector": step.get("selector"),
        "value": step.get("value"),
    }
    if copied["value"] == "********":
        copied["value"] = "{{secret:password}}"
    meta = step.get("meta")
    if isinstance(meta, dict):
        copied["meta"] = meta
    return copied


def _drop_duplicate_initial_navigate(steps: List[dict], prefix_url: object) -> List[dict]:
    if not steps or steps[0].get("action") != "navigate":
        return steps
    if _normalise_url(steps[0].get("value")) == _normalise_url(prefix_url):
        return steps[1:]
    return steps


def _steps_include_auth(steps: List[dict]) -> bool:
    return any(
        _is_password_fill(step)
        or _is_identity_fill(step)
        or (step.get("action") == "navigate" and _is_auth_url(step.get("value")))
        for step in steps
    )


def _needs_auth_prerequisite(steps: List[dict], session_detail: dict, auth_end_step_index: int) -> bool:
    if not steps:
        return False

    for step in steps:
        if step.get("action") == "navigate" and _is_protected_url(step.get("value")):
            return True

    protected_selectors = _recorded_selectors_after(session_detail, auth_end_step_index)
    return any(
        isinstance(step.get("selector"), str) and step.get("selector") in protected_selectors
        for step in steps
        if step.get("action") in MEANINGFUL_ACTIONS
    )


def _recorded_selectors_after(session_detail: dict, step_index: int) -> set:
    selectors = set()
    for step in session_detail.get("steps", []):
        if int(step.get("step_index") or 0) <= int(step_index or 0):
            continue
        selector = step.get("selector")
        if isinstance(selector, str) and selector:
            selectors.add(selector)
        meta = step.get("meta") if isinstance(step.get("meta"), dict) else {}
        for candidate in meta.get("selectors", []) if isinstance(meta.get("selectors"), list) else []:
            if isinstance(candidate, str) and candidate:
                selectors.add(candidate)
    return selectors


def _is_password_fill(step: dict) -> bool:
    if step.get("action") != "fill":
        return False
    haystack = _step_identity_text(step)
    return "password" in haystack or "passwd" in haystack


def _is_identity_fill(step: dict) -> bool:
    if step.get("action") != "fill":
        return False
    haystack = _step_identity_text(step)
    return any(token in haystack for token in ("identifier", "email", "username", "user name", "login id"))


def _is_login_submit(step: dict) -> bool:
    haystack = _step_identity_text(step)
    return any(token in haystack for token in ("sign in", "signin", "log in", "login", "submit"))


def _step_identity_text(step: dict) -> str:
    meta = step.get("meta") if isinstance(step.get("meta"), dict) else {}
    values = [
        step.get("selector"),
        step.get("value"),
        meta.get("accessibleName"),
        meta.get("ariaLabel"),
        meta.get("label"),
        meta.get("name"),
        meta.get("placeholder"),
        meta.get("text"),
        meta.get("type"),
    ]
    return " ".join(_normalise_text(value) for value in values if value)


def _is_auth_url(value: object) -> bool:
    url = str(value or "").lower()
    return any(token in url for token in ("/login", "/signin", "/sign-in", "/auth"))


def _is_protected_url(value: object) -> bool:
    url = str(value or "").lower()
    return url.startswith("http") and not _is_auth_url(url)


def _normalise_url(value: object) -> str:
    return str(value or "").split("#", 1)[0].rstrip("/")


def _ensure_initial_navigation(steps: List[dict], session_detail: dict) -> List[dict]:
    if not steps or steps[0].get("action") == "navigate":
        return steps

    first_url = _first_recorded_url(session_detail)
    if not first_url:
        return steps

    navigate = {
        "step_index": 1,
        "action": "navigate",
        "selector": None,
        "value": first_url,
    }
    renumbered = [navigate]
    for index, step in enumerate(steps, start=2):
        copy = dict(step)
        copy["step_index"] = index
        renumbered.append(copy)
    return renumbered


def _first_recorded_url(session_detail: dict) -> str:
    for step in session_detail.get("steps", []):
        url = step.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
    url = session_detail.get("url")
    return url if isinstance(url, str) else ""


def _validate_assertions(steps: List[dict], session_detail: dict) -> List[dict]:
    issues = []
    for position, step in enumerate(steps, start=1):
        action = step.get("action")
        selector = step.get("selector")
        value = step.get("value")
        if action == "assert_text":
            if value and not _text_was_observed(value, session_detail):
                issues.append(_issue(
                    step.get("step_index", position),
                    action,
                    selector,
                        f"Assertion text '{value}' was not observed in the recording evidence.",
                ))
        elif action == "assert_visible" and isinstance(selector, str):
            if not selector_has_session_evidence(selector, action, session_detail):
                issues.append(_issue(
                    step.get("step_index", position),
                    action,
                    selector,
                    selector_evidence_error(selector, action, session_detail),
                ))
    return issues


def _recorded_text_evidence(session_detail: dict) -> set:
    evidence = set()
    for step in session_detail.get("steps", []):
        meta = step.get("meta") if isinstance(step.get("meta"), dict) else {}
        for value in (
            step.get("value"),
            meta.get("accessibleName"),
            meta.get("ariaLabel"),
            meta.get("label"),
            meta.get("text"),
        ):
            key = _normalise_text(value)
            if key:
                evidence.add(key)
        dom_snapshot = step.get("dom_snapshot")
        if isinstance(dom_snapshot, str):
            for text in re.findall(r">([^<]{2,120})<", dom_snapshot):
                key = _normalise_text(text)
                if key:
                    evidence.add(key)
    return evidence


def _text_was_observed(value: object, session_detail: dict) -> bool:
    key = _normalise_text(value)
    if not key:
        return False
    if key in _recorded_text_evidence(session_detail):
        return True
    return any(
        key in _normalise_text(step.get("dom_snapshot"))
        for step in session_detail.get("steps", [])
        if isinstance(step.get("dom_snapshot"), str)
    )


def _replacement_assertion_for_selector(selector: str, session_detail: dict) -> dict:
    candidates = []
    for _name, value in ASSERTION_ATTR_PATTERN.findall(selector):
        candidates.append(_humanise_token(value))
    if "dashboard" in selector.lower():
        candidates.extend(["Dashboard", "Welcome back"])

    seen = set()
    for text in candidates:
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        if selector_has_session_evidence(f"text={text}", "assert_visible", session_detail):
            return {"action": "assert_visible", "selector": f"text={text}", "value": None}
    return {}


def _humanise_token(value: object) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").split()).title()


def _issue(step_index: int, action: object, selector: object, error: str) -> dict:
    return {
        "step_index": step_index,
        "action": action,
        "selector": selector,
        "error": error,
    }


def _locator_candidates(steps: List[dict], session_detail: dict) -> List[dict]:
    candidates = []
    for step in steps:
        selector = step.get("selector")
        if not selector:
            continue
        candidates.append({
            "step_index": step.get("step_index"),
            "selector": selector,
            "candidates": _candidates_for_selector(selector, session_detail),
        })
    return candidates


def _candidates_for_selector(selector: object, session_detail: dict) -> List[str]:
    if not isinstance(selector, str) or not selector:
        return []
    candidates = []
    for recorded_step in session_detail.get("steps", []):
        meta = recorded_step.get("meta") if isinstance(recorded_step.get("meta"), dict) else {}
        recorded_selector = recorded_step.get("selector")
        if recorded_selector == selector:
            candidates.append(recorded_selector)
            candidates.extend(meta.get("selectors", []) if isinstance(meta.get("selectors"), list) else [])
        elif selector in (meta.get("selectors", []) if isinstance(meta.get("selectors"), list) else []):
            candidates.append(selector)
            candidates.extend(meta.get("selectors", []))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _normalise_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())
