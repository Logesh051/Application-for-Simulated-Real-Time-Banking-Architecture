"""
Unit tests for the Banking API Foundation (Milestone 1).

Covers:
- Account profile retrieval and validation
- Internal consistency between initial balances and transaction history
- Balance inquiries and transaction statements
- Successful transfers and ledger updates
- Threshold review rule (transfers > ₹50,000 return REVIEW_REQUIRED)
- Blocklisted account transfers (sender and recipient rejection)
- Insufficient funds validation
- Invalid amount validations (negative, zero, non-numeric, boolean, NaN, Inf)
- Duplicate transaction ID prevention (idempotency)
- Nonexistent and identical account validations
- Module-level convenience functions and ledger reset
"""

import math
import unittest

from banking_api import (
    BankingAPI,
    TRANSFER_REVIEW_THRESHOLD,
    get_account_balance,
    get_customer_profile,
    get_transaction_statement,
    reset_ledger,
    transfer_funds,
)


class TestBankingAPI(unittest.TestCase):
    """Test suite for BankingAPI with isolated in-memory instances for every test."""

    def setUp(self) -> None:
        """Create a fresh BankingAPI instance with isolated data for each test."""
        self.api = BankingAPI()

    def test_customer_profiles(self) -> None:
        """Verify that customer profiles match the exact required demo specifications."""
        # C1001: Nila Varadhan
        p1 = self.api.get_customer_profile("C1001")
        self.assertEqual(p1["status"], "SUCCESS")
        self.assertEqual(p1["profile"]["account_id"], "C1001")
        self.assertEqual(p1["profile"]["name"], "Nila Varadhan")
        self.assertEqual(p1["profile"]["balance"], 125000.0)
        self.assertEqual(p1["profile"]["credit_score"], 780)
        self.assertEqual(p1["profile"]["monthly_income"], 95000.0)
        self.assertEqual(p1["profile"]["existing_emi"], 15000.0)
        self.assertFalse(p1["profile"]["is_blocklisted"])
        self.assertFalse(p1["profile"]["blocklisted"])

        # C1002: Rehan Thomas (Blocklisted)
        p2 = self.api.get_customer_profile("C1002")
        self.assertEqual(p2["status"], "SUCCESS")
        self.assertEqual(p2["profile"]["account_id"], "C1002")
        self.assertEqual(p2["profile"]["name"], "Rehan Thomas")
        self.assertEqual(p2["profile"]["balance"], 45000.0)
        self.assertEqual(p2["profile"]["credit_score"], 640)
        self.assertEqual(p2["profile"]["monthly_income"], 30000.0)
        self.assertEqual(p2["profile"]["existing_emi"], 5000.0)
        self.assertTrue(p2["profile"]["is_blocklisted"])
        self.assertTrue(p2["profile"]["blocklisted"])

        # C1003: Tara Dev
        p3 = self.api.get_customer_profile("C1003")
        self.assertEqual(p3["status"], "SUCCESS")
        self.assertEqual(p3["profile"]["account_id"], "C1003")
        self.assertEqual(p3["profile"]["name"], "Tara Dev")
        self.assertEqual(p3["profile"]["balance"], 8500.0)
        self.assertEqual(p3["profile"]["credit_score"], 580)
        self.assertEqual(p3["profile"]["monthly_income"], 40000.0)
        self.assertEqual(p3["profile"]["existing_emi"], 25000.0)
        self.assertFalse(p3["profile"]["is_blocklisted"])
        self.assertFalse(p3["profile"]["blocklisted"])

        # Non-existent account
        p_invalid = self.api.get_customer_profile("C9999")
        self.assertEqual(p_invalid["status"], "FAILED")
        self.assertEqual(p_invalid["error_code"], "ACCOUNT_NOT_FOUND")
        self.assertIsNone(p_invalid["profile"])

    def test_transaction_history_consistency(self) -> None:
        """
        Verify that for every account, the initial transaction history is
        mathematically consistent with the starting balance.
        """
        for acc_id in ["C1001", "C1002", "C1003"]:
            stmt = self.api.get_transaction_statement(acc_id)
            self.assertEqual(stmt["status"], "SUCCESS")
            transactions = stmt["transactions"]
            self.assertGreater(len(transactions), 0)

            computed_balance = 0.0
            for tx in transactions:
                if tx["type"] == "CREDIT":
                    computed_balance += tx["amount"]
                elif tx["type"] == "DEBIT":
                    computed_balance -= tx["amount"]
                # Transaction's recorded balance_after must match computed running balance
                self.assertAlmostEqual(computed_balance, tx["balance_after"])

            # Final computed balance must equal account balance
            acc_bal = self.api.get_account_balance(acc_id)["balance"]
            self.assertAlmostEqual(computed_balance, acc_bal)

    def test_get_account_balance(self) -> None:
        """Verify retrieving balances for valid and invalid accounts."""
        b1 = self.api.get_account_balance("C1001")
        self.assertEqual(b1["status"], "SUCCESS")
        self.assertEqual(b1["balance"], 125000.0)
        self.assertEqual(b1["currency"], "INR")

        b2 = self.api.get_account_balance("C1002")
        self.assertEqual(b2["status"], "SUCCESS")
        self.assertEqual(b2["balance"], 45000.0)

        b3 = self.api.get_account_balance("C1003")
        self.assertEqual(b3["status"], "SUCCESS")
        self.assertEqual(b3["balance"], 8500.0)

        b_none = self.api.get_account_balance("C9999")
        self.assertEqual(b_none["status"], "FAILED")
        self.assertIsNone(b_none["balance"])

    def test_successful_transfer(self) -> None:
        """
        Verify allowed transfer updates sender and recipient balances
        and records transaction history entries for both.
        """
        initial_sender_bal = 125000.0
        initial_recipient_bal = 8500.0
        transfer_amt = 12000.0

        res = self.api.transfer_funds("C1001", "C1003", transfer_amt)

        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["amount"], transfer_amt)
        self.assertEqual(res["sender_balance"], initial_sender_bal - transfer_amt)
        self.assertEqual(res["recipient_balance"], initial_recipient_bal + transfer_amt)
        self.assertFalse(res["is_duplicate"])

        # Check ledger balances
        self.assertEqual(
            self.api.get_account_balance("C1001")["balance"], 113000.0
        )
        self.assertEqual(
            self.api.get_account_balance("C1003")["balance"], 20500.0
        )

        # Check sender transaction history
        sender_stmt = self.api.get_transaction_statement("C1001")
        last_sender_tx = sender_stmt["transactions"][-1]
        self.assertEqual(last_sender_tx["type"], "DEBIT")
        self.assertEqual(last_sender_tx["amount"], transfer_amt)
        self.assertEqual(last_sender_tx["balance_after"], 113000.0)

        # Check recipient transaction history
        recipient_stmt = self.api.get_transaction_statement("C1003")
        last_recipient_tx = recipient_stmt["transactions"][-1]
        self.assertEqual(last_recipient_tx["type"], "CREDIT")
        self.assertEqual(last_recipient_tx["amount"], transfer_amt)
        self.assertEqual(last_recipient_tx["balance_after"], 20500.0)

    def test_transfer_review_required_threshold(self) -> None:
        """
        Amounts strictly greater than ₹50,000 must return REVIEW_REQUIRED
        without modifying balances or transaction histories.
        """
        # Transfer of ₹65,000 exceeds ₹50,000 threshold
        res = self.api.transfer_funds("C1001", "C1003", 65000.0)

        self.assertEqual(res["status"], "REVIEW_REQUIRED")
        self.assertEqual(res["error_code"], "REVIEW_REQUIRED")
        self.assertIn("Manual review required", res["message"])

        # Ensure ledger is untouched
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)
        self.assertEqual(self.api.get_account_balance("C1003")["balance"], 8500.0)
        self.assertEqual(len(self.api.get_transaction_statement("C1001")["transactions"]), 3)
        self.assertEqual(len(self.api.get_transaction_statement("C1003")["transactions"]), 3)

        # Boundary test: transfer of exactly ₹50,000 is permitted
        res_exact = self.api.transfer_funds("C1001", "C1003", TRANSFER_REVIEW_THRESHOLD)
        self.assertEqual(res_exact["status"], "SUCCESS")
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 75000.0)

    def test_blocked_account_transfer(self) -> None:
        """Transfers involving blocklisted accounts must be rejected without changing ledger."""
        # C1002 is blocklisted as sender
        res_sender_blocked = self.api.transfer_funds("C1002", "C1001", 5000.0)
        self.assertEqual(res_sender_blocked["status"], "BLOCKED")
        self.assertEqual(res_sender_blocked["error_code"], "ACCOUNT_BLOCKED")
        self.assertEqual(self.api.get_account_balance("C1002")["balance"], 45000.0)
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)

        # C1002 is blocklisted as recipient
        res_recipient_blocked = self.api.transfer_funds("C1001", "C1002", 5000.0)
        self.assertEqual(res_recipient_blocked["status"], "BLOCKED")
        self.assertEqual(res_recipient_blocked["error_code"], "RECIPIENT_BLOCKED")
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)
        self.assertEqual(self.api.get_account_balance("C1002")["balance"], 45000.0)

    def test_insufficient_funds(self) -> None:
        """Transfer exceeding sender available balance must be rejected without changing ledger."""
        # Priya (C1003) has balance ₹8,500, attempts ₹15,000 transfer
        res = self.api.transfer_funds("C1003", "C1001", 15000.0)

        self.assertEqual(res["status"], "FAILED")
        self.assertEqual(res["error_code"], "INSUFFICIENT_FUNDS")
        self.assertIn("Insufficient funds", res["message"])

        # Ensure ledger is untouched
        self.assertEqual(self.api.get_account_balance("C1003")["balance"], 8500.0)
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 125000.0)

    def test_invalid_amounts(self) -> None:
        """Verify validation of non-positive, non-numeric, and non-finite amounts."""
        invalid_amounts = [
            -500.0,
            0,
            0.0,
            "1000",
            True,  # bool is instance of int in Python, must be caught
            False,
            float("nan"),
            float("inf"),
            float("-inf"),
            None,
        ]

        for inv in invalid_amounts:
            with self.subTest(amount=inv):
                res = self.api.transfer_funds("C1001", "C1003", inv)
                self.assertEqual(res["status"], "FAILED")
                self.assertEqual(res["error_code"], "INVALID_AMOUNT")
                # Ensure balance did not mutate
                self.assertEqual(
                    self.api.get_account_balance("C1001")["balance"], 125000.0
                )
                self.assertEqual(
                    self.api.get_account_balance("C1003")["balance"], 8500.0
                )

    def test_duplicate_transaction_ids(self) -> None:
        """
        Repeating a transaction ID must return cached result and prevent
        duplicate deductions on the ledger.
        """
        txn_id = "TXN_TEST_IDEMPOTENT_001"
        transfer_amt = 10000.0

        # First execution
        res1 = self.api.transfer_funds("C1001", "C1003", transfer_amt, transaction_id=txn_id)
        self.assertEqual(res1["status"], "SUCCESS")
        self.assertFalse(res1["is_duplicate"])
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 115000.0)
        self.assertEqual(self.api.get_account_balance("C1003")["balance"], 18500.0)

        # Repeated execution with same transaction_id
        res2 = self.api.transfer_funds("C1001", "C1003", transfer_amt, transaction_id=txn_id)
        self.assertEqual(res2["status"], "SUCCESS")
        self.assertTrue(res2["is_duplicate"])
        self.assertIn("already executed", res2["message"])

        # Critical: Balance must NOT be deducted again!
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 115000.0)
        self.assertEqual(self.api.get_account_balance("C1003")["balance"], 18500.0)

        # Critical: Transaction statement must have only 1 entry with this transaction_id
        c1001_txs = self.api.get_transaction_statement("C1001")["transactions"]
        matching_txs = [t for t in c1001_txs if t["transaction_id"] == txn_id]
        self.assertEqual(len(matching_txs), 1)

    def test_duplicate_transaction_id_mismatch_rejected(self) -> None:
        """
        Reusing an existing transaction ID with different transfer details
        (different amount, recipient, etc.) must be safely rejected with no ledger modification.
        """
        txn_id = "TXN_TEST_MISMATCH_001"
        res1 = self.api.transfer_funds("C1001", "C1003", 5000.0, transaction_id=txn_id)
        self.assertEqual(res1["status"], "SUCCESS")
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 120000.0)

        # Attempt to reuse txn_id with different amount
        res_diff_amt = self.api.transfer_funds("C1001", "C1003", 7000.0, transaction_id=txn_id)
        self.assertEqual(res_diff_amt["status"], "FAILED")
        self.assertEqual(res_diff_amt["error_code"], "DUPLICATE_TRANSACTION_ID_MISMATCH")
        # Ensure no balance change
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 120000.0)

        # Attempt to reuse txn_id with different recipient
        res_diff_rcpt = self.api.transfer_funds("C1001", "C1002", 5000.0, transaction_id=txn_id)
        self.assertEqual(res_diff_rcpt["status"], "FAILED")
        self.assertEqual(res_diff_rcpt["error_code"], "DUPLICATE_TRANSACTION_ID_MISMATCH")
        self.assertEqual(self.api.get_account_balance("C1001")["balance"], 120000.0)

    def test_invalid_and_nonexistent_accounts(self) -> None:
        """Verify validation of missing accounts and same-account transfers."""
        # Non-existent sender
        res1 = self.api.transfer_funds("C9999", "C1001", 1000.0)
        self.assertEqual(res1["status"], "FAILED")
        self.assertEqual(res1["error_code"], "ACCOUNT_NOT_FOUND")

        # Non-existent recipient
        res2 = self.api.transfer_funds("C1001", "C9999", 1000.0)
        self.assertEqual(res2["status"], "FAILED")
        self.assertEqual(res2["error_code"], "ACCOUNT_NOT_FOUND")

        # Same account transfer
        res3 = self.api.transfer_funds("C1001", "C1001", 1000.0)
        self.assertEqual(res3["status"], "FAILED")
        self.assertEqual(res3["error_code"], "INVALID_TRANSFER")

    def test_module_level_helpers_and_reset(self) -> None:
        """Verify module-level convenience functions and reset_ledger capability."""
        reset_ledger()

        bal = get_account_balance("C1001")
        self.assertEqual(bal["status"], "SUCCESS")
        self.assertEqual(bal["balance"], 125000.0)

        profile = get_customer_profile("C1001")
        self.assertEqual(profile["status"], "SUCCESS")
        self.assertEqual(profile["profile"]["name"], "Nila Varadhan")

        # Transfer via module function
        res = transfer_funds("C1001", "C1003", 5000.0)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(get_account_balance("C1001")["balance"], 120000.0)

        # Reset ledger and verify original state is restored
        reset_ledger()
        self.assertEqual(get_account_balance("C1001")["balance"], 125000.0)


if __name__ == "__main__":
    unittest.main()
