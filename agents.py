"""
Specialized Agents for Multi-Agent Banking System.

This module implements the three specialized agents:
1. RiskAgent: Assesses account risk levels and performs transfer pre-checks.
2. BankingAgent: Manages customer profiles, balances, statements, and orchestrates
   transfers via RiskAgent pre-checks and Banking API ledger validations.
3. CreditAgent: Evaluates loan eligibility with credit score and DTI criteria,
   explicitly collaborating with RiskAgent for risk assessment.
"""

import math
from typing import Any, Dict, List, Optional

from banking_api import (
    BankingAPI,
    TRANSFER_REVIEW_THRESHOLD,
    get_api_instance,
)


class RiskAgent:
    """
    Risk and Fraud Screening Agent.
    Performs preliminary profile screening and transfer validation.
    Note: This is a simulated risk model, not a production fraud system.
    """

    def __init__(self, banking_api: Optional[BankingAPI] = None) -> None:
        self.agent_name = "Risk Agent"
        self.banking_api = banking_api or get_api_instance()
        self.review_threshold: float = TRANSFER_REVIEW_THRESHOLD

    def assess_account_risk(self, account_id: str) -> Dict[str, Any]:
        """
        Assesses the risk level of an account:
        - HIGH risk: Account is blocklisted.
        - LOW risk: Account exists and is in good standing (not blocklisted).
        - Safe error: Unknown or missing account.
        """
        checks: List[str] = ["Retrieved customer profile from Banking API"]
        normalized_id = str(account_id).strip().upper() if account_id else ""

        profile_resp = self.banking_api.get_customer_profile(normalized_id)
        if profile_resp["status"] != "SUCCESS" or not profile_resp.get("profile"):
            checks.append("Account existence check: Account not found")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": f"Account risk assessment failed: Account '{account_id}' not found.",
                "data": {
                    "account_id": account_id,
                    "risk_level": "UNKNOWN",
                },
                "checks": checks,
            }

        profile = profile_resp["profile"]
        is_blocked = bool(profile.get("is_blocklisted", False))

        if is_blocked:
            checks.append("Screened blocklist registry: Account is blocklisted")
            checks.append("Assigned risk classification: HIGH")
            return {
                "agent": self.agent_name,
                "status": "SUCCESS",
                "message": f"Risk assessment complete: Account '{normalized_id}' is blocklisted (HIGH risk).",
                "data": {
                    "account_id": normalized_id,
                    "risk_level": "HIGH",
                    "is_blocklisted": True,
                    "name": profile.get("name"),
                },
                "checks": checks,
            }

        checks.append("Screened blocklist registry: Account is clean")
        checks.append("Assigned risk classification: LOW")
        return {
            "agent": self.agent_name,
            "status": "SUCCESS",
            "message": f"Risk assessment complete: Account '{normalized_id}' is in good standing (LOW risk).",
            "data": {
                "account_id": normalized_id,
                "risk_level": "LOW",
                "is_blocklisted": False,
                "name": profile.get("name"),
            },
            "checks": checks,
        }

    def precheck_transfer(
        self,
        sender_id: str,
        recipient_id: str,
        amount: Any,
    ) -> Dict[str, Any]:
        """
        Performs preliminary risk screening on a proposed transfer:
        1. Validates amount is numeric, finite, and strictly positive.
        2. Validates sender and recipient accounts exist.
        3. Rejects transfers involving blocklisted accounts.
        4. Returns REVIEW_REQUIRED for amounts exceeding the ₹50,000 threshold.
        5. Returns APPROVED if preliminary screening passes.
        """
        checks: List[str] = []
        normalized_sender = str(sender_id).strip().upper() if sender_id else ""
        normalized_recipient = str(recipient_id).strip().upper() if recipient_id else ""

        # 1. Validate amount
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            checks.append("Validated transfer amount: Non-numeric value")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": f"Transfer pre-check failed: Invalid amount '{amount}'. Must be numeric.",
                "data": {"sender_id": sender_id, "recipient_id": recipient_id, "amount": amount},
                "checks": checks,
            }

        if not math.isfinite(amount):
            checks.append("Validated transfer amount: Non-finite value")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": "Transfer pre-check failed: Amount must be finite (not NaN or Inf).",
                "data": {"sender_id": sender_id, "recipient_id": recipient_id, "amount": amount},
                "checks": checks,
            }

        if amount <= 0:
            checks.append("Validated transfer amount: Non-positive value")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": f"Transfer pre-check failed: Amount ₹{amount} must be strictly positive.",
                "data": {"sender_id": sender_id, "recipient_id": recipient_id, "amount": amount},
                "checks": checks,
            }
        checks.append(f"Validated transfer amount: ₹{amount:,.2f} is positive and finite")

        # 2. Validate accounts existence
        sender_resp = self.banking_api.get_customer_profile(normalized_sender)
        if sender_resp["status"] != "SUCCESS" or not sender_resp.get("profile"):
            checks.append("Verified sender account: Not found")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": f"Transfer pre-check failed: Sender account '{sender_id}' not found.",
                "data": {"sender_id": sender_id, "recipient_id": recipient_id, "amount": amount},
                "checks": checks,
            }
        checks.append(f"Verified sender account: '{normalized_sender}' exists")

        recipient_resp = self.banking_api.get_customer_profile(normalized_recipient)
        if recipient_resp["status"] != "SUCCESS" or not recipient_resp.get("profile"):
            checks.append("Verified recipient account: Not found")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": f"Transfer pre-check failed: Recipient account '{recipient_id}' not found.",
                "data": {"sender_id": sender_id, "recipient_id": recipient_id, "amount": amount},
                "checks": checks,
            }
        checks.append(f"Verified recipient account: '{normalized_recipient}' exists")

        if normalized_sender == normalized_recipient:
            checks.append("Validated account separation: Sender and recipient are identical")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": "Transfer pre-check failed: Sender and recipient cannot be the same account.",
                "data": {"sender_id": sender_id, "recipient_id": recipient_id, "amount": amount},
                "checks": checks,
            }

        sender_profile = sender_resp["profile"]
        recipient_profile = recipient_resp["profile"]

        # 3. Screen blocklist status
        if sender_profile.get("is_blocklisted", False):
            checks.append(f"Screened sender blocklist: Account '{normalized_sender}' is blocklisted")
            return {
                "agent": self.agent_name,
                "status": "BLOCKED",
                "message": f"Transfer pre-check rejected: Sender account '{normalized_sender}' is blocklisted.",
                "data": {
                    "sender_id": normalized_sender,
                    "recipient_id": normalized_recipient,
                    "amount": float(amount),
                    "blocked_account": normalized_sender,
                },
                "checks": checks,
            }

        if recipient_profile.get("is_blocklisted", False):
            checks.append(f"Screened recipient blocklist: Account '{normalized_recipient}' is blocklisted")
            return {
                "agent": self.agent_name,
                "status": "BLOCKED",
                "message": f"Transfer pre-check rejected: Recipient account '{normalized_recipient}' is blocklisted.",
                "data": {
                    "sender_id": normalized_sender,
                    "recipient_id": normalized_recipient,
                    "amount": float(amount),
                    "blocked_account": normalized_recipient,
                },
                "checks": checks,
            }
        checks.append("Screened blocklist registry: Both accounts clear")

        # 4. Check transfer review threshold (> ₹50,000)
        if amount > self.review_threshold:
            checks.append(
                f"Evaluated high-value threshold: Amount ₹{amount:,.2f} exceeds ₹{self.review_threshold:,.2f}"
            )
            return {
                "agent": self.agent_name,
                "status": "REVIEW_REQUIRED",
                "message": (
                    f"Transfer pre-check flagged: Amount of ₹{amount:,.2f} exceeds "
                    f"₹{self.review_threshold:,.2f} threshold. Manual review required."
                ),
                "data": {
                    "sender_id": normalized_sender,
                    "recipient_id": normalized_recipient,
                    "amount": float(amount),
                    "threshold": self.review_threshold,
                },
                "checks": checks,
            }
        checks.append(
            f"Evaluated high-value threshold: Amount ₹{amount:,.2f} within ₹{self.review_threshold:,.2f} limit"
        )

        # 5. Pre-check passed
        checks.append("Preliminary risk checks passed: Transfer approved for ledger execution")
        return {
            "agent": self.agent_name,
            "status": "APPROVED",
            "message": f"Transfer pre-check approved for ₹{amount:,.2f} from {normalized_sender} to {normalized_recipient}.",
            "data": {
                "sender_id": normalized_sender,
                "recipient_id": normalized_recipient,
                "amount": float(amount),
                "approved": True,
            },
            "checks": checks,
        }


class BankingAgent:
    """
    Banking Operations Agent.
    Retrieves account information and initiates fund transfers through
    the Risk Agent pre-check workflow and Banking API ledger validation.
    Does not modify balances directly.
    """

    def __init__(
        self,
        risk_agent: Optional[RiskAgent] = None,
        banking_api: Optional[BankingAPI] = None,
    ) -> None:
        self.agent_name = "Banking Agent"
        self.banking_api = banking_api or get_api_instance()
        self.risk_agent = risk_agent or RiskAgent(banking_api=self.banking_api)

    def get_customer_profile(self, account_id: str) -> Dict[str, Any]:
        """Retrieves customer profile from Banking API."""
        checks = [f"Queried Banking API profile endpoint for account '{account_id}'"]
        resp = self.banking_api.get_customer_profile(account_id)
        if resp["status"] == "SUCCESS":
            checks.append("Profile successfully retrieved")
            return {
                "agent": self.agent_name,
                "status": "SUCCESS",
                "message": resp["message"],
                "data": resp["profile"],
                "checks": checks,
            }
        checks.append("Profile retrieval failed")
        return {
            "agent": self.agent_name,
            "status": "FAILED",
            "message": resp["message"],
            "data": None,
            "checks": checks,
        }

    # Convenient alias
    get_profile = get_customer_profile

    def get_account_balance(self, account_id: str) -> Dict[str, Any]:
        """Retrieves account balance from Banking API."""
        checks = [f"Queried Banking API balance endpoint for account '{account_id}'"]
        resp = self.banking_api.get_account_balance(account_id)
        if resp["status"] == "SUCCESS":
            checks.append(f"Balance retrieved: ₹{resp['balance']:,.2f}")
            return {
                "agent": self.agent_name,
                "status": "SUCCESS",
                "message": resp["message"],
                "data": {
                    "account_id": resp["account_id"],
                    "name": resp["name"],
                    "balance": resp["balance"],
                    "currency": resp["currency"],
                },
                "checks": checks,
            }
        checks.append("Balance retrieval failed")
        return {
            "agent": self.agent_name,
            "status": "FAILED",
            "message": resp["message"],
            "data": None,
            "checks": checks,
        }

    # Convenient alias
    get_balance = get_account_balance

    def get_transaction_statement(
        self, account_id: str, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Retrieves account transaction history from Banking API."""
        checks = [f"Queried Banking API statement endpoint for account '{account_id}'"]
        resp = self.banking_api.get_transaction_statement(account_id, limit=limit)
        if resp["status"] == "SUCCESS":
            checks.append(f"Statement retrieved with {resp['transaction_count']} transactions")
            return {
                "agent": self.agent_name,
                "status": "SUCCESS",
                "message": resp["message"],
                "data": {
                    "account_id": resp["account_id"],
                    "current_balance": resp["current_balance"],
                    "transaction_count": resp["transaction_count"],
                    "transactions": resp["transactions"],
                },
                "checks": checks,
            }
        checks.append("Statement retrieval failed")
        return {
            "agent": self.agent_name,
            "status": "FAILED",
            "message": resp["message"],
            "data": None,
            "checks": checks,
        }

    # Convenient alias
    get_statement = get_transaction_statement

    def handle_transfer(
        self,
        sender_id: str,
        recipient_id: str,
        amount: Any,
        transaction_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Coordinates the transfer workflow:
        1. Calls Risk Agent pre-check.
        2. If Risk Agent rejects or requires review, halts workflow without mutating ledger.
        3. If Risk Agent approves, submits transfer to Banking API ledger for final validation.
        """
        checks: List[str] = ["Initiated transfer workflow through Risk Agent pre-check"]

        # Step 1: Risk Agent preliminary check
        risk_result = self.risk_agent.precheck_transfer(sender_id, recipient_id, amount)
        checks.extend([f"Risk Agent: {c}" for c in risk_result.get("checks", [])])

        if risk_result["status"] != "APPROVED":
            checks.append("Transfer stopped by Risk Agent: Ledger transfer was NOT submitted")
            return {
                "agent": self.agent_name,
                "status": risk_result["status"],
                "message": f"Transfer rejected during risk pre-check: {risk_result['message']}",
                "data": risk_result.get("data", {}),
                "checks": checks,
            }

        # Step 2: Risk Agent approved; submit to Banking API ledger for final enforcement
        checks.append("Risk Agent approved: Submitting transfer to Banking API ledger")
        api_result = self.banking_api.transfer_funds(
            sender_id=sender_id,
            recipient_id=recipient_id,
            amount=amount,
            transaction_id=transaction_id,
        )

        checks.append(f"Banking API ledger response: {api_result['status']}")

        return {
            "agent": self.agent_name,
            "status": api_result["status"],
            "message": api_result["message"],
            "data": api_result,
            "checks": checks,
        }


class CreditAgent:
    """
    Credit and Loan Underwriting Agent.
    Evaluates loan affordability using deterministic demo criteria:
    - Credit score threshold: at least 650.
    - Debt-to-income (DTI) ratio: at most 50%.
      Formula: ((existing EMI + proposed monthly EMI) / monthly income) * 100.
    - Explicitly collaborates with RiskAgent before finalizing credit decisions.
      HIGH risk accounts are placed ON_HOLD.
    """

    def __init__(
        self,
        risk_agent: Optional[RiskAgent] = None,
        banking_api: Optional[BankingAPI] = None,
    ) -> None:
        self.agent_name = "Credit Agent"
        self.banking_api = banking_api or get_api_instance()
        # Explicit dependency on RiskAgent for inter-agent collaboration
        self.risk_agent = risk_agent or RiskAgent(banking_api=self.banking_api)
        self.min_credit_score: int = 650
        self.max_dti_ratio: float = 50.0

    def evaluate_loan_eligibility(
        self,
        account_id: str,
        proposed_emi: Any,
    ) -> Dict[str, Any]:
        """
        Evaluates customer loan eligibility in the exact required decision order:
        1. Unknown account or invalid input -> safe error (FAILED).
        2. Consult Risk Agent: HIGH risk -> ON_HOLD.
        3. Credit score below 650 -> INELIGIBLE.
        4. DTI above 50% -> INELIGIBLE.
        5. Otherwise -> ELIGIBLE.
        """
        checks: List[str] = []
        normalized_id = str(account_id).strip().upper() if account_id else ""

        # 1. Validate proposed EMI input
        if isinstance(proposed_emi, bool) or not isinstance(proposed_emi, (int, float)):
            checks.append("Input validation: Proposed EMI is non-numeric")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": f"Loan evaluation failed: Proposed EMI '{proposed_emi}' must be numeric.",
                "data": None,
                "checks": checks,
            }

        if not math.isfinite(proposed_emi) or proposed_emi <= 0:
            checks.append("Input validation: Proposed EMI is non-finite or non-positive")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": f"Loan evaluation failed: Proposed EMI ₹{proposed_emi} must be a positive finite amount.",
                "data": None,
                "checks": checks,
            }
        checks.append(f"Input validation: Proposed EMI is ₹{proposed_emi:,.2f}")

        # 2. Retrieve customer profile
        profile_resp = self.banking_api.get_customer_profile(normalized_id)
        if profile_resp["status"] != "SUCCESS" or not profile_resp.get("profile"):
            checks.append("Account verification: Customer account not found")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": f"Loan evaluation failed: Customer account '{account_id}' not found.",
                "data": None,
                "checks": checks,
            }
        checks.append(f"Account verification: Retrieved customer profile for '{normalized_id}'")

        profile = profile_resp["profile"]
        monthly_income = float(profile["monthly_income"])
        existing_emi = float(profile["existing_emi"])
        credit_score = int(profile["credit_score"])

        # Check for non-positive income
        if monthly_income <= 0:
            checks.append("Affordability calculation: Monthly income is non-positive")
            return {
                "agent": self.agent_name,
                "status": "FAILED",
                "message": "Loan evaluation failed: Monthly income must be greater than zero to evaluate DTI.",
                "data": None,
                "checks": checks,
            }

        # Calculate DTI ratio
        dti = ((existing_emi + float(proposed_emi)) / monthly_income) * 100.0
        rounded_dti = round(dti, 2)

        # 3. Inter-agent collaboration: programmatically consult Risk Agent
        checks.append("Inter-agent collaboration: Consulted Risk Agent for account risk assessment")
        risk_result = self.risk_agent.assess_account_risk(normalized_id)
        risk_level = risk_result.get("data", {}).get("risk_level", "UNKNOWN")
        checks.append(f"Risk Agent response received: Risk level is {risk_level}")

        # Decision rule 2: HIGH risk -> ON_HOLD
        if risk_level == "HIGH":
            checks.append("Underwriting policy check: High risk account detected -> Placed ON_HOLD")
            return {
                "agent": self.agent_name,
                "status": "ON_HOLD",
                "message": (
                    f"Loan application placed ON HOLD: Risk Agent identified HIGH risk "
                    f"(account '{normalized_id}' is blocklisted). Manual compliance review required."
                ),
                "data": {
                    "account_id": normalized_id,
                    "customer_name": profile["name"],
                    "decision": "ON_HOLD",
                    "risk_level": "HIGH",
                    "credit_score": credit_score,
                    "monthly_income": monthly_income,
                    "existing_emi": existing_emi,
                    "proposed_emi": float(proposed_emi),
                    "dti": rounded_dti,
                    "risk_details": risk_result,
                },
                "checks": checks,
            }

        # Decision rule 3: Credit score below 650 -> INELIGIBLE
        if credit_score < self.min_credit_score:
            checks.append(
                f"Credit score evaluation: Score {credit_score} is below minimum {self.min_credit_score} (Failed)"
            )
            checks.append(f"Affordability calculation: DTI is {rounded_dti:.1f}%")
            return {
                "agent": self.agent_name,
                "status": "INELIGIBLE",
                "message": (
                    f"Loan application INELIGIBLE: Credit score of {credit_score} is below "
                    f"the minimum threshold of {self.min_credit_score} (DTI: {rounded_dti:.1f}%)."
                ),
                "data": {
                    "account_id": normalized_id,
                    "customer_name": profile["name"],
                    "decision": "INELIGIBLE",
                    "reason": f"Credit score {credit_score} is below minimum requirement of {self.min_credit_score}.",
                    "risk_level": risk_level,
                    "credit_score": credit_score,
                    "monthly_income": monthly_income,
                    "existing_emi": existing_emi,
                    "proposed_emi": float(proposed_emi),
                    "dti": rounded_dti,
                    "risk_details": risk_result,
                },
                "checks": checks,
            }
        checks.append(
            f"Credit score evaluation: Score {credit_score} meets minimum threshold of {self.min_credit_score} (Passed)"
        )

        # Decision rule 4: DTI above 50% -> INELIGIBLE
        if dti > self.max_dti_ratio:
            checks.append(
                f"Affordability calculation: DTI ratio {rounded_dti:.1f}% exceeds maximum {self.max_dti_ratio:.1f}% (Failed)"
            )
            return {
                "agent": self.agent_name,
                "status": "INELIGIBLE",
                "message": (
                    f"Loan application INELIGIBLE: Debt-to-income ratio (DTI) of {rounded_dti:.1f}% "
                    f"exceeds the maximum allowable limit of {self.max_dti_ratio:.1f}%."
                ),
                "data": {
                    "account_id": normalized_id,
                    "customer_name": profile["name"],
                    "decision": "INELIGIBLE",
                    "reason": f"DTI of {rounded_dti:.1f}% exceeds maximum allowable limit of {self.max_dti_ratio:.1f}%.",
                    "risk_level": risk_level,
                    "credit_score": credit_score,
                    "monthly_income": monthly_income,
                    "existing_emi": existing_emi,
                    "proposed_emi": float(proposed_emi),
                    "dti": rounded_dti,
                    "risk_details": risk_result,
                },
                "checks": checks,
            }
        checks.append(
            f"Affordability calculation: DTI ratio {rounded_dti:.1f}% is within maximum {self.max_dti_ratio:.1f}% limit (Passed)"
        )

        # Decision rule 5: All criteria met -> ELIGIBLE
        checks.append("Underwriting policy check: All affordability and risk criteria met -> ELIGIBLE")
        return {
            "agent": self.agent_name,
            "status": "ELIGIBLE",
            "message": (
                f"Loan application ELIGIBLE: Credit score of {credit_score} and DTI ratio "
                f"of {rounded_dti:.1f}% satisfy affordability criteria."
            ),
            "data": {
                "account_id": normalized_id,
                "customer_name": profile["name"],
                "decision": "ELIGIBLE",
                "risk_level": risk_level,
                "credit_score": credit_score,
                "monthly_income": monthly_income,
                "existing_emi": existing_emi,
                "proposed_emi": float(proposed_emi),
                "dti": rounded_dti,
                "risk_details": risk_result,
            },
            "checks": checks,
        }
