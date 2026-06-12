"""
Reasoning — GPT-4o failure root cause analysis.
Receives a failed test step with screenshot and produces
a plain-language explanation of why it failed.
"""

import json
import os
import logging
from typing import Optional, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
REASONING_TIMEOUT_SECONDS = float(os.getenv("AI_REASONING_TIMEOUT_SECONDS", "20"))
REASONING_MAX_RETRIES = int(os.getenv("AI_REASONING_MAX_RETRIES", "0"))

def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for AI failure reasoning")
    return OpenAI(
        api_key=api_key,
        timeout=REASONING_TIMEOUT_SECONDS,
        max_retries=REASONING_MAX_RETRIES,
    )


def _known_execution_failure(failed_step: dict) -> Optional[str]:
    action = failed_step.get("action", "")
    error = str(failed_step.get("error", ""))
    if action == "assert_text" and "value must be a string or regular expression" in error:
        return (
            "The generated assert_text step is malformed: Playwright needs the expected "
            "text in the step value, but this assertion passed a null or non-string value. "
            "Use a string value for assert_text, or use assert_visible when the text is "
            "already encoded in a text= selector."
        )
    return None


def _detect_flow_issue(failed_step: dict, test_steps: Optional[List[dict]]) -> Optional[str]:
    if not test_steps:
        return None
        
    failed_idx = failed_step.get("step_index")
    if failed_idx is None:
        return None
        
    failed_pos = -1
    for pos, step in enumerate(test_steps):
        if step.get("step_index") == failed_idx:
            failed_pos = pos
            break
            
    if failed_pos == -1:
        return None
        
    meaningful_before = [
        s for s in test_steps[:failed_pos]
        if s.get("action") in {"click", "fill", "select", "hover", "assert_text", "assert_visible"}
    ]
    
    has_login = False
    for step in test_steps[:failed_pos]:
        val = str(step.get("value") or "").lower()
        sel = str(step.get("selector") or "").lower()
        action = str(step.get("action") or "").lower()
        if action == "navigate" and any(t in val for t in ("login", "signin", "auth")):
            has_login = True
        if action == "fill" and "password" in sel:
            has_login = True
            
    error = str(failed_step.get("error") or "").lower()
    if len(meaningful_before) <= 1 and not has_login:
        is_selector_err = any(token in error for token in ("selector", "locator", "strict mode", "element", "timeout"))
        if is_selector_err:
            return (
                f"Flow Construction Issue: The test case attempted to interact with the element '{failed_step.get('selector')}' "
                f"without performing the required authentication flow first. The execution timed out because the application "
                f"was not logged in, making the protected page's element unavailable."
            )
            
    return None


def analyse_failure(
    test_title: str,
    expected_result: str,
    failed_step: dict,
    screenshot_b64: Optional[str] = None,
    network_logs: Optional[List[dict]] = None,
    test_steps: Optional[List[dict]] = None,
) -> str:
    """
    Send failure context + screenshot to GPT-4o and get a
    specific, actionable root cause explanation.
    """
    flow_issue = _detect_flow_issue(failed_step, test_steps)
    if flow_issue:
        return flow_issue

    known_failure = _known_execution_failure(failed_step)
    if known_failure:
        return known_failure

    content_parts = []

    # Include screenshot if available (multimodal)
    if screenshot_b64:
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{screenshot_b64}"
            }
        })

    # Build the analysis prompt
    network_text = "None available"
    if network_logs:
        net_entries = []
        for nc in network_logs[:10]:
            if isinstance(nc, dict):
                method = nc.get("method", "?")
                url = nc.get("url", "?")
                status = nc.get("status", "?")
                net_entries.append(f"  {method} {url} → {status}")
        network_text = "\n".join(net_entries) if net_entries else "None available"

    steps_text = "None provided"
    if test_steps:
        steps_entries = []
        for s in test_steps:
            arrow = "--> " if s.get("step_index") == failed_step.get("step_index") else "    "
            steps_entries.append(f"{arrow}Step {s.get('step_index')}: {s.get('action')} on selector '{s.get('selector')}' with value '{s.get('value')}'")
        steps_text = "\n".join(steps_entries)

    prompt = f"""A test case failed during automated execution. Analyse the failure and explain the root cause.

Test Case: {test_title}
Expected Result: {expected_result}

Test Steps Context:
{steps_text}

Failed Step Details:
  - Step Index: {failed_step.get('step_index', '?')}
  - Action: {failed_step.get('action', '?')}
  - Selector: {failed_step.get('selector', '?')}
  - Error Message: {failed_step.get('error', 'No error message')}

Network Calls Around Failure:
{network_text}

Instructions:
- IMPORTANT: Before attributing the failure to a selector issue, check if the test includes login/authentication steps or navigates to the correct module/page before the failed action.
- If the test jumps directly to an internal page action without login/setup, classify this as a FLOW CONSTRUCTION ISSUE, not a selector issue. A selector timeout on a protected page without preceding login steps means the test is incomplete.
- In 2-3 sentences, explain EXACTLY why the test failed.
- Be specific — mention field names, selector values, expected vs actual behavior, and HTTP status codes if relevant.
- Do NOT be generic. Do NOT say "the test failed because of an error."
- If you can see the screenshot, reference what's visible on the page.
- Suggest the most likely fix."""

    content_parts.append({"type": "text", "text": prompt})

    try:
        response = _client().chat.completions.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": content_parts}],
        )
        reasoning = response.choices[0].message.content.strip()
        logger.info("Failure analysis completed")
        return reasoning
    except Exception as e:
        logger.error(f"Reasoning analysis failed: {e}")
        return f"AI analysis unavailable: {str(e)}"
