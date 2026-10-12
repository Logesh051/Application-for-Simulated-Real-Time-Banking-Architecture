"""
Supervisor / Orchestrator for Multi-Agent Banking System.

Responsibilities:
1. Interprets natural language user requests using an optional Gemini LLM parser
   with automatic deterministic fallback to a local regex-based parser.
2. Validates extracted intents and parameters.
3. Coordinates specialized agents according to strict architectural workflows:
   - BALANCE: Supervisor -> Banking Agent -> result.
   - STATEMENT: Supervisor -> Banking Agent -> result.
   - TRANSFER: Supervisor -> Banking Agent -> (Risk Agent pre-check & Banking API ledger) -> result.
   - LOAN_ELIGIBILITY: Supervisor -> Credit Agent -> (Risk Agent consultation) -> result.
   - UNKNOWN / NEEDS_INPUT: Graceful handling with actionable feedback.
4. Enforces idempotent transaction ID handling for transfers to prevent duplicate deductions.
5. Assembles complete execution traces for full observability.
"""

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

# Attempt loading environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agents import BankingAgent, CreditAgent, RiskAgent
from banking_api import BankingAPI, get_api_instance


# Standard supported intents
INTENT_BALANCE = "BALANCE"
INTENT_STATEMENT = "STATEMENT"
INTENT_TRANSFER = "TRANSFER"
INTENT_LOAN_ELIGIBILITY = "LOAN_ELIGIBILITY"
INTENT_UNKNOWN = "UNKNOWN"

VALID_INTENTS = {
    INTENT_BALANCE,
    INTENT_STATEMENT,
    INTENT_TRANSFER,
    INTENT_LOAN_ELIGIBILITY,
    INTENT_UNKNOWN,
}


class Supervisor:
    """
    Central Orchestrator that interprets intents, coordinates specialized agents,
    and constructs end-to-end execution traces.
    """

    def __init__(
        self,
        banking_agent: Optional[BankingAgent] = None,
        risk_agent: Optional[RiskAgent] = None,
        credit_agent: Optional[CreditAgent] = None,
        banking_api: Optional[BankingAPI] = None,
        llm_client: Optional[Any] = None,
        explain_client: Optional[Any] = None,
    ) -> None:
        self.banking_api = banking_api or get_api_instance()
        self.risk_agent = risk_agent or RiskAgent(banking_api=self.banking_api)
        self.banking_agent = banking_agent or BankingAgent(
            banking_api=self.banking_api, risk_agent=self.risk_agent
        )
        self.credit_agent = credit_agent or CreditAgent(
            banking_api=self.banking_api, risk_agent=self.risk_agent
        )
        # Optional mockable or injected LLM clients
        self.llm_client = llm_client
        self.explain_client = explain_client if explain_client is not None else llm_client

    def parse_intent(self, text: str) -> Tuple[Dict[str, Any], str, str]:
        """
        Interprets natural language text.
        Attempts optional Gemini LLM interpretation first if configured.
        Falls back to local deterministic parser if Gemini is unconfigured,
        fails, or returns invalid structure.

        Returns:
            (parsed_fields_dict, parser_used_name, parser_reason_note)
        """
        # 1. Attempt Gemini parsing if available
        llm_result, llm_reason = self._parse_with_gemini(text)
        if llm_result is not None:
            return llm_result, "GEMINI_LLM", llm_reason

        # 2. Fall back to local parser
        local_result = self._parse_with_local(text)
        return local_result, "LOCAL_PARSER", llm_reason

    def _parse_with_gemini(self, text: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Optional Gemini intent interpretation layer.
        Treats LLM output as untrusted and strictly validates schema.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

        # If custom client injected (e.g. for testing)
        client = self.llm_client

        if client is None:
            if not api_key:
                return None, "GEMINI_API_KEY environment variable not set."

            try:
                # Lazy-import official google-genai package
                from google import genai  # type: ignore

                client = genai.Client(api_key=api_key)
            except ImportError:
                return None, "google-genai library not installed."
            except Exception as e:
                return None, f"Failed to initialize Gemini client: {e}"

        prompt_instruction = (
            "You are an intent and parameter extraction assistant for a simulated banking system.\n"
            "Analyze the user prompt and return ONLY a valid JSON object with these keys:\n"
            "- intent: strictly one of ['BALANCE', 'STATEMENT', 'TRANSFER', 'LOAN_ELIGIBILITY', 'UNKNOWN']\n"
            "- account_id: string or null\n"
            "- recipient_id: string or null\n"
            "- amount: numeric float or null\n"
            "- proposed_emi: numeric float or null\n\n"
            f"User Prompt: {text}"
        )
        try:
            # Support callable mock/function client or google-genai Client
            raw_text = ""
            if callable(client):
                res = client(prompt_instruction)
                raw_text = getattr(res, "text", res) if not isinstance(res, str) else res
            elif hasattr(client, "models") and hasattr(client.models, "generate_content"):
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_instruction,
                )
                raw_text = getattr(response, "text", response)
            else:
                return None, "Unrecognized LLM client interface."

            if isinstance(raw_text, bytes):
                raw_text = raw_text.decode("utf-8")
            elif not isinstance(raw_text, str):
                raw_text = str(raw_text)

            if not raw_text:
                return None, "Empty response from LLM."

            # Strip possible markdown code fences
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            data = json.loads(cleaned)
            if not isinstance(data, dict):
                return None, "LLM response is not a valid JSON object."

            intent = str(data.get("intent", "")).strip().upper()
            if intent not in VALID_INTENTS:
                return None, f"LLM returned invalid intent: '{intent}'."

            # Normalize extracted fields safely
            sanitized = {
                "intent": intent,
                "account_id": str(data["account_id"]).strip().upper() if data.get("account_id") else None,
                "recipient_id": str(data["recipient_id"]).strip().upper() if data.get("recipient_id") else None,
                "amount": float(data["amount"]) if data.get("amount") is not None and not isinstance(data.get("amount"), bool) else None,
                "proposed_emi": float(data["proposed_emi"]) if data.get("proposed_emi") is not None and not isinstance(data.get("proposed_emi"), bool) else None,
            }
            return sanitized, f"Parsed using Gemini model '{model_name}'."

        except Exception as err:
            return None, f"Gemini invocation/parsing failed: {err}."

    def _parse_with_local(self, text: str) -> Dict[str, Any]:
        """
        Deterministic, local regex-based natural language parser.
        Extracts intents and parameters without guessing missing information.
        """
        clean_text = text.strip()
        lower_text = clean_text.lower()

        # 1. Identify Intent
        intent = INTENT_UNKNOWN
        if any(w in lower_text for w in ["transfer", "send money", "wire", "pay"]):
            intent = INTENT_TRANSFER
        elif any(w in lower_text for w in ["loan", "emi", "borrow", "eligibility", "affordability"]):
            intent = INTENT_LOAN_ELIGIBILITY
        elif any(w in lower_text for w in ["statement", "transaction history", "transactions", "mini statement"]):
            intent = INTENT_STATEMENT
        elif any(w in lower_text for w in ["balance", "funds", "how much money"]):
            intent = INTENT_BALANCE

        account_id = None
        recipient_id = None
        amount = None
        proposed_emi = None

        # Extract account IDs (standard demo format C\d{4})
        accounts_found = [m.upper() for m in re.findall(r"\b[cC]\d{4}\b", clean_text)]

        if intent == INTENT_TRANSFER:
            # Look for transfer parties e.g. "from C1001 to C1003"
            from_to_match = re.search(
                r"from\s+([cC]\d{4})\s+to\s+([cC]\d{4})", clean_text, re.IGNORECASE
            )
            to_from_match = re.search(
                r"to\s+([cC]\d{4})\s+from\s+([cC]\d{4})", clean_text, re.IGNORECASE
            )

            if from_to_match:
                account_id = from_to_match.group(1).upper()
                recipient_id = from_to_match.group(2).upper()
            elif to_from_match:
                recipient_id = to_from_match.group(1).upper()
                account_id = to_from_match.group(2).upper()
            elif len(accounts_found) >= 2:
                account_id = accounts_found[0]
                recipient_id = accounts_found[1]
            elif len(accounts_found) == 1:
                account_id = accounts_found[0]

            # Extract amount
            amount_match = re.search(
                r"(?:transfer|send|pay)?\s*[₹Rs.\s]*([\d,]+(?:\.\d+)?)\s*(?:from|to|\s|$)",
                clean_text,
                re.IGNORECASE,
            )
            # Currency symbol pattern
            curr_match = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)", clean_text, re.IGNORECASE)

            if curr_match:
                raw_amt = curr_match.group(1).replace(",", "")
                try:
                    amount = float(raw_amt)
                except ValueError:
                    amount = None
            elif amount_match:
                raw_amt = amount_match.group(1).replace(",", "")
                # Ignore if matched number is just account id digits
                if raw_amt not in [acc.replace("C", "") for acc in accounts_found]:
                    try:
                        amount = float(raw_amt)
                    except ValueError:
                        amount = None

        elif intent == INTENT_LOAN_ELIGIBILITY:
            if accounts_found:
                account_id = accounts_found[0]

            # Extract proposed EMI
            emi_match = re.search(
                r"(?:proposed\s+)?(?:monthly\s+)?emi\s+(?:of\s+)?[₹Rs.\s]*([\d,]+(?:\.\d+)?)",
                clean_text,
                re.IGNORECASE,
            )
            if emi_match:
                raw_emi = emi_match.group(1).replace(",", "")
                try:
                    proposed_emi = float(raw_emi)
                except ValueError:
                    proposed_emi = None

        elif intent in (INTENT_BALANCE, INTENT_STATEMENT):
            if accounts_found:
                account_id = accounts_found[0]

        return {
            "intent": intent,
            "account_id": account_id,
            "recipient_id": recipient_id,
            "amount": amount,
            "proposed_emi": proposed_emi,
        }

    def process_request(
        self,
        prompt: str,
        active_account_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        preparsed_intent: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point for user requests:
        1. Interprets natural-language prompt or uses trusted preparsed parameters.
        2. Validates parameters and returns safe NEEDS_INPUT if incomplete.
        3. Routes to appropriate specialized agent workflow.
        4. Generates customer-friendly explanation via Gemini (with local fallback).
        5. Attaches full execution trace and parser/explanation provenance.
        """
        trace: List[str] = [f"Supervisor: Received user prompt: '{prompt}'"]

        # Parse intent & parameters
        if preparsed_intent:
            parsed_fields = preparsed_intent
            parser_name = "SAMPLE_ACTION"
            parser_note = "Predefined verified parameters from sample action"
            intent = parsed_fields.get("intent", INTENT_UNKNOWN)
            trace.append(f"Supervisor: Intent verified via {parser_name}: {intent} ({parser_note})")
        else:
            parsed_fields, parser_name, parser_note = self.parse_intent(prompt)
            intent = parsed_fields.get("intent", INTENT_UNKNOWN)
            trace.append(f"Supervisor: Intent interpreted via {parser_name}: {intent} ({parser_note})")

        # Apply active_account_id fallback if sender/account_id not mentioned in prompt
        account_id = parsed_fields.get("account_id") or (
            active_account_id.strip().upper() if active_account_id else None
        )
        recipient_id = parsed_fields.get("recipient_id")
        amount = parsed_fields.get("amount")
        proposed_emi = parsed_fields.get("proposed_emi")

        def finish_result(
            target_intent: str,
            target_status: str,
            raw_msg: str,
            target_data: Any,
        ) -> Dict[str, Any]:
            explanation, expl_src, expl_note = self.generate_friendly_explanation(
                prompt=prompt,
                intent=target_intent,
                status=target_status,
                data=target_data,
                raw_message=raw_msg,
            )
            trace.append(f"Supervisor: Final explanation generated via {expl_src} ({expl_note})")
            return self._build_result(
                intent=target_intent,
                status=target_status,
                message=explanation,
                raw_message=raw_msg,
                data=target_data,
                trace=trace,
                parser=parser_name,
                explanation_source=expl_src,
            )

        # 1. BALANCE workflow
        if intent == INTENT_BALANCE:
            if not account_id:
                trace.append("Supervisor: Missing account ID for balance inquiry -> Halting")
                return finish_result(
                    target_intent=intent,
                    target_status="NEEDS_INPUT",
                    raw_msg="Please specify an account ID (e.g., C1001) to check the balance.",
                    target_data={"missing_parameters": ["account_id"]},
                )

            trace.append(f"Supervisor: Routing to Banking Agent -> get_account_balance('{account_id}')")
            res = self.banking_agent.get_account_balance(account_id)
            trace.extend([f"Banking Agent: {c}" for c in res.get("checks", [])])
            trace.append(f"Supervisor: Balance request completed with status '{res['status']}'")

            return finish_result(
                target_intent=intent,
                target_status=res["status"],
                raw_msg=res["message"],
                target_data=res.get("data"),
            )

        # 2. STATEMENT workflow
        if intent == INTENT_STATEMENT:
            if not account_id:
                trace.append("Supervisor: Missing account ID for statement request -> Halting")
                return finish_result(
                    target_intent=intent,
                    target_status="NEEDS_INPUT",
                    raw_msg="Please specify an account ID (e.g., C1001) to view the transaction statement.",
                    target_data={"missing_parameters": ["account_id"]},
                )

            trace.append(f"Supervisor: Routing to Banking Agent -> get_transaction_statement('{account_id}')")
            res = self.banking_agent.get_transaction_statement(account_id)
            trace.extend([f"Banking Agent: {c}" for c in res.get("checks", [])])
            trace.append(f"Supervisor: Statement request completed with status '{res['status']}'")

            return finish_result(
                target_intent=intent,
                target_status=res["status"],
                raw_msg=res["message"],
                target_data=res.get("data"),
            )

        # 3. TRANSFER workflow
        if intent == INTENT_TRANSFER:
            missing_params = []
            if not account_id:
                missing_params.append("sender_id")
            if not recipient_id:
                missing_params.append("recipient_id")
            if amount is None or amount <= 0:
                missing_params.append("amount")

            if missing_params:
                trace.append(f"Supervisor: Missing required transfer parameters: {missing_params} -> Halting")
                return finish_result(
                    target_intent=intent,
                    target_status="NEEDS_INPUT",
                    raw_msg=(
                        f"Transfer requires sender, recipient, and positive amount. "
                        f"Missing or invalid: {', '.join(missing_params)}."
                    ),
                    target_data={"missing_parameters": missing_params},
                )

            # Idempotency check: A stable transaction_id must be provided to execute transfer safely
            if not transaction_id:
                trace.append("Supervisor: Missing transaction ID for transfer -> Halting execution")
                return finish_result(
                    target_intent=intent,
                    target_status="FAILED",
                    raw_msg=(
                        "Transfer halted: A unique transaction ID is required to guarantee duplicate "
                        "protection. Please provide a transaction_id."
                    ),
                    target_data={
                        "error_code": "MISSING_TRANSACTION_ID",
                        "sender_id": account_id,
                        "recipient_id": recipient_id,
                        "amount": amount,
                    },
                )

            trace.append(
                f"Supervisor: Routing transfer of ₹{amount:,.2f} from {account_id} to {recipient_id} "
                f"(TxnID: {transaction_id}) to Banking Agent transfer pipeline"
            )

            # Delegate to Banking Agent (which internally invokes Risk Agent pre-check then ledger)
            res = self.banking_agent.handle_transfer(
                sender_id=account_id,
                recipient_id=recipient_id,
                amount=amount,
                transaction_id=transaction_id,
            )

            trace.extend([f"{res.get('agent', 'Agent')}: {c}" for c in res.get("checks", [])])
            trace.append(f"Supervisor: Transfer workflow returned status '{res['status']}'")

            return finish_result(
                target_intent=intent,
                target_status=res["status"],
                raw_msg=res["message"],
                target_data=res.get("data"),
            )

        # 4. LOAN_ELIGIBILITY workflow
        if intent == INTENT_LOAN_ELIGIBILITY:
            missing_params = []
            if not account_id:
                missing_params.append("account_id")
            if proposed_emi is None or proposed_emi <= 0:
                missing_params.append("proposed_emi")

            if missing_params:
                trace.append(f"Supervisor: Missing required loan parameters: {missing_params} -> Halting")
                return finish_result(
                    target_intent=intent,
                    target_status="NEEDS_INPUT",
                    raw_msg=(
                        f"Loan eligibility evaluation requires an account ID and proposed monthly EMI. "
                        f"Missing: {', '.join(missing_params)}."
                    ),
                    target_data={"missing_parameters": missing_params},
                )

            trace.append(
                f"Supervisor: Routing loan eligibility check for '{account_id}' with proposed "
                f"EMI ₹{proposed_emi:,.2f} to Credit Agent"
            )

            # Delegate to Credit Agent (which internally collaborates with Risk Agent)
            res = self.credit_agent.evaluate_loan_eligibility(
                account_id=account_id,
                proposed_emi=proposed_emi,
            )

            trace.extend([f"Credit Agent: {c}" for c in res.get("checks", [])])
            trace.append(f"Supervisor: Loan evaluation returned decision '{res['status']}'")

            return finish_result(
                target_intent=intent,
                target_status=res["status"],
                raw_msg=res["message"],
                target_data=res.get("data"),
            )

        # 5. UNKNOWN intent
        trace.append("Supervisor: Could not determine valid banking intent from prompt")
        return finish_result(
            target_intent=INTENT_UNKNOWN,
            target_status="UNKNOWN",
            raw_msg=(
                "I could not understand your request. You can inquire about account balances, "
                "request transaction statements, initiate transfers, or check loan eligibility."
            ),
            target_data=None,
        )

    def generate_friendly_explanation(
        self,
        prompt: str,
        intent: str,
        status: str,
        data: Any,
        raw_message: str,
    ) -> Tuple[str, str, str]:
        """
        Generates a friendly plain-English customer-facing explanation of the verified facts.
        Tries Gemini response generation first; falls back cleanly to deterministic local phrasing.
        Returns:
            (explanation_text, explanation_source, explanation_note)
        """
        # 1. Attempt Gemini plain-English explanation
        llm_expl, llm_note = self._explain_with_gemini(
            prompt=prompt,
            intent=intent,
            status=status,
            data=data,
            raw_message=raw_message,
        )
        if llm_expl:
            return llm_expl, "GEMINI_EXPLANATION", llm_note

        # 2. Deterministic local explanation fallback
        local_expl = self._local_friendly_explanation(
            intent=intent,
            status=status,
            data=data,
            raw_message=raw_message,
        )
        return local_expl, "LOCAL_EXPLANATION", f"Deterministic plain-English fallback ({llm_note})"

    def _explain_with_gemini(
        self,
        prompt: str,
        intent: str,
        status: str,
        data: Any,
        raw_message: str,
    ) -> Tuple[Optional[str], str]:
        """
        Uses Gemini to generate a friendly, natural plain-English explanation of verified facts.
        Strictly preserves factual safety rules: cannot alter balances or decisions.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        model_name = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

        client = self.explain_client
        if client is None:
            if not api_key:
                return None, "GEMINI_API_KEY environment variable not set."
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
            except ImportError:
                return None, "google-genai library not installed."
            except Exception as e:
                return None, f"Failed to initialize Gemini client: {e}"

        prompt_instruction = (
            "You are a friendly customer banking assistant for Friends Bank.\n"
            "Explain the following verified banking transaction result to the customer in 1 to 3 clear, warm, professional sentences.\n"
            "STRICT RULES:\n"
            "- Base your explanation strictly on the verified facts provided below. Do not invent details.\n"
            "- NEVER alter balances, authorize transfers, or change eligibility decisions.\n"
            "- If a transfer was restricted or needs review, clearly emphasize that NO money was moved.\n"
            "- If a loan is eligible, state that they meet the criteria based on their income and credit score, but NEVER state that money or loan has been disbursed.\n"
            "- If a loan is on hold or ineligible, explain the reason politely.\n\n"
            f"User Prompt: {prompt}\n"
            f"Intent: {intent}\n"
            f"Status: {status}\n"
            f"Verified Facts: {json.dumps(data) if data is not None else 'None'}\n"
            f"System Outcome: {raw_message}\n\n"
            "Your friendly explanation (plain text only):"
        )
        try:
            raw_text = ""
            if callable(client):
                res = client(prompt_instruction)
                raw_text = getattr(res, "text", res) if not isinstance(res, str) else res
            elif hasattr(client, "models") and hasattr(client.models, "generate_content"):
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_instruction,
                )
                raw_text = getattr(response, "text", response)
            else:
                return None, "Unrecognized LLM client interface."

            if isinstance(raw_text, bytes):
                raw_text = raw_text.decode("utf-8")
            elif not isinstance(raw_text, str):
                raw_text = str(raw_text)

            if not raw_text or not raw_text.strip():
                return None, "Empty response from Gemini."

            clean_text = raw_text.strip().replace("```", "").strip()
            # If the response was formatted as JSON, unwrap text if present
            if clean_text.startswith("{") and clean_text.endswith("}"):
                try:
                    js = json.loads(clean_text)
                    clean_text = js.get("explanation") or js.get("message") or None
                except Exception:
                    clean_text = None

            if not clean_text:
                return None, "Non-textual explanation from LLM."

            return clean_text, f"Generated using Gemini model '{model_name}'."
        except Exception as err:
            return None, f"Gemini explanation failed: {err}."

    def _local_friendly_explanation(
        self,
        intent: str,
        status: str,
        data: Any,
        raw_message: str,
    ) -> str:
        """
        Translates internal technical statuses and factual data into clear, customer-friendly plain English.
        """
        # Transfer outcomes
        if intent == INTENT_TRANSFER:
            if status == "SUCCESS" and isinstance(data, dict):
                recipient = data.get("recipient_name") or data.get("recipient_id", "the recipient")
                amount = data.get("amount", 0)
                return f"Your demo transfer is complete. ₹{amount:,.2f} was transferred to {recipient}."
            elif status == "REVIEW_REQUIRED":
                return "This transfer needs additional review. No money was moved."
            elif status in ("BLOCKED", "FAILED") and "blocked" in raw_message.lower():
                return "This operation cannot continue because this demo account is restricted."
            elif status == "NEEDS_INPUT":
                return "Please provide the sender account, recipient, and amount to complete your transfer."
            elif status == "CANCELLED":
                return "Transfer cancelled. No changes were made to your account."
            return raw_message

        # Balance outcomes
        if intent == INTENT_BALANCE:
            if status == "SUCCESS" and isinstance(data, dict):
                acc_id = data.get("account_id", "")
                bal = data.get("balance", 0)
                return f"Your current available balance for account {acc_id} is ₹{bal:,.2f}."
            elif status == "NEEDS_INPUT":
                return "Please specify which account you would like to check the balance for."
            return raw_message

        # Statement outcomes
        if intent == INTENT_STATEMENT:
            if status == "SUCCESS" and isinstance(data, dict):
                acc_id = data.get("account_id", "")
                txs = data.get("transactions", [])
                return f"Here is your recent transaction history for account {acc_id}. There are {len(txs)} recorded transactions."
            elif status == "NEEDS_INPUT":
                return "Please specify which account you would like to view transactions for."
            return raw_message

        # Loan outcomes
        if intent == INTENT_LOAN_ELIGIBILITY:
            if status == "ELIGIBLE" and isinstance(data, dict):
                return "Based on the demo rules, you meet the current eligibility criteria for this proposed loan."
            elif status == "INELIGIBLE" and isinstance(data, dict):
                reasons = []
                if data.get("credit_score", 0) < 650:
                    reasons.append(f"credit score of {data.get('credit_score')} is below the 650 requirement")
                if data.get("dti", 0) > 50.0:
                    reasons.append(f"debt-to-income ratio of {data.get('dti'):.1f}% exceeds the 50% limit")
                reason_str = " and ".join(reasons) if reasons else "financial requirements were not met"
                return f"Based on the demo eligibility rules, this application does not qualify because the {reason_str}."
            elif status == "ON_HOLD":
                return "This operation cannot continue because this demo account is restricted and on hold for risk review."
            elif status == "NEEDS_INPUT":
                return "Please provide an account ID and proposed monthly EMI to evaluate loan eligibility."
            return raw_message

        # Unknown
        if intent == INTENT_UNKNOWN:
            return (
                "I could not understand your request. You can check your balance, view transactions, "
                "transfer demo money, or explore loan eligibility."
            )

        return raw_message

    def _build_result(
        self,
        intent: str,
        status: str,
        message: str,
        data: Any,
        trace: List[str],
        parser: str,
        explanation_source: str = "LOCAL_EXPLANATION",
        raw_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Constructs standardized Supervisor response dictionary."""
        return {
            "intent": intent,
            "status": status,
            "message": message,
            "raw_agent_message": raw_message or message,
            "data": data,
            "execution_trace": trace,
            "parser_used": parser,
            "explanation_source": explanation_source,
        }
