import sys
import unittest
from unittest.mock import patch
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from analyser import _normalise_generated_test_cases
from executor import _resolve_step_value
from step_validation import validate_steps_against_session


class GeneratedStepTests(unittest.TestCase):
    def test_text_click_reuses_unique_recorded_selector(self):
        session = {
            "steps": [{
                "action": "click",
                "selector": "#submit",
                "value": "Sign In",
                "meta": {"accessibleName": "Sign In"},
            }]
        }
        tests = [{"steps": [{"action": "click", "selector": "text=Sign In", "value": None}]}]

        normalised = _normalise_generated_test_cases(tests, session)

        self.assertEqual(normalised[0]["steps"][0]["selector"], "#submit")

    def test_unknown_fill_selector_is_rejected(self):
        session = {
            "steps": [{
                "action": "fill",
                "selector": "#email",
                "value": "user@example.test",
                "meta": {"selectors": ["#email"]},
                "dom_snapshot": '<input id="email">',
            }]
        }
        steps = [{"step_index": 1, "action": "fill", "selector": "#invented", "value": "x"}]

        issues = validate_steps_against_session(steps, session)

        self.assertEqual(issues[0]["step_index"], 1)
        self.assertIn("#invented", issues[0]["error"])

    def test_recorded_selector_passes_preflight(self):
        session = {
            "steps": [{
                "action": "fill",
                "selector": "#email",
                "value": "user@example.test",
                "meta": {"selectors": ["#email"]},
                "dom_snapshot": '<input id="email">',
            }]
        }
        steps = [{"step_index": 1, "action": "fill", "selector": "#email", "value": "x"}]

        self.assertEqual(validate_steps_against_session(steps, session), [])

    def test_secret_placeholder_uses_backend_environment(self):
        with patch.dict("os.environ", {"TEST_SECRET_PASSWORD": "s3cret"}, clear=False):
            self.assertEqual(_resolve_step_value("{{secret:password}}"), "s3cret")

    def test_secret_placeholder_requires_backend_environment(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "TEST_SECRET_PASSWORD"):
                _resolve_step_value("{{secret:password}}")


if __name__ == "__main__":
    unittest.main()
