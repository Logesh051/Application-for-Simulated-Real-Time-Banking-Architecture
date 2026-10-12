"""
Unit tests for the Three Specialized Agents (Milestone 2).

Covers:
- Banking Agent balance and statement retrieval
- Banking Agent transfer execution and ledger updates
- High-value transfer review with no ledger mutation
- Blocklisted transfer rejection with no ledger mutation
- Risk Agent account risk assessment (LOW, HIGH, UNKNOWN)
- Risk Agent transfer pre-checks
- Inter-agent collaboration: Credit Agent calling Risk Agent
- Credit Agent loan eligibility decisions:
  * C1001 (proposed EMI ₹10,000) -> ELIGIBLE (~26.3% DTI)
  * C1002 -> ON_HOLD (Blocklisted / HIGH risk)
  * C1003 (proposed EMI ₹10,000) -> INELIGIBLE (Credit score 580, DTI 87.5%)
  * DTI exceeding 50% with high credit score -> INELIGIBLE
- Invalid inputs, negative amounts, non-numeric values, and unknown accounts
- Structured output consistency across all agents (agent, status, message, data, checks)
"""

import unittest
from unittest.mock import MagicMock

from agents import BankingAgent, CreditAgent, RiskAgent
from banking_api import BankingAPI


class TestSpecializedAgents(unittest.TestCase):
    """Test suite for BankingAgent, RiskAgent, and CreditAgent with isolated data."""

    def setUp(self) -> None:
        """Create fresh isolated API and agent instances for every test."""
        self.api = BankingAPI()
        self.risk_agent = RiskAgent(banking_api=self.api)
        self.banking_agent = BankingAgent(banking_api=self.api, risk_agent=self.risk_agent)
        self.credit_agent = CreditAgent(banking_api=self.api, risk_agent=self.risk_agent)

    def test_structured_output_consistency(self) -> None:
        """
        Verify every agent response conforms to the standard structured schema:
        agent (str), status (str), message (str), data, checks (list[str]).
        """
        responses = [
            self.banking_agent.get_account_balance("C1001"),
            self.banking_agent.get_customer_profile("C1001"),
            self.banking_agent.get_transaction_statement("C1001"),
            self.banking_agent.handle_transfer("C1001", "C1003", 5000.0),
            self.risk_agent.assess_account_risk("C1001"),
            self.risk_agent.precheck_transfer("C1001", "C1003", 5000.0),
            self.credit_agent.evaluate_loan_eligibility("C1001", 10000.0),
        ]

        for resp in responses:
            self.assertIn("agent", resp)
            self.assertIsInstance(resp["agent"], str)
            self.assertIn("status", resp)
            self.assertIsInstance(resp["status"], str)
            self.assertIn("message", resp)
            self.assertIsInstance(resp["message"], str)
            self.assertIn("data", resp)
            self.assertIn("checks", resp)
            self.assertIsInstance(resp["checks"], list)
            self.assertGreater(len(resp["checks"]), 0)

    def test_banking_agent_balance_and_statement(self) -> None:
        """Verify Banking Agent balance and statement queries."""
        # Balance retrieval
        bal_res = self.banking_agent.get_account_balance("C1001")
        self.assertEqual(bal_res["agent"], "Banking Agent")
        self.assertEqual(bal_res["status"], "SUCCESS")
        self.assertEqual(bal_res["data"]["balance"], 125000.0)

        # Statement retrieval
        stmt_res = self.banking_agent.get_transaction_statement("C1001")
        self.assertEqual(stmt_res["agent"], "Banking Agent")
        self.assertEqual(stmt_res["status"], "SUCCESS")
        self.assertEqual(stmt_res["data"]["current_balance"], 125000.0)
        self.assertEqual(len(stmt_res["data"]["transactions"]), 3)

        # Profile retrieval
        prof_res = self.banking_agent.get_customer_profile("C1001")
        self.assertEqual(prof_res["status"], "SUCCESS")
        self.assertEqual(prof_res["data"]["name"], "Nila Varadhan")

        # Unknown account
        unknown_res = self.banking_agent.get_account_balance("C9999")
        self.assertEqual(unknown_res["status"], "FAILED")
        self.assertIsNone(unknown_res["data"])

    def test_banking_agent_successful_transfer(self) -> None:
        """Verify successful transfer coordinates Risk Agent pre-check and Banking API."""
        initial_sender = 125000.0
        initial_recipient = 8500.0
        transfer_amt = 12000.0

        res = self.banking_agent.handle_transfer("C1001", "C1003", transfer_amt)

        self.assertEqual(res["agent"], "Banking Agent")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data"]["sender_balance"], initial_sender - transfer_amt)
        self.assertEqual(res["data"]["recipient_balance"], initial_recipient + transfer_amt)

        # Confirm ledger state was updated
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 113000.0)
        self.assertEqual(self.api.get_account_balance("C1003")["balance"], 20500.0)

        # Verify trace contains both Risk Agent and Ledger check actions
        checks_text = " ".join(res["checks"])
        self.assertIn("Risk Agent", checks_text)
        self.assertIn("Banking API", checks_text)

    def test_high_value_transfer_review_no_ledger_mutation(self) -> None:
        """Transfers > ₹50,000 must be halted with REVIEW_REQUIRED and never mutate balances."""
        res = self.banking_agent.handle_transfer("C1001", "C1003", 65000.0)

        self.assertEqual(res["status"], "REVIEW_REQUIRED")
        self.assertIn("Manual review required", res["message"])

        # Crucial: Verify ledger balances did NOT mutate
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)
        self.assertEqual(self.api.get_account_balance("C1003")["balance"], 8500.0)

        # Verify transaction statements are unmodified (still 3 transactions)
        self.assertEqual(len(self.api.get_transaction_statement("C1001")["transactions"]), 3)
        self.assertEqual(len(self.api.get_transaction_statement("C1003")["transactions"]), 3)

    def test_blocklisted_transfer_rejection(self) -> None:
        """Transfers involving blocklisted accounts must be rejected with no ledger modification."""
        # C1002 is blocklisted as sender
        res_sender = self.banking_agent.handle_transfer("C1002", "C1001", 5000.0)
        self.assertEqual(res_sender["status"], "BLOCKED")
        self.assertEqual(self.api.get_account_balance("C1002")["balance"], 45000.0)
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)

        # C1002 is blocklisted as recipient
        res_rcpt = self.banking_agent.handle_transfer("C1001", "C1002", 5000.0)
        self.assertEqual(res_rcpt["status"], "BLOCKED")
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)
        self.assertEqual(self.api.get_account_balance("C1002")["balance"], 45000.0)

    def test_risk_agent_account_assessments(self) -> None:
        """Verify Risk Agent accurately assigns risk levels according to blocklist status."""
        # C1001: Clean -> LOW risk
        r1 = self.risk_agent.assess_account_risk("C1001")
        self.assertEqual(r1["status"], "SUCCESS")
        self.assertEqual(r1["data"]["risk_level"], "LOW")
        self.assertFalse(r1["data"]["is_blocklisted"])

        # C1002: Blocklisted -> HIGH risk
        r2 = self.risk_agent.assess_account_risk("C1002")
        self.assertEqual(r2["status"], "SUCCESS")
        self.assertEqual(r2["data"]["risk_level"], "HIGH")
        self.assertTrue(r2["data"]["is_blocklisted"])

        # C1003: Clean -> LOW risk
        r3 = self.risk_agent.assess_account_risk("C1003")
        self.assertEqual(r3["status"], "SUCCESS")
        self.assertEqual(r3["data"]["risk_level"], "LOW")
        self.assertFalse(r3["data"]["is_blocklisted"])

        # C9999: Unknown account -> FAILED
        r_unknown = self.risk_agent.assess_account_risk("C9999")
        self.assertEqual(r_unknown["status"], "FAILED")
        self.assertEqual(r_unknown["data"]["risk_level"], "UNKNOWN")

    def test_risk_agent_precheck_transfer(self) -> None:
        """Verify Risk Agent preliminary transfer validations."""
        # Approved transfer
        appr = self.risk_agent.precheck_transfer("C1001", "C1003", 20000.0)
        self.assertEqual(appr["status"], "APPROVED")
        self.assertTrue(appr["data"]["approved"])

        # High value (> ₹50,000)
        rev = self.risk_agent.precheck_transfer("C1001", "C1003", 50001.0)
        self.assertEqual(rev["status"], "REVIEW_REQUIRED")

        # Blocked sender
        blk = self.risk_agent.precheck_transfer("C1002", "C1001", 1000.0)
        self.assertEqual(blk["status"], "BLOCKED")

        # Nonexistent account
        missing = self.risk_agent.precheck_transfer("C9999", "C1001", 1000.0)
        self.assertEqual(missing["status"], "FAILED")

        # Same account
        same = self.risk_agent.precheck_transfer("C1001", "C1001", 1000.0)
        self.assertEqual(same["status"], "FAILED")

    def test_credit_agent_calls_risk_agent(self) -> None:
        """
        Verify that Credit Agent programmatically invokes the injected Risk Agent instance
        before evaluating loan eligibility.
        """
        spy_risk_agent = MagicMock(wraps=self.risk_agent)
        credit_agent_with_spy = CreditAgent(banking_api=self.api, risk_agent=spy_risk_agent)

        res = credit_agent_with_spy.evaluate_loan_eligibility("C1001", 10000.0)

        # Assert spy was called exactly once with C1001
        spy_risk_agent.assess_account_risk.assert_called_once_with("C1001")
        self.assertEqual(res["status"], "ELIGIBLE")

        # Verify collaboration trace appears in checks list
        checks_text = " ".join(res["checks"])
        self.assertIn("Consulted Risk Agent", checks_text)

    def test_credit_agent_loan_eligibility_c1001(self) -> None:
        """
        C1001: Credit score 780, Income ₹95,000, Existing EMI ₹15,000.
        Proposed EMI ₹10,000 -> DTI = (25,000 / 95,000) * 100 ≈ 26.3%.
        Expected: ELIGIBLE.
        """
        res = self.credit_agent.evaluate_loan_eligibility("C1001", 10000.0)

        self.assertEqual(res["agent"], "Credit Agent")
        self.assertEqual(res["status"], "ELIGIBLE")
        self.assertEqual(res["data"]["decision"], "ELIGIBLE")
        self.assertEqual(res["data"]["credit_score"], 780)
        self.assertAlmostEqual(res["data"]["dti"], 26.32, places=1)
        self.assertEqual(res["data"]["risk_level"], "LOW")

    def test_credit_agent_loan_eligibility_c1002_on_hold(self) -> None:
        """
        C1002: Rehan Thomas is blocklisted.
        Expected: ON_HOLD because of HIGH risk blocklist status.
        """
        res = self.credit_agent.evaluate_loan_eligibility("C1002", 5000.0)

        self.assertEqual(res["agent"], "Credit Agent")
        self.assertEqual(res["status"], "ON_HOLD")
        self.assertEqual(res["data"]["decision"], "ON_HOLD")
        self.assertEqual(res["data"]["risk_level"], "HIGH")
        self.assertIn("ON HOLD", res["message"])
        self.assertIn("blocklisted", res["message"])

    def test_credit_agent_loan_eligibility_c1003_ineligible(self) -> None:
        """
        C1003: Tara Dev: Credit score 580 (< 650), Income ₹40,000, Existing EMI ₹25,000.
        Proposed EMI ₹10,000 -> DTI = (35,000 / 40,000) * 100 = 87.5% (> 50%).
        Expected: INELIGIBLE (Fails credit score threshold of 650).
        """
        res = self.credit_agent.evaluate_loan_eligibility("C1003", 10000.0)

        self.assertEqual(res["agent"], "Credit Agent")
        self.assertEqual(res["status"], "INELIGIBLE")
        self.assertEqual(res["data"]["decision"], "INELIGIBLE")
        self.assertEqual(res["data"]["credit_score"], 580)
        self.assertAlmostEqual(res["data"]["dti"], 87.5, places=1)
        self.assertIn("below the minimum threshold of 650", res["message"])

    def test_credit_agent_dti_exceeds_threshold_ineligible(self) -> None:
        """
        Test candidate with good credit score (>= 650) but excessive DTI (> 50%).
        Nila (C1001, credit score 780) with a proposed EMI of ₹40,000:
        DTI = (15,000 + 40,000) / 95,000 * 100 = 57.89% (> 50%).
        Expected: INELIGIBLE due to DTI ratio.
        """
        res = self.credit_agent.evaluate_loan_eligibility("C1001", 40000.0)

        self.assertEqual(res["status"], "INELIGIBLE")
        self.assertEqual(res["data"]["decision"], "INELIGIBLE")
        self.assertGreater(res["data"]["dti"], 50.0)
        self.assertIn("exceeds the maximum allowable limit of 50.0%", res["message"])

    def test_invalid_inputs_and_unknown_accounts(self) -> None:
        """Verify handling of invalid inputs, negative values, and unknown accounts."""
        # Nonexistent account for Credit Agent
        c_unknown = self.credit_agent.evaluate_loan_eligibility("C9999", 5000.0)
        self.assertEqual(c_unknown["status"], "FAILED")

        # Invalid proposed EMI (non-numeric, zero, negative, bool)
        for inv_emi in [-1000.0, 0, "5000", True, float("nan")]:
            with self.subTest(emi=inv_emi):
                res = self.credit_agent.evaluate_loan_eligibility("C1001", inv_emi)
                self.assertEqual(res["status"], "FAILED")

        # Invalid transfer amount for Banking Agent
        for inv_amt in [-500.0, 0, "1000", False, float("inf")]:
            with self.subTest(amt=inv_amt):
                res = self.banking_agent.handle_transfer("C1001", "C1003", inv_amt)
                self.assertEqual(res["status"], "FAILED")
                self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)


if __name__ == "__main__":
    unittest.main()
