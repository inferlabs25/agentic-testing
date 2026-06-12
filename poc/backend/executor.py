"""
Playwright execution engine with deterministic selector fallback and artifacts.
"""

import asyncio
import base64
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import List, Optional
import uuid

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect, sync_playwright

logger = logging.getLogger(__name__)

ACTION_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_ACTION_TIMEOUT_MS", "5000"))
POST_CLICK_SETTLE_MS = int(os.getenv("PLAYWRIGHT_POST_CLICK_SETTLE_MS", "300"))
SECRET_VALUE_PATTERN = re.compile(r"^\{\{?secret:([A-Za-z0-9_.-]+)\}?\}$")
ASSERTION_ATTR_PATTERN = re.compile(
    r"\[\s*(data-testid|aria-label|name|placeholder)\s*[*^$|~]?=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

OVERLAY_HINT_SELECTORS = [
    s.strip()
    for s in os.getenv(
        "PLAYWRIGHT_OVERLAY_HINT_SELECTORS",
        "[id*='cookie'], [class*='cookie'], [id*='consent'], [class*='consent'], text=/cookie|consent/i",
    ).split(",")
    if s.strip()
]
OVERLAY_DISMISS_SELECTORS = [
    s.strip()
    for s in os.getenv(
        "PLAYWRIGHT_DISMISS_SELECTORS",
        "button:has-text('Accept'), button:has-text('Accept all'), button:has-text('I agree'), "
        "button:has-text('Agree'), button:has-text('Got it'), button:has-text('OK'), "
        "button:has-text('Allow all'), button:has-text('Dismiss'), button:has-text('Close'), "
        "[aria-label='Close'], [data-testid='close']",
    ).split(",")
    if s.strip()
]


def _set_windows_proactor_policy():
    if sys.platform != "win32":
        return None
    policy_cls = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if policy_cls is None:
        return None
    current_policy = asyncio.get_event_loop_policy()
    if isinstance(current_policy, policy_cls):
        return None
    asyncio.set_event_loop_policy(policy_cls())
    return current_policy


def _restore_event_loop_policy(previous_policy) -> None:
    if previous_policy is not None:
        asyncio.set_event_loop_policy(previous_policy)


def _resolve_step_value(value):
    if not isinstance(value, str):
        return value

    match = SECRET_VALUE_PATTERN.match(value.strip())
    if not match:
        if value == "********":
            secret_value = os.getenv("TEST_SECRET_PASSWORD")
            if secret_value is not None:
                return secret_value
        return value

    env_key = "TEST_SECRET_" + re.sub(r"[^A-Za-z0-9]+", "_", match.group(1)).upper()
    secret_value = os.getenv(env_key)
    if secret_value is None:
        raise ValueError(
            f"Secret value '{value}' requires backend environment variable {env_key}"
        )
    return secret_value


def _first_visible(locator, max_checks: int = 5):
    try:
        count = locator.count()
    except Exception:
        return locator.first

    for index in range(min(count, max_checks)):
        candidate = locator.nth(index)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return locator.first


def _is_click_target(locator) -> bool:
    try:
        return locator.evaluate(
            """element => {
                const tag = element.tagName.toLowerCase();
                const role = (element.getAttribute("role") || "").toLowerCase();
                const inputType = (element.getAttribute("type") || "").toLowerCase();
                if (["button", "a", "summary", "label"].includes(tag)) return true;
                if (tag === "input" && ["button", "checkbox", "radio", "submit"].includes(inputType)) return true;
                return ["button", "link", "menuitem", "tab"].includes(role);
            }"""
        )
    except Exception:
        return False


def _first_click_target(locator, max_checks: int = 5):
    try:
        count = locator.count()
    except Exception:
        return locator.first

    for index in range(min(count, max_checks)):
        candidate = locator.nth(index)
        try:
            if candidate.is_visible() and _is_click_target(candidate):
                return candidate
        except Exception:
            continue
    return _first_visible(locator, max_checks)


def _dismiss_overlays(page) -> Optional[str]:
    hint_visible = False
    for selector in OVERLAY_HINT_SELECTORS:
        try:
            locator = page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible():
                hint_visible = True
                break
        except Exception:
            continue
    if not hint_visible:
        return None

    for selector in OVERLAY_DISMISS_SELECTORS:
        try:
            locator = page.locator(selector)
            for index in range(min(locator.count(), 3)):
                target = locator.nth(index)
                if target.is_visible():
                    target.click(timeout=2000)
                    page.wait_for_timeout(300)
                    return selector
        except Exception:
            continue
    return None


def _candidate_selectors(step: dict) -> List[tuple]:
    candidates = []
    selector = step.get("selector")
    if isinstance(selector, str) and selector:
        candidates.append(("primary", selector))

    for item in step.get("locator_candidates") or []:
        if isinstance(item, str):
            candidates.append(("recorded-candidate", item))
        elif isinstance(item, dict):
            for selector in item.get("candidates") or []:
                candidates.append(("recorded-candidate", selector))

    value = step.get("value")
    if step.get("action") == "click" and isinstance(value, str) and value:
        candidates.append(("text", f"text={value}"))
        candidates.append(("role-button", f"role=button[name='{value}']"))

    if step.get("action") in {"assert_visible", "assert_text"} and isinstance(selector, str):
        for attr_name, attr_value in ASSERTION_ATTR_PATTERN.findall(selector):
            candidates.append((f"attr-{attr_name}", f"[{attr_name}='{attr_value}']"))
            human_text = _humanise_selector_token(attr_value)
            if human_text:
                candidates.append(("text-derived", f"text={human_text}"))

    seen = set()
    unique = []
    for strategy, selector in candidates:
        if selector and selector not in seen:
            seen.add(selector)
            unique.append((strategy, selector))
    return unique


def _humanise_selector_token(value: object) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").split()).title()


def _perform_action(page, step: dict, selector: str, force: bool = False):
    action = step.get("action")
    value = step.get("value")
    locator = page.locator(selector)

    if action == "click":
        target = _first_click_target(locator)
        try:
            target.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            pass
        target.click(timeout=5000, force=force)
        page.wait_for_timeout(POST_CLICK_SETTLE_MS)
    elif action == "hover":
        _first_visible(locator).hover(timeout=5000)
        page.wait_for_timeout(POST_CLICK_SETTLE_MS)
    elif action == "fill":
        fill_value = _resolve_step_value(value)
        target = _first_visible(locator)
        try:
            target.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            pass
        target.fill(fill_value, timeout=5000, force=force)
    elif action == "select":
        _first_visible(locator).select_option(_resolve_step_value(value), timeout=5000)
    else:
        raise ValueError(f"Action '{action}' does not use selector fallback.")


def _execute_interaction(page, step: dict) -> dict:
    selector = step.get("selector")
    if not selector:
        raise ValueError(f"{step.get('action')} step requires a selector.")

    overlay_selector = _dismiss_overlays(page)
    if overlay_selector:
        try:
            _perform_action(page, step, selector)
            return {
                "selector_used": selector,
                "healing_applied": True,
                "healing_reason": f"overlay-dismissed:{overlay_selector}",
            }
        except Exception:
            pass

    last_error = None
    for strategy, candidate in _candidate_selectors(step):
        try:
            _perform_action(page, step, candidate)
            return {
                "selector_used": candidate,
                "healing_applied": strategy != "primary",
                "healing_reason": None if strategy == "primary" else strategy,
            }
        except Exception as exc:
            last_error = exc
            continue

    try:
        _perform_action(page, step, selector, force=True)
        return {
            "selector_used": selector,
            "healing_applied": True,
            "healing_reason": "force-last-resort",
        }
    except Exception as exc:
        raise last_error or exc


def _execute_assert_visible(page, step: dict) -> dict:
    selector = step.get("selector")
    if not selector:
        raise ValueError("assert_visible step requires a selector.")

    last_error = None
    for strategy, candidate in _candidate_selectors(step):
        try:
            expect(_first_visible(page.locator(candidate))).to_be_visible(timeout=5000)
            return {
                "selector_used": candidate,
                "healing_applied": strategy != "primary",
                "healing_reason": None if strategy == "primary" else strategy,
            }
        except Exception as exc:
            last_error = exc
            continue
    raise last_error


def _execute_assert_text(page, step: dict) -> dict:
    selector = step.get("selector")
    value = step.get("value")
    if not selector:
        raise ValueError("assert_text step requires a selector.")
    if not isinstance(value, str):
        raise ValueError("assert_text requires expected text in value.")

    last_error = None
    for strategy, candidate in _candidate_selectors(step):
        try:
            expect(_first_visible(page.locator(candidate))).to_contain_text(value, timeout=5000)
            return {
                "selector_used": candidate,
                "healing_applied": strategy != "primary",
                "healing_reason": None if strategy == "primary" else strategy,
            }
        except Exception as exc:
            last_error = exc
            continue
    raise last_error


def _save_failure_screenshot(page, artifact_root: Path, run_id: str, step_index: int) -> tuple:
    try:
        screenshot_bytes = page.screenshot(full_page=False)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
        screenshot_path = artifact_root / run_id / f"step-{step_index}-failure.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(screenshot_bytes)
        return screenshot_b64, str(screenshot_path)
    except Exception:
        return None, None


def execute_test_case(
    test_case_steps: List[dict],
    base_url: str = None,
    artifact_dir: str = None,
    record_trace: bool = True,
    record_video: bool = False,
) -> dict:
    step_results = []
    artifact_paths = []
    overall_status = "passed"
    start_time = time.time()
    run_id = str(uuid.uuid4())
    artifact_root = Path(artifact_dir or os.getenv("ARTIFACT_DIR", "artifacts"))
    artifact_root.mkdir(parents=True, exist_ok=True)

    previous_policy = _set_windows_proactor_policy()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context_args = {
                "viewport": {"width": 1280, "height": 720},
                "ignore_https_errors": True,
            }
            if record_video:
                video_dir = artifact_root / run_id / "videos"
                video_dir.mkdir(parents=True, exist_ok=True)
                context_args["record_video_dir"] = str(video_dir)

            context = browser.new_context(**context_args)
            if record_trace:
                context.tracing.start(screenshots=True, snapshots=True, sources=False)

            page = context.new_page()
            page.set_default_timeout(ACTION_TIMEOUT_MS)
            has_navigated = False

            for step in test_case_steps:
                step_index = step.get("step_index", 0)
                action = step.get("action", "")
                selector = step.get("selector")
                step_start = time.time()
                selector_used = selector
                healing_applied = False
                healing_reason = None

                try:
                    if action == "navigate":
                        url = step.get("value")
                        if not isinstance(url, str):
                            raise ValueError("navigate step requires URL in value.")
                        if base_url and not url.startswith("http"):
                            url = base_url.rstrip("/") + "/" + url.lstrip("/")
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        has_navigated = True
                    elif action in {"click", "hover", "fill", "select"}:
                        if not has_navigated and base_url:
                            page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
                            has_navigated = True
                        action_result = _execute_interaction(page, step)
                        selector_used = action_result["selector_used"]
                        healing_applied = action_result["healing_applied"]
                        healing_reason = action_result["healing_reason"]
                    elif action == "assert_text":
                        if not has_navigated and base_url:
                            page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
                            has_navigated = True
                        assertion_result = _execute_assert_text(page, step)
                        selector_used = assertion_result["selector_used"]
                        healing_applied = assertion_result["healing_applied"]
                        healing_reason = assertion_result["healing_reason"]
                    elif action == "assert_visible":
                        if not has_navigated and base_url:
                            page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
                            has_navigated = True
                        assertion_result = _execute_assert_visible(page, step)
                        selector_used = assertion_result["selector_used"]
                        healing_applied = assertion_result["healing_applied"]
                        healing_reason = assertion_result["healing_reason"]
                    elif action == "wait":
                        page.wait_for_timeout(int(step.get("value") or 1000))
                    else:
                        raise ValueError(f"Unknown action: {action}")

                    step_results.append({
                        "step_index": step_index,
                        "action": action,
                        "selector": selector,
                        "selector_used": selector_used,
                        "status": "passed",
                        "error": None,
                        "screenshot_b64": None,
                        "duration_ms": round((time.time() - step_start) * 1000, 2),
                        "healing_applied": healing_applied,
                        "healing_reason": healing_reason,
                    })
                except Exception as exc:
                    screenshot_b64, screenshot_path = _save_failure_screenshot(
                        page, artifact_root, run_id, step_index
                    )
                    if screenshot_path:
                        artifact_paths.append(screenshot_path)

                    step_results.append({
                        "step_index": step_index,
                        "action": action,
                        "selector": selector,
                        "selector_used": selector_used,
                        "status": "failed",
                        "error": str(exc),
                        "screenshot_b64": screenshot_b64,
                        "duration_ms": round((time.time() - step_start) * 1000, 2),
                        "healing_applied": healing_applied,
                        "healing_reason": healing_reason,
                    })
                    overall_status = "failed"
                    logger.warning("Step %s failed: %s", step_index, exc)
                    break

            if record_trace:
                try:
                    trace_path = artifact_root / run_id / "trace.zip"
                    trace_path.parent.mkdir(parents=True, exist_ok=True)
                    context.tracing.stop(path=str(trace_path))
                    artifact_paths.append(str(trace_path))
                except Exception as exc:
                    logger.warning("Trace capture failed: %s", exc)

            browser.close()
    finally:
        _restore_event_loop_policy(previous_policy)

    return {
        "overall_status": overall_status,
        "step_results": step_results,
        "duration_seconds": round(time.time() - start_time, 2),
        "artifact_paths": artifact_paths,
    }
