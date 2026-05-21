"""
Executor — Playwright Python test execution engine.
Runs approved test cases in a real browser, captures step-by-step results,
and includes a basic self-healing selector fallback.
"""

import asyncio
import base64
import logging
import os
import re
import sys
import time
from typing import List
from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

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

ACTION_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_ACTION_TIMEOUT_MS", "5000"))
POST_CLICK_SETTLE_MS = int(os.getenv("PLAYWRIGHT_POST_CLICK_SETTLE_MS", "300"))
POST_CLICK_NAVIGATION_TIMEOUT_MS = int(
    os.getenv("PLAYWRIGHT_POST_CLICK_NAVIGATION_TIMEOUT_MS", "5000")
)
SECRET_VALUE_PATTERN = re.compile(r"^\{\{secret:([A-Za-z0-9_.-]+)\}\}$")


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


def _is_any_visible(page, selectors: List[str]) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible():
                return True
        except Exception:
            continue
    return False


def _dismiss_overlays(page) -> bool:
    if not _is_any_visible(page, OVERLAY_HINT_SELECTORS):
        return False

    for selector in OVERLAY_DISMISS_SELECTORS:
        try:
            locator = page.locator(selector)
            count = min(locator.count(), 3)
            for i in range(count):
                target = locator.nth(i)
                if target.is_visible():
                    target.click(timeout=2000)
                    logger.info("Dismissed overlay using selector: %s", selector)
                    page.wait_for_timeout(300)
                    return True
        except Exception:
            continue

    return False


def _pick_visible(locator, max_checks: int = 5):
    try:
        count = locator.count()
    except Exception:
        return locator

    for i in range(min(count, max_checks)):
        candidate = locator.nth(i)
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
                if (tag === "input" && ["button", "checkbox", "radio", "submit"].includes(inputType)) {
                    return true;
                }
                return ["button", "link", "menuitem", "tab"].includes(role);
            }"""
        )
    except Exception:
        return False


def _pick_click_target(locator, max_checks: int = 5):
    try:
        count = locator.count()
    except Exception:
        return locator

    for i in range(min(count, max_checks)):
        candidate = locator.nth(i)
        try:
            if candidate.is_visible() and _is_click_target(candidate):
                return candidate
        except Exception:
            continue

    return _pick_visible(locator, max_checks)


def _resolve_action_locator(page, selector: str):
    return _pick_visible(page.locator(selector))


def _resolve_click_locator(page, selector: str):
    locator = _pick_click_target(page.locator(selector))
    return _reveal_hidden_action_target(page, selector, locator)


def _escape_css_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _is_visible(locator) -> bool:
    try:
        return locator.count() > 0 and locator.is_visible()
    except Exception:
        return False


def _has_match(locator) -> bool:
    try:
        return locator.count() > 0
    except Exception:
        return False


def _element_handle(locator):
    try:
        if not _has_match(locator):
            return None
        return locator.element_handle(timeout=ACTION_TIMEOUT_MS)
    except Exception:
        return None


def _is_handle_visible(handle) -> bool:
    if handle is None:
        return False
    try:
        return handle.is_visible()
    except Exception:
        return False


def _panel_ids_from_target(selector: str, target_handle=None) -> List[str]:
    panel_ids = re.findall(r"#([A-Za-z_][\w-]*)", selector or "")

    if target_handle is not None:
        try:
            panel_ids.extend(target_handle.evaluate(
                """element => {
                    const ids = [];
                    let current = element;
                    while (current && current !== document.body) {
                        if (current.id) ids.push(current.id);
                        current = current.parentElement;
                    }
                    return ids;
                }"""
            ))
        except Exception:
            pass

    return list(dict.fromkeys(panel_ids))


def _panel_trigger_selectors(panel_ids: List[str]) -> List[str]:
    trigger_selectors = []
    for panel_id in panel_ids:
        escaped_id = _escape_css_attr(panel_id)
        trigger_selectors.extend([
            f'[aria-controls="{escaped_id}"]',
            f'[data-target="#{escaped_id}"]',
            f'[data-bs-target="#{escaped_id}"]',
        ])

        if panel_id.endswith("-panel"):
            trigger_id = _escape_css_attr(f"{panel_id[:-len('-panel')]}-trigger")
            trigger_selectors.append(f'[id="{trigger_id}"]')

    return list(dict.fromkeys(trigger_selectors))


def _reveal_hidden_action_target(page, selector: str, locator):
    if _is_visible(locator):
        return locator

    target_handle = _element_handle(locator)
    panel_ids = _panel_ids_from_target(selector, target_handle)
    for trigger_selector in _panel_trigger_selectors(panel_ids):
        try:
            trigger = _pick_visible(page.locator(trigger_selector))
            if not _is_visible(trigger):
                continue

            for action_name in ("hover", "click"):
                getattr(trigger, action_name)(timeout=2000)
                page.wait_for_timeout(250)
                refreshed = _resolve_action_locator(page, selector)
                if _is_visible(refreshed):
                    logger.info(
                        "Revealed hidden action target using %s on trigger %s",
                        action_name,
                        trigger_selector,
                    )
                    return refreshed
                if _is_handle_visible(target_handle):
                    logger.info(
                        "Revealed hidden action target handle using %s on trigger %s",
                        action_name,
                        trigger_selector,
                    )
                    return target_handle
        except Exception:
            continue

    return locator


def _resolve_interactive_locator(page, selector: str):
    locator = _resolve_action_locator(page, selector)
    return _reveal_hidden_action_target(page, selector, locator)


def _settle_after_click(page, previous_url: str) -> None:
    try:
        page.wait_for_timeout(POST_CLICK_SETTLE_MS)
    except Exception:
        pass

    try:
        url_changed = page.url != previous_url
    except Exception:
        url_changed = False

    if not url_changed:
        return

    try:
        page.wait_for_load_state("domcontentloaded", timeout=POST_CLICK_NAVIGATION_TIMEOUT_MS)
    except Exception:
        pass


def _resolve_step_value(value):
    if not isinstance(value, str):
        return value

    match = SECRET_VALUE_PATTERN.match(value.strip())
    if not match:
        return value

    env_key = "TEST_SECRET_" + re.sub(r"[^A-Za-z0-9]+", "_", match.group(1)).upper()
    secret_value = os.getenv(env_key)
    if secret_value is None:
        raise ValueError(
            f"Secret value '{value}' requires backend environment variable {env_key}"
        )
    return secret_value


def _try_self_heal(page, step: dict) -> bool:
    """
    Self-healing fallback: if the primary selector fails,
    try alternative strategies to find the element.
    Returns True if element was found and action succeeded.
    """
    value = step.get("value", "")
    action = step.get("action", "")

    strategies = []

    # Strategy 1: Try by text content for commands that expose visible text.
    if value and action == "click":
        strategies.append(("text", f"text={value}"))

    # Strategy 2: Try by role for buttons with known visible text.
    selector = step.get("selector", "")
    if "button" in selector.lower() or action == "click":
        if value:
            strategies.append(("role-button", f"role=button[name='{value}']"))

    for strategy_name, alt_selector in strategies:
        try:
            if action == "click":
                locator = _pick_click_target(page.locator(alt_selector))
            else:
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
            page.set_default_timeout(ACTION_TIMEOUT_MS)

            for step in test_case_steps:
                step_index = step.get("step_index", 0)
                action = step.get("action", "")
                selector = step.get("selector", "")
                value = step.get("value", "")
                step_start = time.time()
                logger.info("Executing step %s: %s %s", step_index, action, selector or "")

                try:
                    _dismiss_overlays(page)
                    if action == "navigate":
                        url = value
                        if base_url and not url.startswith("http"):
                            url = base_url.rstrip("/") + "/" + url.lstrip("/")
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)

                    elif action == "click":
                        previous_url = page.url
                        locator = _resolve_click_locator(page, selector)
                        try:
                            locator.scroll_into_view_if_needed(timeout=2000)
                        except Exception:
                            pass
                        clicked = False
                        try:
                            locator.click(timeout=5000)
                            clicked = True
                        except (PlaywrightTimeout, Exception):
                            if _dismiss_overlays(page):
                                try:
                                    locator = _resolve_click_locator(page, selector)
                                    locator.click(timeout=5000)
                                    clicked = True
                                except (PlaywrightTimeout, Exception):
                                    pass
                            if not clicked and _has_match(locator):
                                try:
                                    locator.click(timeout=5000, force=True)
                                    clicked = True
                                except (PlaywrightTimeout, Exception):
                                    pass
                            if not clicked:
                                if not _try_self_heal(page, step):
                                    raise
                                clicked = True
                        if clicked:
                            _settle_after_click(page, previous_url)

                    elif action == "hover":
                        locator = _resolve_interactive_locator(page, selector)
                        locator.hover(timeout=5000)
                        page.wait_for_timeout(POST_CLICK_SETTLE_MS)

                    elif action == "fill":
                        fill_value = _resolve_step_value(value)
                        locator = _resolve_interactive_locator(page, selector)
                        try:
                            locator.scroll_into_view_if_needed(timeout=2000)
                        except Exception:
                            pass
                        filled = False
                        try:
                            locator.fill(fill_value, timeout=5000)
                            filled = True
                        except (PlaywrightTimeout, Exception):
                            if _dismiss_overlays(page):
                                try:
                                    locator = _resolve_interactive_locator(page, selector)
                                    locator.fill(fill_value, timeout=5000)
                                    filled = True
                                except (PlaywrightTimeout, Exception):
                                    pass
                            if not filled and _has_match(locator):
                                try:
                                    locator.fill(fill_value, timeout=5000, force=True)
                                    filled = True
                                except (PlaywrightTimeout, Exception):
                                    pass
                            if not filled and not _try_self_heal(page, step):
                                raise

                    elif action == "select":
                        select_value = _resolve_step_value(value)
                        locator = _resolve_interactive_locator(page, selector)
                        locator.select_option(select_value, timeout=5000)

                    elif action == "assert_text":
                        locator = _resolve_action_locator(page, selector)
                        if isinstance(value, str):
                            expect(locator).to_have_text(value, timeout=5000)
                        elif isinstance(selector, str) and selector.strip().startswith("text="):
                            expect(locator).to_be_visible(timeout=5000)
                        else:
                            raise ValueError(
                                "assert_text step requires a string value or a text= selector"
                            )

                    elif action == "assert_visible":
                        locator = _resolve_action_locator(page, selector)
                        expect(locator).to_be_visible(timeout=5000)

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
                    logger.info("Step %s passed in %.2fms", step_index, step_duration)

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
                    logger.warning("Step %s failed after %.2fms: %s", step_index, step_duration, e)
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
