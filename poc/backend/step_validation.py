"""
Preflight validation for AI-generated test steps.

The validator is intentionally conservative for interaction steps. A generated
click, hover, fill, or select should target something seen during recording or
something with clear evidence in a captured DOM snapshot.
"""

import re
from typing import Iterable, List, Optional


INTERACTION_ACTIONS = {"click", "fill", "hover", "select"}
FIELD_ACTIONS = {"fill", "select"}
INPUT_ACTIONS = {"change", "fill", "input"}

ID_PATTERN = re.compile(r"#([A-Za-z_][\w-]*)")
TEXT_PATTERN = re.compile(r"^text\s*=\s*(.+)$", re.IGNORECASE)
ATTR_PATTERN = re.compile(
    r"\[\s*(data-testid|name|placeholder|aria-label)\s*[*^$|~]?=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
TAG_ATTR_PATTERN = re.compile(
    r"^\s*([A-Za-z][\w-]*)\s*\[\s*([A-Za-z_:][\w:-]*)\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def validate_steps_against_session(steps: List[dict], session_detail: dict) -> List[dict]:
    evidence = _build_evidence(session_detail)
    issues = []

    for position, step in enumerate(steps, start=1):
        action = str(step.get("action") or "").lower()
        selector = step.get("selector")
        if action not in INTERACTION_ACTIONS:
            continue
        if not isinstance(selector, str) or not selector.strip():
            issues.append(_issue(step, position, "Interaction step is missing a selector."))
            continue
        if _selector_is_supported(selector, action, evidence):
            continue

        issues.append(
            _issue(
                step,
                position,
                _unsupported_selector_error(selector, action, evidence),
            )
        )

    return issues


def selector_has_session_evidence(selector: object, action: str, session_detail: dict) -> bool:
    if not isinstance(selector, str) or not selector.strip():
        return False
    return _selector_is_supported(selector, action, _build_evidence(session_detail))


def selector_evidence_error(selector: object, action: str, session_detail: dict) -> str:
    return _unsupported_selector_error(str(selector or ""), action, _build_evidence(session_detail))


def validation_reason(issues: List[dict]) -> str:
    first = issues[0] if issues else {}
    step_index = first.get("step_index", "?")
    error = first.get("error", "Generated steps did not match the recording evidence.")
    return (
        f"Execution was stopped before Playwright replay because generated step {step_index} "
        f"failed recording preflight validation. {error}"
    )


def _issue(step: dict, position: int, error: str) -> dict:
    return {
        "step_index": step.get("step_index", position),
        "action": step.get("action"),
        "selector": step.get("selector"),
        "error": error,
    }


def _build_evidence(session_detail: dict) -> dict:
    recorded_selectors = set()
    field_selectors = set()
    field_steps_count = 0
    recorded_text = set()
    dom_snapshots = []

    for step in session_detail.get("steps", []):
        action = _normalise_action(step.get("action"))
        selector = step.get("selector")
        if isinstance(selector, str) and selector:
            recorded_selectors.add(selector)
            if action in FIELD_ACTIONS:
                field_selectors.add(selector)
                field_steps_count += 1

        meta = step.get("meta") if isinstance(step.get("meta"), dict) else {}
        for candidate in meta.get("selectors", []) if isinstance(meta.get("selectors"), list) else []:
            if not isinstance(candidate, str) or not candidate:
                continue
            recorded_selectors.add(candidate)
            if action in FIELD_ACTIONS:
                field_selectors.add(candidate)

        for value in (
            step.get("value"),
            meta.get("accessibleName"),
            meta.get("ariaLabel"),
            meta.get("label"),
            meta.get("text"),
        ):
            key = _normalise_text(value)
            if key:
                recorded_text.add(key)

        dom_snapshot = step.get("dom_snapshot")
        if isinstance(dom_snapshot, str) and dom_snapshot:
            dom_snapshots.append(dom_snapshot.lower())

    return {
        "dom_snapshots": list(dict.fromkeys(dom_snapshots)),
        "field_selectors": field_selectors,
        "field_steps_count": field_steps_count,
        "recorded_selectors": recorded_selectors,
        "recorded_text": recorded_text,
    }


def _unsupported_selector_error(selector: str, action: str, evidence: dict) -> str:
    error = (
        f"Selector '{selector}' for {action} was not captured during recording "
        "and has no clear match in a recorded DOM snapshot."
    )
    if action in FIELD_ACTIONS and evidence["field_steps_count"] == 0:
        error += (
            " No form fill/select events were recorded; capture the field entry after "
            "recording starts or submit the populated form so submit-time form-state "
            "capture can preserve the real field selectors."
        )
    return error


def _selector_is_supported(selector: str, action: str, evidence: dict) -> bool:
    selector = selector.strip()
    if selector in evidence["recorded_selectors"]:
        return True
    if action in FIELD_ACTIONS and selector in evidence["field_selectors"]:
        return True

    text_selector = _text_selector_value(selector)
    if text_selector:
        text_key = _normalise_text(text_selector)
        return text_key in evidence["recorded_text"] or _text_in_dom(text_key, evidence["dom_snapshots"])

    return _css_selector_has_dom_evidence(selector, evidence["dom_snapshots"])


def _css_selector_has_dom_evidence(selector: str, dom_snapshots: Iterable[str]) -> bool:
    attrs = ATTR_PATTERN.findall(selector)
    if attrs:
        return any(_attribute_in_dom(name, value, dom_snapshots) for name, value in attrs)

    ids = [element_id for element_id in ID_PATTERN.findall(selector) if element_id.lower() not in {"root", "app", "__next"}]
    if ids:
        return any(_attribute_in_dom("id", element_id, dom_snapshots) for element_id in ids)

    tag_attr = TAG_ATTR_PATTERN.match(selector)
    if tag_attr:
        tag, name, value = tag_attr.groups()
        tag_pattern = re.compile(
            rf"<{re.escape(tag.lower())}\b[^>]*\b{re.escape(name.lower())}\s*=\s*['\"]"
            rf"{re.escape(value.lower())}['\"]",
            re.IGNORECASE,
        )
        return any(tag_pattern.search(snapshot) for snapshot in dom_snapshots)

    return False


def _attribute_in_dom(name: str, value: str, dom_snapshots: Iterable[str]) -> bool:
    pattern = re.compile(
        rf"\b{re.escape(name.lower())}\s*=\s*['\"]{re.escape(value.lower())}['\"]",
        re.IGNORECASE,
    )
    return any(pattern.search(snapshot) for snapshot in dom_snapshots)


def _text_selector_value(selector: str) -> Optional[str]:
    match = TEXT_PATTERN.match(selector)
    if not match:
        return None
    return match.group(1).strip().strip("\"'") or None


def _text_in_dom(text_key: str, dom_snapshots: Iterable[str]) -> bool:
    return bool(text_key) and any(text_key in snapshot for snapshot in dom_snapshots)


def _normalise_action(action: object) -> str:
    action = str(action or "").lower()
    return "fill" if action in INPUT_ACTIONS else action


def _normalise_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())
