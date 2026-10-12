"""
Simulated Banking API and Ledger Foundation.

This module provides deterministic account management, transaction statements,
and safe transfer logic with strict validation rules.
"""

from copy import deepcopy
from datetime import datetime
import math
import uuid
from typing import Any, Dict, List, Optional


# Transfer review limit: transfers strictly greater than this amount require review
TRANSFER_REVIEW_THRESHOLD: float = 50000.0


def get_default_accounts() -> Dict[str, Dict[str, Any]]:
    """
    Returns a fresh dictionary of initial customer accounts.
    Transaction histories are internally consistent with initial account balances.
    """
    return {
        "C1001": {
            "account_id": "C1001",
            "name": "Nila Varadhan",
            "balance": 125000.0,
            "credit_score": 780,
            "monthly_income": 95000.0,
            "existing_emi": 15000.0,
            "is_blocklisted": False,
            "blocklisted": False,
            "transactions": [
                {
                    "transaction_id": "TXN_INIT_1001_1",
                    "timestamp": "2026-10-01 09:00:00",
                    "type": "CREDIT",
                    "amount": 35000.0,
                    "description": "Opening Deposit",
                    "balance_after": 35000.0,
                },
                {
                    "transaction_id": "TXN_INIT_1001_2",
                    "timestamp": "2026-10-05 10:30:00",
                    "type": "CREDIT",
                    "amount": 95000.0,
                    "description": "Monthly Salary Credit",
                    "balance_after": 130000.0,
                },
                {
                    "transaction_id": "TXN_INIT_1001_3",
                    "timestamp": "2026-10-08 16:45:00",
                    "type": "DEBIT",
                    "amount": 5000.0,
                    "description": "Utility Bill Payment",
                    "balance_after": 125000.0,
                },
            ],
        },
        "C1002": {
            "account_id": "C1002",
            "name": "Rehan Thomas",
            "balance": 45000.0,
            "credit_score": 640,
            "monthly_income": 30000.0,
            "existing_emi": 5000.0,
            "is_blocklisted": True,
            "blocklisted": True,
            "transactions": [
                {
                    "transaction_id": "TXN_INIT_1002_1",
                    "timestamp": "2026-10-01 09:15:00",
                    "type": "CREDIT",
                    "amount": 20000.0,
                    "description": "Opening Deposit",
                    "balance_after": 20000.0,
                },
                {
                    "transaction_id": "TXN_INIT_1002_2",
                    "timestamp": "2026-10-04 11:20:00",
                    "type": "CREDIT",
                    "amount": 30000.0,
                    "description": "Client Invoice Settlement",
                    "balance_after": 50000.0,
                },
                {
                    "transaction_id": "TXN_INIT_1002_3",
                    "timestamp": "2026-10-07 14:10:00",
                    "type": "DEBIT",
                    "amount": 5000.0,
                    "description": "Office Supplies Expense",
                    "balance_after": 45000.0,
                },
            ],
        },
        "C1003": {
            "account_id": "C1003",
            "name": "Tara Dev",
            "balance": 8500.0,
            "credit_score": 580,
            "monthly_income": 40000.0,
            "existing_emi": 25000.0,
            "is_blocklisted": False,
            "blocklisted": False,
            "transactions": [
                {
                    "transaction_id": "TXN_INIT_1003_1",
                    "timestamp": "2026-10-01 09:30:00",
                    "type": "CREDIT",
                    "amount": 10000.0,
                    "description": "Opening Deposit",
                    "balance_after": 10000.0,
                },
                {
                    "transaction_id": "TXN_INIT_1003_2",
                    "timestamp": "2026-10-03 14:00:00",
                    "type": "CREDIT",
                    "amount": 8500.0,
                    "description": "Freelance Payout Credit",
                    "balance_after": 18500.0,
                },
                {
                    "transaction_id": "TXN_INIT_1003_3",
                    "timestamp": "2026-10-06 18:30:00",
                    "type": "DEBIT",
                    "amount": 10000.0,
                    "description": "Monthly Rent Transfer",
                    "balance_after": 8500.0,
                },
            ],
        },
    }


class BankingAPI:
    """
    In-memory ledger providing deterministic balance, profile, and transfer operations.
    """

    def __init__(self, initial_accounts: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.review_threshold: float = TRANSFER_REVIEW_THRESHOLD
        self._initial_accounts_template = initial_accounts or get_default_accounts()
        self.accounts: Dict[str, Dict[str, Any]] = deepcopy(self._initial_accounts_template)
        # Store processed transactions by transaction_id to prevent duplicate deductions
        self.processed_transactions: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        """Resets the ledger and processed transactions back to the initial state."""
        self.accounts = deepcopy(self._initial_accounts_template)
        self.processed_transactions.clear()

    def get_customer_profile(self, account_id: str) -> Dict[str, Any]:
        """
        Retrieves the profile for a customer account.
        """
        normalized_id = str(account_id).strip().upper() if account_id else ""
        account = self.accounts.get(normalized_id)
        if not account:
            return {
                "status": "FAILED",
                "error_code": "ACCOUNT_NOT_FOUND",
                "message": f"Customer account '{account_id}' not found.",
                "profile": None,
            }

        # Return a copy excluding internal transaction array for a clean profile view
        profile = {
            "account_id": account["account_id"],
            "name": account["name"],
            "balance": account["balance"],
            "credit_score": account["credit_score"],
            "monthly_income": account["monthly_income"],
            "existing_emi": account["existing_emi"],
            "is_blocklisted": account["is_blocklisted"],
            "blocklisted": account["blocklisted"],
        }
        return {
            "status": "SUCCESS",
            "message": "Customer profile retrieved successfully.",
            "profile": profile,
        }

    def get_account_balance(self, account_id: str) -> Dict[str, Any]:
        """
        Retrieves the current balance for an account.
        """
        normalized_id = str(account_id).strip().upper() if account_id else ""
        account = self.accounts.get(normalized_id)
        if not account:
            return {
                "status": "FAILED",
                "error_code": "ACCOUNT_NOT_FOUND",
                "message": f"Account '{account_id}' not found.",
                "account_id": account_id,
                "balance": None,
            }

        return {
            "status": "SUCCESS",
            "message": "Account balance retrieved successfully.",
            "account_id": account["account_id"],
            "name": account["name"],
            "balance": account["balance"],
            "currency": "INR",
        }

    def get_transaction_statement(
        self, account_id: str, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retrieves the list of transactions for an account.
        """
        normalized_id = str(account_id).strip().upper() if account_id else ""
        account = self.accounts.get(normalized_id)
        if not account:
            return {
                "status": "FAILED",
                "error_code": "ACCOUNT_NOT_FOUND",
                "message": f"Account '{account_id}' not found.",
                "account_id": account_id,
                "current_balance": None,
                "transactions": [],
            }

        tx_list = deepcopy(account.get("transactions", []))
        if limit is not None and limit > 0:
            tx_list = tx_list[-limit:]

        return {
            "status": "SUCCESS",
            "message": "Transaction statement retrieved successfully.",
            "account_id": account["account_id"],
            "current_balance": account["balance"],
            "transaction_count": len(tx_list),
            "transactions": tx_list,
        }

    def transfer_funds(
        self,
        sender_id: str,
        recipient_id: str,
        amount: Any,
        transaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a safe transfer with strict deterministic ledger validation:
        1. Checks unique transaction_id to prevent duplicate deductions.
        2. Validates amount is a numeric, finite, positive value.
        3. Validates sender and recipient accounts exist.
        4. Validates sender account is not blocklisted.
        5. Validates transfer amounts > ₹50,000 return REVIEW_REQUIRED without changing ledger.
        6. Validates available balance is sufficient.
        7. On success, updates sender and recipient balances and transaction histories.
        """
        normalized_sender = str(sender_id).strip().upper() if sender_id else ""
        normalized_recipient = str(recipient_id).strip().upper() if recipient_id else ""

        # 1. Idempotency check: prevent duplicate deductions and reject mismatched details
        if transaction_id and transaction_id in self.processed_transactions:
            cached = deepcopy(self.processed_transactions[transaction_id])
            details_match = (
                cached.get("sender_id") == normalized_sender
                and cached.get("recipient_id") == normalized_recipient
                and isinstance(amount, (int, float))
                and not isinstance(amount, bool)
                and math.isfinite(amount)
                and cached.get("amount") == float(amount)
            )
            if not details_match:
                return {
                    "status": "FAILED",
                    "error_code": "DUPLICATE_TRANSACTION_ID_MISMATCH",
                    "message": (
                        f"Transaction ID '{transaction_id}' was already used for a different transaction. "
                        "Reusing transaction IDs with different transfer details is rejected."
                    ),
                    "transaction_id": transaction_id,
                    "sender_id": normalized_sender,
                    "recipient_id": normalized_recipient,
                    "amount": amount,
                    "sender_balance": self._get_balance_or_none(normalized_sender),
                }

            sender_acc = self.accounts.get(normalized_sender)
            current_sender_bal = sender_acc["balance"] if sender_acc else None
            cached["is_duplicate"] = True
            cached["message"] = (
                f"Transaction '{transaction_id}' was already executed. "
                "Duplicate deduction prevented."
            )
            cached["sender_balance"] = current_sender_bal
            return cached

        # 2. Validate amount: numeric, finite, and strictly positive
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            return {
                "status": "FAILED",
                "error_code": "INVALID_AMOUNT",
                "message": f"Invalid amount '{amount}'. Amount must be a numeric value.",
                "transaction_id": transaction_id,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "amount": amount,
                "sender_balance": self._get_balance_or_none(normalized_sender),
            }

        if not math.isfinite(amount):
            return {
                "status": "FAILED",
                "error_code": "INVALID_AMOUNT",
                "message": "Invalid amount. Amount must be a finite number.",
                "transaction_id": transaction_id,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "amount": amount,
                "sender_balance": self._get_balance_or_none(normalized_sender),
            }

        if amount <= 0:
            return {
                "status": "FAILED",
                "error_code": "INVALID_AMOUNT",
                "message": f"Invalid amount '{amount}'. Amount must be strictly greater than zero.",
                "transaction_id": transaction_id,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "amount": amount,
                "sender_balance": self._get_balance_or_none(normalized_sender),
            }

        # 3. Validate accounts existence
        if not normalized_sender or normalized_sender not in self.accounts:
            return {
                "status": "FAILED",
                "error_code": "ACCOUNT_NOT_FOUND",
                "message": f"Sender account '{sender_id}' not found.",
                "transaction_id": transaction_id,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "amount": amount,
                "sender_balance": None,
            }

        if not normalized_recipient or normalized_recipient not in self.accounts:
            return {
                "status": "FAILED",
                "error_code": "ACCOUNT_NOT_FOUND",
                "message": f"Recipient account '{recipient_id}' not found.",
                "transaction_id": transaction_id,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "amount": amount,
                "sender_balance": self.accounts[normalized_sender]["balance"],
            }

        if normalized_sender == normalized_recipient:
            return {
                "status": "FAILED",
                "error_code": "INVALID_TRANSFER",
                "message": "Sender and recipient accounts cannot be the same.",
                "transaction_id": transaction_id,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "amount": amount,
                "sender_balance": self.accounts[normalized_sender]["balance"],
            }

        sender = self.accounts[normalized_sender]
        recipient = self.accounts[normalized_recipient]

        # 4. Validate blocklist status
        if sender.get("is_blocklisted", False):
            return {
                "status": "BLOCKED",
                "error_code": "ACCOUNT_BLOCKED",
                "message": f"Transfer rejected: Sender account '{normalized_sender}' is blocklisted.",
                "transaction_id": transaction_id,
                "sender_id": normalized_sender,
                "recipient_id": normalized_recipient,
                "amount": amount,
                "sender_balance": sender["balance"],
            }

        if recipient.get("is_blocklisted", False):
            return {
                "status": "BLOCKED",
                "error_code": "RECIPIENT_BLOCKED",
                "message": f"Transfer rejected: Recipient account '{normalized_recipient}' is blocklisted.",
                "transaction_id": transaction_id,
                "sender_id": normalized_sender,
                "recipient_id": normalized_recipient,
                "amount": amount,
                "sender_balance": sender["balance"],
            }

        # 5. ₹50,000 threshold check -> REVIEW_REQUIRED without changing ledger
        if amount > self.review_threshold:
            return {
                "status": "REVIEW_REQUIRED",
                "error_code": "REVIEW_REQUIRED",
                "message": (
                    f"Transfer amount of ₹{amount:,.2f} exceeds ₹{self.review_threshold:,.2f} threshold. "
                    "Manual review required."
                ),
                "transaction_id": transaction_id,
                "sender_id": normalized_sender,
                "recipient_id": normalized_recipient,
                "amount": amount,
                "sender_balance": sender["balance"],
            }

        # 6. Validate sufficient available balance
        if sender["balance"] < amount:
            return {
                "status": "FAILED",
                "error_code": "INSUFFICIENT_FUNDS",
                "message": (
                    f"Insufficient funds: Available balance is ₹{sender['balance']:,.2f}, "
                    f"attempted transfer is ₹{amount:,.2f}."
                ),
                "transaction_id": transaction_id,
                "sender_id": normalized_sender,
                "recipient_id": normalized_recipient,
                "amount": amount,
                "sender_balance": sender["balance"],
            }

        # 7. Execute transfer on ledger
        assigned_txn_id = transaction_id or f"TXN_{uuid.uuid4().hex[:8].upper()}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sender["balance"] -= float(amount)
        recipient["balance"] += float(amount)

        sender_entry = {
            "transaction_id": assigned_txn_id,
            "timestamp": now_str,
            "type": "DEBIT",
            "amount": float(amount),
            "description": f"Transfer to {recipient['name']} ({normalized_recipient})",
            "balance_after": sender["balance"],
        }
        sender["transactions"].append(sender_entry)

        recipient_entry = {
            "transaction_id": f"{assigned_txn_id}_CREDIT",
            "timestamp": now_str,
            "type": "CREDIT",
            "amount": float(amount),
            "description": f"Transfer from {sender['name']} ({normalized_sender})",
            "balance_after": recipient["balance"],
        }
        recipient["transactions"].append(recipient_entry)

        result = {
            "status": "SUCCESS",
            "message": f"Successfully transferred ₹{amount:,.2f} from {normalized_sender} to {normalized_recipient}.",
            "transaction_id": assigned_txn_id,
            "sender_id": normalized_sender,
            "recipient_id": normalized_recipient,
            "sender_name": sender["name"],
            "recipient_name": recipient["name"],
            "amount": float(amount),
            "sender_balance": sender["balance"],
            "recipient_balance": recipient["balance"],
            "is_duplicate": False,
        }

        # Save to processed transactions for duplicate prevention
        self.processed_transactions[assigned_txn_id] = deepcopy(result)
        return result

    def _get_balance_or_none(self, account_id: str) -> Optional[float]:
        account = self.accounts.get(account_id)
        return account["balance"] if account else None


# Module-level default instance and convenience functions
_default_api = BankingAPI()


def get_api_instance() -> BankingAPI:
    """Returns the default BankingAPI singleton instance."""
    return _default_api


def reset_ledger() -> None:
    """Resets the default module ledger back to its initial state."""
    _default_api.reset()


def get_customer_profile(account_id: str) -> Dict[str, Any]:
    """Retrieves customer profile using the default ledger."""
    return _default_api.get_customer_profile(account_id)


def get_account_balance(account_id: str) -> Dict[str, Any]:
    """Retrieves account balance using the default ledger."""
    return _default_api.get_account_balance(account_id)


def get_transaction_statement(account_id: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """Retrieves transaction statement using the default ledger."""
    return _default_api.get_transaction_statement(account_id, limit=limit)


def transfer_funds(
    sender_id: str,
    recipient_id: str,
    amount: Any,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Executes fund transfer using the default ledger."""
    return _default_api.transfer_funds(
        sender_id=sender_id,
        recipient_id=recipient_id,
        amount=amount,
        transaction_id=transaction_id,
    )
