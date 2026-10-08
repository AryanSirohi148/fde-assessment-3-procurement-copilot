"""
Unit tests for Procurement Copilot Solution
Tests:
  - Architecture A (Single-agent) and Architecture B (Staged)
  - Policy engine rules (financial tiers, security, privacy, legal triggers)
  - Budget calculations
  - Catalog overlap detection
  - Vendor risk handling (including 503 outage degradation)
  - Prompt injection detection
"""
from __future__ import annotations

import unittest
from src.solution import handle_request
from src.contracts import ProcurementDecision
from src.tools.policy_engine import (
    check_approval_tiers,
    check_required_fields,
    check_prompt_injection,
    check_security_triggers,
    check_privacy_triggers,
    check_legal_triggers,
)
from src.tools.budget_tool import check_budget
from src.tools.catalog_tool import check_catalog_overlap
from src.tools.vendor_risk_tool import check_vendor_risk


class TestSolutionAndTools(unittest.TestCase):

    def test_single_architecture_basic_request(self):
        decision = handle_request("REQ-1001", architecture="single")
        self.assertIsInstance(decision, ProcurementDecision)
        self.assertEqual(decision.request_id, "REQ-1001")
        self.assertTrue(decision.human_review_required)
        self.assertIn("Manager", decision.required_approvals)
        self.assertNotIn("budget_insufficient", decision.risk_flags)
        self.assertNotIn("vendor_risk_unavailable", decision.risk_flags)
        self.assertGreaterEqual(len(decision.evidence), 2)

    def test_staged_architecture_basic_request(self):
        decision = handle_request("REQ-1001", architecture="staged")
        self.assertIsInstance(decision, ProcurementDecision)
        self.assertEqual(decision.request_id, "REQ-1001")
        self.assertTrue(decision.human_review_required)
        self.assertIn("Manager", decision.required_approvals)
        self.assertIsNotNone(decision.telemetry)
        self.assertEqual(decision.telemetry.llm_calls, 2)

    def test_catalog_overlap_and_legal_trigger(self):
        decision = handle_request("REQ-1002", architecture="single")
        self.assertTrue(any("overlap" in f.lower() for f in decision.risk_flags))
        self.assertTrue(any("security" in f.lower() for f in decision.risk_flags))
        self.assertTrue(any("legal" in f.lower() for f in decision.risk_flags))
        self.assertTrue(any("security" in a.lower() for a in decision.required_approvals))
        self.assertTrue(any("legal" in a.lower() for a in decision.required_approvals))

    def test_budget_shortfall(self):
        decision = handle_request("REQ-1005", architecture="single")
        self.assertTrue(any("budget" in f.lower() for f in decision.risk_flags))
        self.assertTrue(any("finance" in a.lower() for a in decision.required_approvals))

    def test_prompt_injection_and_missing_info(self):
        decision = handle_request("REQ-1006", architecture="single")
        self.assertTrue(any("prompt_injection" in f.lower() for f in decision.risk_flags))
        self.assertTrue(any("missing" in f.lower() for f in decision.risk_flags))
        self.assertGreater(len(decision.missing_information), 0)

    def test_vendor_risk_outage_graceful_degradation(self):
        decision = handle_request("REQ-1009", architecture="single")
        self.assertTrue(any("unavailable" in f.lower() for f in decision.risk_flags))
        self.assertTrue(any("security" in f.lower() for f in decision.risk_flags))
        self.assertTrue(decision.human_review_required)

    def test_financial_approval_tiers(self):
        # <= $1,000 -> Manager
        self.assertEqual(check_approval_tiers(800)["required_approvals"], ["Manager"])
        # $1,000.01 - $10,000 -> Dept Head + Procurement
        self.assertEqual(
            check_approval_tiers(5000)["required_approvals"],
            ["Department Head", "Procurement"],
        )
        # $10,000.01 - $25,000 -> Dept Head + Finance + Procurement
        self.assertEqual(
            check_approval_tiers(15000)["required_approvals"],
            ["Department Head", "Finance", "Procurement"],
        )
        # > $25,000 -> Dept Head + Finance + CFO + Procurement
        self.assertEqual(
            check_approval_tiers(30000)["required_approvals"],
            ["Department Head", "Finance", "CFO", "Procurement"],
        )


if __name__ == "__main__":
    unittest.main()
