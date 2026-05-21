"""
Analyser — GPT-4o application understanding + test case generation.
Two sequential API calls:
  1. Understand the recorded session (multimodal with screenshots)
  2. Generate test cases from the understanding
"""

import json
import os
import logging
from typing import List, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_STEPS = int(os.getenv("AI_MAX_STEPS", "10"))
MAX_FIELD_CHARS = int(os.getenv("AI_FIELD_CHAR_LIMIT", "200"))
MAX_NETWORK_CALLS_PER_STEP = int(os.getenv("AI_MAX_NETWORK_CALLS_PER_STEP", "3"))


def _trim_text(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _compact_network_calls(network_calls: List[dict]) -> List[dict]:
    compact = []
    for nc in network_calls[:MAX_NETWORK_CALLS_PER_STEP]:
        if not isinstance(nc, dict):
            continue
        compact.append({
            "method": nc.get("method"),
            "url": _trim_text(nc.get("url"), MAX_FIELD_CHARS),
            "status": nc.get("status"),
        })
    return compact


def _compact_steps(steps: List[dict]) -> List[dict]:
    compact_steps = []
    for step in steps[:MAX_STEPS]:
        compact_steps.append({
            "step_index": step.get("step_index"),
            "action": step.get("action"),
            "url": _trim_text(step.get("url"), MAX_FIELD_CHARS),
            "selector": _trim_text(step.get("selector"), MAX_FIELD_CHARS),
            "value": _trim_text(step.get("value"), MAX_FIELD_CHARS),
            "network_calls": _compact_network_calls(step.get("network_calls", [])),
        })
    return compact_steps


def understand_session(session_detail: dict) -> dict:
    """
    Call 1 — Send session data (including screenshots) to GPT-4o
    and get a structured understanding of the application and user flow.
    """
    # Build the message content with text + screenshots
    content_parts = []

    # Collect screenshots from steps
    screenshots_added = 0
    for step in session_detail.get("steps", []):
        if step.get("screenshot_b64") and screenshots_added < 5:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{step['screenshot_b64']}"
                }
            })
            screenshots_added += 1

    # Build a text summary of the steps
    steps_summary = []
    for step in session_detail.get("steps", []):
        step_desc = f"Step {step['step_index']}: {step['action']}"
        if step.get("selector"):
            step_desc += f" on '{step['selector']}'"
        if step.get("value"):
            step_desc += f" with value '{step['value']}'"
        if step.get("url"):
            step_desc += f" (URL: {step['url']})"
        steps_summary.append(step_desc)

    # Collect network call info
    network_summary = []
    for step in session_detail.get("steps", []):
        for nc in step.get("network_calls", []):
            if isinstance(nc, dict):
                method = nc.get("method", "?")
                url = nc.get("url", "?")
                status = nc.get("status", "?")
                network_summary.append(f"{method} {url} → {status}")

    prompt = f"""You are a senior QA engineer. Analyse this recorded user session on a web application.

Session URL: {session_detail.get('url', 'unknown')}

User Actions Recorded:
{chr(10).join(steps_summary)}

Network Calls Observed:
{chr(10).join(network_summary[:20]) if network_summary else 'None captured'}

Identify:
1. What type of application this is (e-commerce, CRM, HR tool, etc.)
2. What the user was doing — describe the flow step by step
3. All form fields and their likely validation rules
4. All API endpoints called and their purpose
5. What constitutes success and failure for this flow

Return as structured JSON with keys: app_type, flow_description, form_fields, api_endpoints, success_criteria, failure_criteria"""

    content_parts.append({"type": "text", "text": prompt})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            max_tokens=4096,
            messages=[{"role": "user", "content": content_parts}],
        )
        understanding = json.loads(response.choices[0].message.content)
        logger.info("Session understanding completed successfully")
        return understanding
    except Exception as e:
        logger.error(f"Understanding failed: {e}")
        return {
            "error": str(e),
            "app_type": "unknown",
            "flow_description": "Analysis failed",
            "form_fields": [],
            "api_endpoints": [],
            "success_criteria": "unknown",
            "failure_criteria": "unknown",
        }


def generate_test_cases(understanding: dict, session_detail: dict) -> List[dict]:
    """
    Call 2 — Generate test cases from the application understanding.
    Returns a list of test case dicts ready to save to the DB.
    """
    compact_steps = _compact_steps(session_detail.get("steps", []))
    steps_json = json.dumps(compact_steps, indent=2)

    prompt = f"""Based on this application understanding:
{json.dumps(understanding, indent=2)}

And the original recorded session steps:
{steps_json}

Generate comprehensive test cases. For EACH test case, provide:
- title: descriptive test case name
- type: one of "happy", "negative", "edge", "security"
- steps: array of Playwright-compatible actions. Each step must have:
    - step_index: sequential number starting at 1
    - action: one of "navigate", "click", "fill", "assert_text", "assert_visible", "select", "wait"
    - selector: CSS selector or Playwright selector (e.g., "#username", "text=Login", "[data-testid='submit']")
    - value: the value to use (URL for navigate, text for fill, expected text for assert_text, or null)
- expected_result: what should happen when the test passes
- reason: why this test matters for quality assurance

Generate at least 8 test cases covering:
- 2-3 happy path cases (normal successful flows)
- 2-3 negative cases (invalid inputs, missing fields)
- 1-2 edge cases (boundary values, special characters)
- 1-2 security cases (XSS, SQL injection attempts)

Return as a JSON object with a single key "test_cases" containing the array."""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(response.choices[0].message.content)
        test_cases = result.get("test_cases", [])
        logger.info(f"Generated {len(test_cases)} test cases")
        return test_cases
    except Exception as e:
        logger.error(f"Test case generation failed: {e}")
        return []


def analyse_session(session_detail: dict) -> dict:
    """
    Full analysis pipeline: understand the session, then generate test cases.
    Returns dict with 'understanding' and 'test_cases' keys.
    """
    understanding = understand_session(session_detail)
    test_cases = generate_test_cases(understanding, session_detail)
    return {
        "understanding": understanding,
        "test_cases": test_cases,
    }
