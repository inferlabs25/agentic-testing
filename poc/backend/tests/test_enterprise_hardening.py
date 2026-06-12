import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from failure_intelligence import classify_failure
from redaction import redact_data, redact_event_payload, redact_url
from test_readiness import auto_repair_test_case, prepare_generated_test_case
from executor import _resolve_step_value


class EnterpriseHardeningTests(unittest.TestCase):
    def test_redacts_sensitive_url_values(self):
        url = redact_url("https://example.test/login?token=abc&next=/home")

        self.assertIn("token=%5BREDACTED%5D", url)
        self.assertIn("next=%2Fhome", url)

    def test_redacts_nested_sensitive_data(self):
        clean = redact_data({"headers": {"Authorization": "Bearer abc"}, "password": "secret"})

        self.assertEqual(clean["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(clean["password"], "[REDACTED]")

    def test_event_redaction_masks_network_url(self):
        event = {
            "event_type": "network",
            "timestamp": 1.0,
            "url": "https://example.test?api_key=secret",
            "selector": None,
            "value": None,
            "dom_snapshot": None,
            "screenshot_b64": None,
            "network_data": {"url": "https://api.test?access_token=abc"},
            "meta": None,
        }

        clean = redact_event_payload(event)

        self.assertIn("%5BREDACTED%5D", clean["url"])
        self.assertIn("%5BREDACTED%5D", clean["network_data"]["url"])

    def test_ready_generated_test_case(self):
        session = {
            "session_id": "s1",
            "url": "https://example.test/login",
            "steps": [{
                "action": "click",
                "selector": "#submit",
                "value": "Submit",
                "meta": {"selectors": ["#submit"]},
                "dom_snapshot": '<button id="submit">Submit</button>',
            }],
        }
        generated = {
            "title": "Submit",
            "type": "happy",
            "steps": [{"action": "click", "selector": "#submit", "value": "Submit"}],
        }

        prepared = prepare_generated_test_case(generated, session)

        self.assertEqual(prepared["readiness_status"], "ready_to_run")
        self.assertEqual(prepared["status"], "draft")
        self.assertEqual(prepared["steps"][0]["action"], "navigate")

    def test_suggested_generated_test_case_for_invented_selector(self):
        session = {"session_id": "s1", "steps": []}
        generated = {
            "title": "Invented field",
            "type": "security",
            "steps": [{"action": "fill", "selector": "#made-up", "value": "' OR 1=1"}],
        }

        prepared = prepare_generated_test_case(generated, session)

        self.assertEqual(prepared["readiness_status"], "suggested_review")
        self.assertEqual(prepared["status"], "suggested_review")

    def test_suggested_generated_test_case_for_unobserved_assertion(self):
        session = {
            "session_id": "s1",
            "steps": [{
                "action": "click",
                "selector": "#submit",
                "value": "Submit",
                "url": "https://example.test/login",
                "meta": {"selectors": ["#submit"], "text": "Submit"},
                "dom_snapshot": '<button id="submit">Submit</button>',
            }],
        }
        generated = {
            "title": "Wrong message",
            "type": "negative",
            "steps": [{"action": "assert_text", "selector": "text=Invalid credentials", "value": "Invalid credentials"}],
        }

        prepared = prepare_generated_test_case(generated, session)

        self.assertEqual(prepared["readiness_status"], "suggested_review")
        self.assertIn("not observed", prepared["readiness_reason"])

    def test_auto_repair_removes_unobserved_assertion_and_makes_smoke_ready(self):
        session = {
            "session_id": "s1",
            "steps": [{
                "action": "click",
                "selector": "#submit",
                "value": "Submit",
                "url": "https://example.test/login",
                "meta": {"selectors": ["#submit"], "text": "Submit"},
                "dom_snapshot": '<button id="submit">Submit</button>',
            }],
        }
        generated = {
            "title": "Invalid login",
            "type": "negative",
            "steps": [
                {"action": "click", "selector": "#submit", "value": "Submit"},
                {
                    "action": "assert_text",
                    "selector": "text=Invalid credentials",
                    "value": "Invalid credentials",
                },
            ],
        }

        repaired = auto_repair_test_case(generated, session)

        self.assertEqual(repaired["readiness_status"], "ready_to_run")
        self.assertNotIn("assert_text", [step["action"] for step in repaired["steps"]])
        self.assertIn("Executable smoke validation", repaired["expected_result"])

    def test_auto_repair_keeps_review_when_no_executable_evidence_remains(self):
        session = {
            "session_id": "s1",
            "steps": [{
                "action": "navigate",
                "url": "https://example.test/login",
                "dom_snapshot": "<main>Login</main>",
            }],
        }
        generated = {
            "title": "Broken selector",
            "type": "happy",
            "steps": [{"action": "click", "selector": "#root > div:n...", "value": "Open"}],
        }

        repaired = auto_repair_test_case(generated, session)

        self.assertEqual(repaired["readiness_status"], "suggested_review")
        self.assertIn("removed all executable steps", repaired["readiness_reason"].lower())

    def test_css_assertion_without_recorded_evidence_is_suggested_review(self):
        session = {
            "session_id": "s1",
            "steps": [{
                "action": "navigate",
                "url": "https://example.test/dashboard",
                "dom_snapshot": '<div id="root"><main>Welcome back</main></div>',
            }],
        }
        generated = {
            "title": "Dashboard",
            "type": "happy",
            "steps": [{
                "action": "assert_visible",
                "selector": "#root > div[data-testid='dashboard']",
            }],
        }

        prepared = prepare_generated_test_case(generated, session)

        self.assertEqual(prepared["readiness_status"], "suggested_review")
        self.assertIn("not captured", prepared["readiness_reason"])

    def test_auto_repair_replaces_dashboard_assertion_with_recorded_text(self):
        session = {
            "session_id": "s1",
            "steps": [{
                "action": "navigate",
                "url": "https://example.test/dashboard",
                "dom_snapshot": '<div id="root"><nav>Dashboard</nav><main>Welcome back, Ramesh</main></div>',
            }],
        }
        generated = {
            "title": "Dashboard",
            "type": "happy",
            "steps": [{
                "action": "assert_visible",
                "selector": "#root > div[data-testid='dashboard']",
            }],
        }

        repaired = auto_repair_test_case(generated, session)

        self.assertEqual(repaired["readiness_status"], "ready_to_run")
        self.assertEqual(repaired["steps"][-1]["selector"], "text=Dashboard")

    def test_authenticated_feature_test_gets_login_prerequisite(self):
        session = {
            "session_id": "s1",
            "steps": [
                {
                    "step_index": 1,
                    "action": "navigate",
                    "url": "https://example.test/login?returnTo=/knowledge",
                },
                {
                    "step_index": 2,
                    "action": "fill",
                    "selector": "#identifier",
                    "value": "user@example.test",
                    "meta": {"selectors": ["#identifier"], "label": "Email"},
                    "dom_snapshot": '<input id="identifier" name="identifier">',
                },
                {
                    "step_index": 3,
                    "action": "fill",
                    "selector": "#password",
                    "value": "{{secret:password}}",
                    "meta": {"selectors": ["#password"], "label": "Password"},
                    "dom_snapshot": '<input id="password" name="password">',
                },
                {
                    "step_index": 4,
                    "action": "click",
                    "selector": "#sign-in",
                    "value": "Sign In",
                    "meta": {"selectors": ["#sign-in"], "text": "Sign In"},
                    "dom_snapshot": '<button id="sign-in">Sign In</button>',
                },
                {
                    "step_index": 5,
                    "action": "navigate",
                    "url": "https://example.test/knowledge",
                    "dom_snapshot": '<main><p class="article">Financial planning</p></main>',
                },
                {
                    "step_index": 6,
                    "action": "click",
                    "selector": ".article",
                    "value": "Financial planning",
                    "meta": {"selectors": [".article"], "text": "Financial planning"},
                    "dom_snapshot": '<main><p class="article">Financial planning</p></main>',
                },
            ],
        }
        generated = {
            "title": "Open article",
            "type": "happy",
            "steps": [
                {"action": "navigate", "value": "https://example.test/knowledge"},
                {"action": "click", "selector": ".article", "value": None},
            ],
        }

        prepared = prepare_generated_test_case(generated, session)
    
        self.assertEqual(prepared["readiness_status"], "ready_to_run")
        self.assertEqual(
            [step["action"] for step in prepared["steps"][:4]],
            ["navigate", "wait", "fill", "fill"],
        )
        self.assertEqual(prepared["steps"][0]["value"], "https://example.test/login?returnTo=/knowledge")
        self.assertEqual(prepared["steps"][3]["value"], "{{secret:password}}")
        self.assertEqual(prepared["steps"][8]["value"], "Financial planning")

    def test_login_test_is_not_prefixed_with_duplicate_login(self):
        session = {
            "session_id": "s1",
            "steps": [
                {"step_index": 1, "action": "navigate", "url": "https://example.test/login"},
                {
                    "step_index": 2,
                    "action": "fill",
                    "selector": "#identifier",
                    "value": "user@example.test",
                    "meta": {"label": "Email", "selectors": ["#identifier"]},
                    "dom_snapshot": '<input id="identifier">',
                },
                {
                    "step_index": 3,
                    "action": "fill",
                    "selector": "#password",
                    "value": "{{secret:password}}",
                    "meta": {"label": "Password", "selectors": ["#password"]},
                    "dom_snapshot": '<input id="password">',
                },
                {
                    "step_index": 4,
                    "action": "click",
                    "selector": "#sign-in",
                    "value": "Sign In",
                    "meta": {"text": "Sign In", "selectors": ["#sign-in"]},
                    "dom_snapshot": '<button id="sign-in">Sign In</button>',
                },
                {"step_index": 5, "action": "navigate", "url": "https://example.test/dashboard"},
            ],
        }
        generated = {
            "title": "Login",
            "type": "happy",
            "steps": [
                {"action": "navigate", "value": "https://example.test/login"},
                {"action": "fill", "selector": "#identifier", "value": "user@example.test"},
                {"action": "fill", "selector": "#password", "value": "{{secret:password}}"},
            ],
        }
    
        prepared = prepare_generated_test_case(generated, session)
    
        self.assertEqual(
            [step["action"] for step in prepared["steps"]],
            ["navigate", "wait", "fill", "fill"],
        )

    def test_truncated_selector_is_suggested_review(self):
        session = {"session_id": "s1", "steps": [{"url": "https://example.test"}]}
        generated = {
            "title": "Truncated selector",
            "type": "happy",
            "steps": [{"action": "click", "selector": "#root > div:n...", "value": "Open"}],
        }

        prepared = prepare_generated_test_case(generated, session)

        self.assertEqual(prepared["readiness_status"], "suggested_review")

    def test_single_brace_secret_placeholder_resolves(self):
        import os
        old = os.environ.get("TEST_SECRET_PASSWORD")
        os.environ["TEST_SECRET_PASSWORD"] = "secret-value"
        try:
            self.assertEqual(_resolve_step_value("{secret:password}"), "secret-value")
        finally:
            if old is None:
                os.environ.pop("TEST_SECRET_PASSWORD", None)
            else:
                os.environ["TEST_SECRET_PASSWORD"] = old

    def test_failure_classifier_detects_selector_issue(self):
        classified = classify_failure(
            {"action": "click", "selector": "#missing", "error": "Locator resolved to no element"}
        )

        self.assertEqual(classified["category"], "selector_issue")

    def test_detect_missing_auth_from_context(self):
        session = {
            "session_id": "s1",
            "auth_context": {
                "requires_auth": True,
                "start_state": "authenticated",
                "start_url": "https://example.test/knowledge"
            },
            "steps": [
                {"step_index": 1, "action": "navigate", "url": "https://example.test/knowledge"},
                {"step_index": 2, "action": "click", "selector": ".article", "value": "Financial planning"}
            ]
        }
        generated = {
            "title": "Open article without auth",
            "type": "happy",
            "steps": [
                {"action": "navigate", "value": "https://example.test/knowledge"},
                {"action": "click", "selector": ".article", "value": None}
            ]
        }
        prepared = prepare_generated_test_case(generated, session)
        self.assertEqual(prepared["readiness_status"], "suggested_review")
        self.assertTrue(any("missing_auth_precondition" in issue["error"] for issue in prepared["evidence_source"]["validation_issues"]))

    def test_reconstruct_navigation_path(self):
        session = {
            "session_id": "s1",
            "steps": [
                {"step_index": 1, "action": "navigate", "url": "https://example.test/dashboard"},
                {"step_index": 2, "action": "click", "selector": "#menu-button", "value": "Menu"},
                {"step_index": 3, "action": "click", "selector": "#submenu-kb", "value": "Knowledge Base"},
                {"step_index": 4, "action": "click", "selector": ".article", "value": "Financial planning"}
            ]
        }
        generated = {
            "title": "Quick open article",
            "type": "happy",
            "steps": [
                {"action": "click", "selector": ".article", "value": None}
            ]
        }
        prepared = prepare_generated_test_case(generated, session)
        actions = [step["action"] for step in prepared["steps"]]
        non_wait_actions = [a for a in actions if a != "wait"]
        self.assertEqual(non_wait_actions, ["navigate", "click", "click", "click"])
        self.assertEqual(prepared["steps"][0]["action"], "navigate")
        self.assertEqual(prepared["steps"][0]["value"], "https://example.test/dashboard")

    def test_failure_classifier_detects_flow_construction_issue(self):
        failed_step = {
            "step_index": 2,
            "action": "click",
            "selector": ".article",
            "error": "Locator.click: Timeout 30000ms exceeded. selector resolved to no element"
        }
        test_steps = [
            {"step_index": 1, "action": "navigate", "value": "https://example.test/knowledge"},
            {"step_index": 2, "action": "click", "selector": ".article", "value": None}
        ]
        classified = classify_failure(failed_step, test_steps=test_steps)
        self.assertEqual(classified["category"], "flow_construction_issue")
        self.assertIn("Regenerate the test with login and module navigation", classified["recommended_fix"])


if __name__ == "__main__":
    unittest.main()
