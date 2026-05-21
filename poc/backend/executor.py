"""
Executor — Playwright Python test execution engine.
Runs approved test cases in a real browser, captures step-by-step results,
and includes a basic self-healing selector fallback.
"""

import asyncio
import base64
import logging
import sys
import time
from typing import List
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)


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


def _try_self_heal(page, step: dict) -> bool:
    """
    Self-healing fallback: if the primary selector fails,
    try alternative strategies to find the element.
    Returns True if element was found and action succeeded.
    """
    value = step.get("value", "")
    action = step.get("action", "")

    strategies = []

    # Strategy 1: Try by text content
    if value:
        strategies.append(("text", f"text={value}"))

    # Strategy 2: Try by placeholder
    if value and action == "fill":
        strategies.append(("placeholder", f"[placeholder*='{value}' i]"))

    # Strategy 3: Try by role
    selector = step.get("selector", "")
    if "button" in selector.lower() or action == "click":
        if value:
            strategies.append(("role-button", f"role=button[name='{value}']"))
    if "input" in selector.lower() or action == "fill":
        strategies.append(("role-textbox", "role=textbox"))

    for strategy_name, alt_selector in strategies:
        try:
            locator = page.locator(alt_selector).first
            if locator.is_visible(timeout=2000):
                if action == "click":
                    locator.click(timeout=3000)
                elif action == "fill":
                    locator.fill(value, timeout=3000)
                logger.info(f"Self-healed using strategy: {strategy_name} → {alt_selector}")
                return True
        except Exception:
            continue

    return False


def execute_test_case(test_case_steps: List[dict], base_url: str = None) -> dict:
    """
    Execute a test case step-by-step in a real Chromium browser.

    Args:
        test_case_steps: list of step dicts with action, selector, value
        base_url: optional base URL (used if steps have relative URLs)

    Returns:
        dict with 'overall_status', 'step_results', and 'duration_seconds'
    """
    step_results = []
    overall_status = "passed"
    start_time = time.time()

    previous_policy = _set_windows_proactor_policy()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)  # headless for server; set False for demo
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )
            page = context.new_page()

            for step in test_case_steps:
                step_index = step.get("step_index", 0)
                action = step.get("action", "")
                selector = step.get("selector", "")
                value = step.get("value", "")
                step_start = time.time()

                try:
                    if action == "navigate":
                        url = value
                        if base_url and not url.startswith("http"):
                            url = base_url.rstrip("/") + "/" + url.lstrip("/")
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)

                    elif action == "click":
                        try:
                            page.click(selector, timeout=5000)
                        except (PlaywrightTimeout, Exception):
                            if not _try_self_heal(page, step):
                                raise

                    elif action == "fill":
                        try:
                            page.fill(selector, value, timeout=5000)
                        except (PlaywrightTimeout, Exception):
                            if not _try_self_heal(page, step):
                                raise

                    elif action == "select":
                        page.select_option(selector, value, timeout=5000)

                    elif action == "assert_text":
                        expect(page.locator(selector)).to_have_text(
                            value, timeout=5000
                        )

                    elif action == "assert_visible":
                        expect(page.locator(selector)).to_be_visible(timeout=5000)

                    elif action == "wait":
                        wait_ms = int(value) if value else 1000
                        page.wait_for_timeout(wait_ms)

                    else:
                        logger.warning(f"Unknown action: {action}")

                    step_duration = (time.time() - step_start) * 1000
                    step_results.append({
                        "step_index": step_index,
                        "action": action,
                        "selector": selector,
                        "status": "passed",
                        "error": None,
                        "screenshot_b64": None,
                        "duration_ms": round(step_duration, 2),
                    })

                except Exception as e:
                    step_duration = (time.time() - step_start) * 1000
                    # Capture screenshot on failure
                    screenshot_b64 = None
                    try:
                        screenshot_bytes = page.screenshot(full_page=False)
                        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                    except Exception:
                        pass

                    step_results.append({
                        "step_index": step_index,
                        "action": action,
                        "selector": selector,
                        "status": "failed",
                        "error": str(e),
                        "screenshot_b64": screenshot_b64,
                        "duration_ms": round(step_duration, 2),
                    })
                    overall_status = "failed"
                    break  # Stop on first failure

            browser.close()
    finally:
        _restore_event_loop_policy(previous_policy)

    total_duration = time.time() - start_time

    return {
        "overall_status": overall_status,
        "step_results": step_results,
        "duration_seconds": round(total_duration, 2),
    }
