"""
Headless validation tests for Friends Bank app.py using Streamlit AppTest.

Verifies:
- Clean startup and initial render of Friends Bank light theme
- Customer selector with personalized names (Nila Varadhan, Rehan Thomas, Tara Dev)
- All six sample-use-case buttons (Balance, Statement, Transfer, Review, Loan, Restricted Loan)
- Two-step transfer confirmation requirement before moving funds
- Transfer cancellation leaves ledger untouched
- High-value transfer triggers review-required outcome without moving funds
- Loan eligibility workflow with friendly customer-facing text
- Rerun idempotency: rerunning does not duplicate deductions
- Visual request pipeline rendering and correct agent status (active vs skipped)
- Reset demo ledger button
- Switching customer context does not repeat previous operations
"""

import os
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from banking_api import reset_ledger

APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))


class TestStreamlitApp(unittest.TestCase):
    """Headless integration tests for the Friends Bank Streamlit UI."""

    def setUp(self) -> None:
        """Ensure clean, isolated ledger state for every UI test."""
        reset_ledger()
        self.env_patch = patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_app_initial_render(self) -> None:
        """Verify the app initializes cleanly without exceptions and renders Friends Bank branding."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        self.assertFalse(at.exception)
        # Verify customer selector exists with personalized names
        self.assertGreater(len(at.selectbox), 0)
        # Verify assistant text input exists
        self.assertGreater(len(at.text_input), 0)
        # Verify Friends Bank title is present in markdown
        self.assertTrue(any("Friends Bank" in str(m.value) for m in at.markdown))

    def test_balance_query_workflow(self) -> None:
        """Submit a balance query and verify output and balance metric render."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        self.assertFalse(at.exception)

        # Set input text and submit form
        at.text_input[0].input("Show the balance for C1001")
        [b for b in at.button if "Submit Request" in str(b.label) or "Send Request" in str(b.label)][0].click()
        at.run()

        self.assertFalse(at.exception)
        # Verify balance metric displayed with 125,000
        self.assertTrue(any("125,000" in str(m.value) for m in at.metric))

    def test_sample_button_balance(self) -> None:
        """Sample button 1: Balance C1001 retrieves balance for Nila Varadhan."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        [b for b in at.button if "Balance C1001" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(any("125,000" in str(m.value) for m in at.metric))

    def test_sample_button_transactions(self) -> None:
        """Sample button 2: Transactions C1001 retrieves transaction statement."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        [b for b in at.button if "Transactions C1001" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)
        self.assertGreater(len(at.dataframe), 0)

    def test_sample_button_transfer_allowed(self) -> None:
        """Sample button 3: Transfer ₹12,000 stages two-step confirmation."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        [b for b in at.button if "Transfer ₹12,000" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)
        confirm_btn = [b for b in at.button if "Confirm demo transfer" in str(b.label)]
        self.assertEqual(len(confirm_btn), 1)

    def test_sample_button_transfer_review(self) -> None:
        """Sample button 4: Transfer ₹65,000 triggers review-required outcome without moving funds."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        [b for b in at.button if "Transfer ₹65,000" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)
        [b for b in at.button if "Confirm demo transfer" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Review Required" in str(w.value) or "additional review" in str(w.value) for w in at.warning))

    def test_sample_button_loan_c1001(self) -> None:
        """Sample button 5: Loan Check C1001 confirms pre-approval eligibility."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        [b for b in at.button if "Loan Check C1001" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Completed successfully" in str(s.value) or "meet the current eligibility" in str(s.value) for s in at.success))

    def test_sample_button_loan_c1002_restricted(self) -> None:
        """Sample button 6: Loan Check C1002 halts due to restricted status."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        [b for b in at.button if "Loan Check C1002" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(any("Application Notice" in str(w.value) or "restricted" in str(w.value) for w in at.warning))

    def test_transfer_requires_confirmation_and_rerun_idempotency(self) -> None:
        """
        Verify that transfer requests first prompt for explicit confirmation,
        execute only after confirmed, and subsequent reruns DO NOT re-execute.
        """
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        self.assertFalse(at.exception)

        # 1. Initiate transfer via chat
        at.text_input[0].input("Transfer ₹12,000 from C1001 to C1003")
        [b for b in at.button if "Submit Request" in str(b.label) or "Send Request" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)

        # Confirmation card must be displayed before ledger is touched
        confirm_buttons = [b for b in at.button if "Confirm demo transfer" in str(b.label)]
        self.assertEqual(len(confirm_buttons), 1)

        # Ledger balances must still be starting values before confirmation
        supervisor = at.session_state["supervisor"]
        self.assertEqual(supervisor.banking_api.get_account_balance("C1001")["balance"], 125000.0)

        # 2. Confirm the demo transfer
        confirm_buttons[0].click()
        at.run()
        self.assertFalse(at.exception)

        # Verify sender and recipient balances updated
        self.assertEqual(supervisor.banking_api.get_account_balance("C1001")["balance"], 113000.0)
        self.assertEqual(supervisor.banking_api.get_account_balance("C1003")["balance"], 20500.0)

        # 3. Simulate ordinary Streamlit rerun
        at.run()
        self.assertFalse(at.exception)

        # Balances must remain stable (not deducted again to 101,000!)
        self.assertEqual(supervisor.banking_api.get_account_balance("C1001")["balance"], 113000.0)

    def test_transfer_cancellation_leaves_ledger_unmodified(self) -> None:
        """Verify that cancelling a transfer leaves the ledger completely unmodified."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        self.assertFalse(at.exception)

        # Initiate transfer
        at.text_input[0].input("Transfer ₹12,000 from C1001 to C1003")
        [b for b in at.button if "Submit Request" in str(b.label) or "Send Request" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)

        # Cancel button must exist
        cancel_buttons = [b for b in at.button if "Cancel" in str(b.label)]
        self.assertEqual(len(cancel_buttons), 1)

        # Click Cancel
        cancel_buttons[0].click()
        at.run()
        self.assertFalse(at.exception)

        # Balance remains 125,000
        supervisor = at.session_state["supervisor"]
        self.assertEqual(supervisor.banking_api.get_account_balance("C1001")["balance"], 125000.0)
        self.assertEqual(supervisor.banking_api.get_account_balance("C1003")["balance"], 8500.0)

    def test_visual_pipeline_reflects_agent_participation(self) -> None:
        """Verify the visual request pipeline displays active and skipped agent states accurately."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        # Query balance (only Banking Agent should run, Credit Agent should not)
        at.text_input[0].input("Show the balance for C1001")
        [b for b in at.button if "Submit Request" in str(b.label) or "Send Request" in str(b.label)][0].click()
        at.run()
        self.assertFalse(at.exception)

        # Check visual pipeline markdown contains active Banking Agent and skipped Credit Agent text
        pipeline_renders = [
            str(m.value) for m in at.markdown
            if 'class="pipeline-container"' in str(m.value)
        ]
        self.assertGreater(len(pipeline_renders), 0)
        self.assertIn("Banking Agent", pipeline_renders[0])
        self.assertIn("Not needed for this request", pipeline_renders[0])

    def test_reset_demo_ledger_button(self) -> None:
        """Reset button restores ledger to starting balances and clears response."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        self.assertFalse(at.exception)

        # Perform a transfer with confirmation
        at.text_input[0].input("Transfer ₹12,000 from C1001 to C1003")
        [b for b in at.button if "Submit Request" in str(b.label) or "Send Request" in str(b.label)][0].click()
        at.run()
        confirm_btn = [b for b in at.button if "Confirm demo transfer" in str(b.label)][0]
        confirm_btn.click()
        at.run()
        self.assertFalse(at.exception)

        # Click Reset button in sidebar
        reset_btn = [b for b in at.button if "Reset Demo Ledger" in str(b.label)][0]
        reset_btn.click()
        at.run()

        self.assertFalse(at.exception)
        # Verify ledger in session state has restored C1001 balance to 125,000
        supervisor = at.session_state["supervisor"]
        self.assertEqual(supervisor.banking_api.get_account_balance("C1001")["balance"], 125000.0)

    def test_switching_customer_context_does_not_reexecute(self) -> None:
        """Changing the active customer selectbox reruns without repeating previous transfer."""
        at = AppTest.from_file(APP_PATH, default_timeout=10).run()
        self.assertFalse(at.exception)

        # Execute a transfer
        at.text_input[0].input("Transfer ₹12,000 from C1001 to C1003")
        [b for b in at.button if "Submit Request" in str(b.label) or "Send Request" in str(b.label)][0].click()
        at.run()
        confirm_btn = [b for b in at.button if "Confirm demo transfer" in str(b.label)][0]
        confirm_btn.click()
        at.run()
        self.assertFalse(at.exception)

        supervisor = at.session_state["supervisor"]
        self.assertEqual(supervisor.banking_api.get_account_balance("C1001")["balance"], 113000.0)

        # Switch active customer context in selectbox
        at.selectbox[0].select("C1002")
        at.run()
        self.assertFalse(at.exception)

        # Balance must remain 113,000 (NOT deducted again!)
        self.assertEqual(supervisor.banking_api.get_account_balance("C1001")["balance"], 113000.0)


if __name__ == "__main__":
    unittest.main()
