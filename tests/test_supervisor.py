"""
Unit tests for the Supervisor / Orchestrator (Milestone 3).

Covers:
1. Balance requests routed to Banking Agent
2. Statement requests routed to Banking Agent
3. Transfer requests routed through Banking Agent transfer workflow with correct params
4. Loan requests routed to Credit Agent with proposed EMI
5. Missing or ambiguous required parameters produce NEEDS_INPUT safely
6. Unknown requests handled gracefully
7. Gemini unavailable -> local parser fallback works seamlessly
8. Invalid LLM output -> local fallback works seamlessly
9. Mocked Gemini success path works correctly
10. Existing agent decisions (ON_HOLD, INELIGIBLE, REVIEW_REQUIRED, BLOCKED) are preserved
11. Transfer requires transaction ID to prevent duplicate deductions
12. Execution trace correctly captures complete multi-agent pipeline
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from banking_api import BankingAPI
from supervisor import (
    INTENT_BALANCE,
    INTENT_LOAN_ELIGIBILITY,
    INTENT_STATEMENT,
    INTENT_TRANSFER,
    INTENT_UNKNOWN,
    Supervisor,
)


class TestSupervisor(unittest.TestCase):
    """Test suite for the Supervisor Orchestrator with isolated data and mocked LLM calls."""

    def setUp(self) -> None:
        """Create fresh isolated BankingAPI and Supervisor instance for each test."""
        self.api = BankingAPI()
        self.env_patch = patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        self.env_patch.start()
        self.supervisor = Supervisor(banking_api=self.api)

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_balance_routing(self) -> None:
        """Balance request routes to Banking Agent and retrieves balance."""
        res = self.supervisor.process_request("Show the balance for C1001")

        self.assertEqual(res["intent"], INTENT_BALANCE)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data"]["balance"], 125000.0)
        self.assertEqual(res["data"]["account_id"], "C1001")

        # Verify trace records routing
        trace_text = " ".join(res["execution_trace"])
        self.assertIn("Banking Agent", trace_text)
        self.assertIn("Balance request completed", trace_text)

    def test_statement_routing(self) -> None:
        """Statement request routes to Banking Agent and retrieves statement."""
        res = self.supervisor.process_request("Show the transaction statement for C1001")

        self.assertEqual(res["intent"], INTENT_STATEMENT)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data"]["current_balance"], 125000.0)
        self.assertEqual(len(res["data"]["transactions"]), 3)

        trace_text = " ".join(res["execution_trace"])
        self.assertIn("Banking Agent", trace_text)
        self.assertIn("Statement request completed", trace_text)

    def test_transfer_routing(self) -> None:
        """Transfer request routes to Banking Agent transfer pipeline with correct params."""
        res = self.supervisor.process_request(
            "Transfer ₹12,000 from C1001 to C1003",
            transaction_id="TXN_SUP_TEST_001",
        )

        self.assertEqual(res["intent"], INTENT_TRANSFER)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data"]["sender_balance"], 113000.0)
        self.assertEqual(res["data"]["recipient_balance"], 20500.0)

        # Ledger state verified
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 113000.0)
        self.assertEqual(self.api.get_account_balance("C1003")["balance"], 20500.0)

        # Execution trace reflects full pipeline: Supervisor -> Banking Agent -> Risk Agent -> Ledger
        trace_text = " ".join(res["execution_trace"])
        self.assertIn("Risk Agent", trace_text)
        self.assertIn("Banking API", trace_text)

    def test_loan_eligibility_routing(self) -> None:
        """Loan request routes to Credit Agent with extracted proposed EMI."""
        res = self.supervisor.process_request(
            "Check loan eligibility for C1001 with a proposed monthly EMI of ₹10,000"
        )

        self.assertEqual(res["intent"], INTENT_LOAN_ELIGIBILITY)
        self.assertEqual(res["status"], "ELIGIBLE")
        self.assertEqual(res["data"]["decision"], "ELIGIBLE")
        self.assertAlmostEqual(res["data"]["dti"], 26.32, places=1)

        trace_text = " ".join(res["execution_trace"])
        self.assertIn("Credit Agent", trace_text)
        self.assertIn("Risk Agent", trace_text)

    def test_missing_or_ambiguous_parameters_needs_input(self) -> None:
        """Missing required parameters return safe NEEDS_INPUT without guessing."""
        # Transfer missing recipient
        res1 = self.supervisor.process_request(
            "Transfer ₹5,000 from C1001",
            transaction_id="TXN_ERR_01",
        )
        self.assertEqual(res1["status"], "NEEDS_INPUT")
        self.assertIn("recipient_id", res1["data"]["missing_parameters"])

        # Transfer missing amount
        res2 = self.supervisor.process_request(
            "Transfer from C1001 to C1003",
            transaction_id="TXN_ERR_02",
        )
        self.assertEqual(res2["status"], "NEEDS_INPUT")
        self.assertIn("amount", res2["data"]["missing_parameters"])

        # Loan missing proposed EMI
        res3 = self.supervisor.process_request(
            "Check loan eligibility for C1001"
        )
        self.assertEqual(res3["status"], "NEEDS_INPUT")
        self.assertIn("proposed_emi", res3["data"]["missing_parameters"])

        # Balance inquiry without account ID and no active account
        res4 = self.supervisor.process_request("What is my balance?")
        self.assertEqual(res4["status"], "NEEDS_INPUT")
        self.assertIn("account_id", res4["data"]["missing_parameters"])

    def test_transfer_requires_transaction_id(self) -> None:
        """Transfers without a transaction ID must be halted to prevent duplicate deductions."""
        res = self.supervisor.process_request(
            "Transfer ₹10,000 from C1001 to C1003",
            transaction_id=None,
        )

        self.assertEqual(res["status"], "FAILED")
        self.assertEqual(res["data"]["error_code"], "MISSING_TRANSACTION_ID")
        self.assertIn("transaction_id", res["message"])

        # Ledger balances must be strictly unmodified
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)
        self.assertEqual(self.api.get_account_balance("C1003")["balance"], 8500.0)

    def test_unknown_requests_handled_gracefully(self) -> None:
        """Unrecognized queries return safe UNKNOWN intent with helpful guidance."""
        res = self.supervisor.process_request("Tell me a joke about banking")

        self.assertEqual(res["intent"], INTENT_UNKNOWN)
        self.assertEqual(res["status"], "UNKNOWN")
        self.assertIsNone(res["data"])
        self.assertIn("could not understand", res["message"])

    def test_gemini_unavailable_fallback_to_local_parser(self) -> None:
        """When GEMINI_API_KEY is not set, parser falls back seamlessly to local parser."""
        with patch.dict(os.environ, {}, clear=True):
            sup = Supervisor(banking_api=self.api)
            res = sup.process_request("Show the balance for C1001")

            self.assertEqual(res["parser_used"], "LOCAL_PARSER")
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["data"]["balance"], 125000.0)

            trace_text = " ".join(res["execution_trace"])
            self.assertIn("LOCAL_PARSER", trace_text)

    def test_invalid_llm_output_fallback_to_local_parser(self) -> None:
        """When LLM returns non-JSON or invalid schema, supervisor falls back to local parser."""
        # Mock client returning invalid non-JSON string
        mock_broken_client = MagicMock(return_value="I am not a JSON object")
        sup = Supervisor(banking_api=self.api, llm_client=mock_broken_client)

        res = sup.process_request("Show the balance for C1001")

        # Must gracefully fall back to local parser and still succeed
        self.assertEqual(res["parser_used"], "LOCAL_PARSER")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data"]["balance"], 125000.0)

        # Mock client returning invalid intent
        mock_invalid_intent = MagicMock(
            return_value=json.dumps({"intent": "MALICIOUS_INTENT", "account_id": "C1001"})
        )
        sup2 = Supervisor(banking_api=self.api, llm_client=mock_invalid_intent)
        res2 = sup2.process_request("Show the balance for C1001")

        self.assertEqual(res2["parser_used"], "LOCAL_PARSER")
        self.assertEqual(res2["status"], "SUCCESS")
        self.assertEqual(res2["data"]["balance"], 125000.0)

    def test_mocked_gemini_success_path(self) -> None:
        """When LLM returns valid structured JSON, supervisor uses GEMINI_LLM provenance."""
        valid_llm_payload = json.dumps({
            "intent": "BALANCE",
            "account_id": "C1001",
            "recipient_id": None,
            "amount": None,
            "proposed_emi": None,
        })
        mock_client = MagicMock(return_value=valid_llm_payload)
        sup = Supervisor(banking_api=self.api, llm_client=mock_client)

        res = sup.process_request("Can you let me know how much Nila has?")

        self.assertEqual(res["parser_used"], "GEMINI_LLM")
        self.assertEqual(res["intent"], INTENT_BALANCE)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data"]["balance"], 125000.0)

    def test_preserves_underlying_agent_decisions_and_holds(self) -> None:
        """Supervisor preserves ON_HOLD, INELIGIBLE, BLOCKED, and REVIEW_REQUIRED outcomes."""
        # 1. High value transfer > ₹50,000 -> REVIEW_REQUIRED
        res_review = self.supervisor.process_request(
            "Transfer ₹65,000 from C1001 to C1003",
            transaction_id="TXN_HV_001",
        )
        self.assertEqual(res_review["status"], "REVIEW_REQUIRED")
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)

        # 2. Blocklisted account transfer -> BLOCKED
        res_blocked = self.supervisor.process_request(
            "Transfer ₹5,000 from C1002 to C1001",
            transaction_id="TXN_BLK_001",
        )
        self.assertEqual(res_blocked["status"], "BLOCKED")
        self.assertEqual(self.api.get_account_balance("C1002")["balance"], 45000.0)

        # 3. Blocklisted account loan eligibility -> ON_HOLD
        res_hold = self.supervisor.process_request(
            "Check loan eligibility for C1002 with a proposed monthly EMI of ₹5,000"
        )
        self.assertEqual(res_hold["status"], "ON_HOLD")
        self.assertEqual(res_hold["data"]["decision"], "ON_HOLD")

        # 4. Low credit score loan eligibility -> INELIGIBLE
        res_inelig = self.supervisor.process_request(
            "Check loan eligibility for C1003 with a proposed monthly EMI of ₹10,000"
        )
        self.assertEqual(res_inelig["status"], "INELIGIBLE")
        self.assertEqual(res_inelig["data"]["decision"], "INELIGIBLE")

    def test_active_account_context_fallback(self) -> None:
        """Active account ID is used when prompt does not explicitly state account ID."""
        res = self.supervisor.process_request(
            "Show my account balance",
            active_account_id="C1001",
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data"]["account_id"], "C1001")
        self.assertEqual(res["data"]["balance"], 125000.0)

    def test_preparsed_intent_bypasses_parser(self) -> None:
        """Preparsed intent parameter from quick action buttons bypasses the LLM parser."""
        preparsed = {
            "intent": INTENT_BALANCE,
            "account_id": "C1001",
            "recipient_id": None,
            "amount": None,
            "proposed_emi": None,
        }
        res = self.supervisor.process_request(
            prompt="Quick sample balance button click",
            preparsed_intent=preparsed,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["parser_used"], "SAMPLE_ACTION")
        self.assertEqual(res["data"]["balance"], 125000.0)
        trace_text = " ".join(res["execution_trace"])
        self.assertIn("SAMPLE_ACTION", trace_text)

    def test_gemini_explanation_success(self) -> None:
        """When Gemini client returns a friendly natural explanation, it is attached to the result."""
        mock_explain = MagicMock(return_value="Your balance is healthy and ready for transfers.")
        sup = Supervisor(banking_api=self.api, explain_client=mock_explain)

        res = sup.process_request("Show the balance for C1001")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["explanation_source"], "GEMINI_EXPLANATION")
        self.assertEqual(res["message"], "Your balance is healthy and ready for transfers.")
        trace_text = " ".join(res["execution_trace"])
        self.assertIn("GEMINI_EXPLANATION", trace_text)

    def test_gemini_explanation_fallback_on_error(self) -> None:
        """When Gemini explanation call fails, supervisor safely falls back to local friendly text."""
        mock_failing_client = MagicMock(side_effect=RuntimeError("Quota exceeded or timeout"))
        sup = Supervisor(banking_api=self.api, explain_client=mock_failing_client)

        res = sup.process_request("Show the balance for C1001")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["explanation_source"], "LOCAL_EXPLANATION")
        self.assertIn("available balance for account C1001 is ₹125,000.00", res["message"])
        trace_text = " ".join(res["execution_trace"])
        self.assertIn("LOCAL_EXPLANATION", trace_text)


if __name__ == "__main__":
    unittest.main()
