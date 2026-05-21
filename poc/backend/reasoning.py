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

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
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


def analyse_failure(
    test_title: str,
    expected_result: str,
    failed_step: dict,
    screenshot_b64: Optional[str] = None,
    network_logs: Optional[List[dict]] = None,
) -> str:
    """
    Send failure context + screenshot to GPT-4o and get a
    specific, actionable root cause explanation.

    Args:
        test_title: name of the test case
        expected_result: what was supposed to happen
        failed_step: dict with step_index, action, selector, error
        screenshot_b64: base64-encoded PNG of the page at failure time
        network_logs: list of network call dicts around the failure

    Returns:
        Plain-language root cause string (2-3 sentences).
    """
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

    prompt = f"""A test case failed during automated execution. Analyse the failure and explain the root cause.

Test Case: {test_title}
Expected Result: {expected_result}

Failed Step Details:
  - Step Index: {failed_step.get('step_index', '?')}
  - Action: {failed_step.get('action', '?')}
  - Selector: {failed_step.get('selector', '?')}
  - Error Message: {failed_step.get('error', 'No error message')}

Network Calls Around Failure:
{network_text}

Instructions:
- In 2-3 sentences, explain EXACTLY why the test failed.
- Be specific — mention field names, selector values, expected vs actual behavior, and HTTP status codes if relevant.
- Do NOT be generic. Do NOT say "the test failed because of an error."
- If you can see the screenshot, reference what's visible on the page.
- Suggest the most likely fix."""

    content_parts.append({"type": "text", "text": prompt})

    try:
        response = client.chat.completions.create(
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
