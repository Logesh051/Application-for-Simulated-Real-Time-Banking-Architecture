# Friends Bank — 5–8 Minute Demonstration Script

> **Presenter Guide:** This script provides a practical, step-by-step walkthrough to present **Friends Bank** during an interview, technical evaluation, or recorded video demonstration. Every interaction directly reflects the live running Streamlit interface.

---

## Preparation (Before You Begin)

1. Ensure the Streamlit server is running:
   ```powershell
   python -m streamlit run app.py
   ```
2. Open **[http://localhost:8501](http://localhost:8501)** in Google Chrome or Microsoft Edge.
3. Maximize the browser window (or zoom to 100%).
4. In the left sidebar, click **"🔄 Reset Demo Ledger"** to ensure all balances and session states start at baseline values.
5. Make sure the active customer in the sidebar is set to **`C1001 — Nila Varadhan`**.

---

## Step-by-Step Presentation Walkthrough

### Step 1: Introduction & Environment Notice (30–45 seconds)
- **Action:** Point to the top banner: **"Friends Bank — A simulated banking environment"**.
- **What Appears on Screen:** Clean light-themed header with the demo notice: *"Demo environment — fictional accounts and simulated money. No real transactions."*
- **What You Say:**
  > *"Hello everyone! Today I'm demonstrating Friends Bank, a simulated multi-agent digital banking environment. Before we dive into the demo, I'd like to highlight that this application uses simulated accounts, fictional customers, and demo money. It is designed to demonstrate how autonomous AI agents collaborate safely to handle banking operations."*

---

### Step 2: Overview of the Interface & Active Customer (30 seconds)
- **Action:** Point to the left sidebar customer selector and the right metrics card.
- **What Appears on Screen:** Customer selector showing `C1001 — Nila Varadhan`, the active demo balance metric showing **`₹125,000.00`**, and the engine status (*"🤖 Gemini: Connected"* or *"⚡ Local Engine: Active"*).
- **What You Say:**
  > *"In the sidebar, we can switch between active fictional customer profiles. We're currently logged in as Nila Varadhan, account C1001. Her available demo balance is ₹125,000. Under 'How Friends Bank works', users can clearly see that requests are coordinated across specialized agents: a Banking Agent, a Risk Agent, and a Credit Agent, with natural language powered by Gemini and backed by an offline local fallback."*

---

### Step 3: Balance Inquiry & Transaction Statement (45 seconds)
- **Action 1:** Click the first quick scenario button: **"💰 Balance C1001"** (or type `"Check my balance"` in the chat box and click **"Submit Request"**).
- **What Appears on Screen:** Green success card: *"Completed successfully"*, balance metric displaying **`₹125,000.00`**, and the Live Request Pipeline showing Banking Agent as **Completed** and Credit Agent as **Not needed for this request**.
- **What You Say:**
  > *"Let's test a simple balance inquiry by clicking 'Balance C1001'. The coordinator understands the request and dispatches it strictly to the Banking Agent. Notice how the visual pipeline reflects real agent participation: the Banking Agent is marked 'Completed', while the Credit and Risk agents are skipped because they aren't needed. This avoids unnecessary computation."*

- **Action 2:** Click the second button: **"📜 Transactions C1001"**.
- **What Appears on Screen:** A formatted table listing the recent account statement records (Salary credit of ₹1,00,000, Grocery spend of ₹5,000, etc.).
- **What You Say:**
  > *"Next, we retrieve Nila's statement with one click. The Banking Agent queries the ledger and formats the chronological transaction history into an interactive data table."*

---

### Step 4: Standard Transfer with Two-Step Confirmation (60 seconds)
- **Action 1:** Click the third button: **"💸 Transfer ₹12,000"** (Transfer ₹12,000 from C1001 to C1003).
- **What Appears on Screen:** An amber review card appears:
  - *From Account: `C1001`*
  - *To Recipient: `C1003`*
  - *Transfer Amount: `₹12,000.00`*
  - Buttons: **[✅ Confirm demo transfer]** (Teal primary) and **[❌ Cancel]** (White secondary).
  - *Notice: Balance metric still shows ₹125,000.00. No money has moved yet.*
- **What You Say:**
  > *"Now let's demonstrate money movement. When we initiate a transfer of ₹12,000 from Nila to C1003 (Tara Dev), the system stages the transfer in an explicit confirmation card. Notice that the balance is still ₹125,000. In real banking, transfers should never execute without explicit customer confirmation. If I clicked Cancel, the transaction would abort cleanly."*

- **Action 2:** Click **"✅ Confirm demo transfer"**.
- **What Appears on Screen:** Green success card with updated balances:
  - *Transfer Amount: `₹12,000.00`*
  - *Sender New Balance: `₹113,000.00`*
  - *Recipient New Balance: `₹20,500.00`*
- **What You Say:**
  > *"When we click 'Confirm', the Banking Agent first calls the Risk Agent to screen the recipient and amount. The Risk Agent approves the pre-check, and the Core Banking API atomically debits ₹12,000 from Nila and credits it to Tara Dev with full idempotency protection."*

---

### Step 5: High-Value Transfer Risk Review Threshold (45 seconds)
- **Action 1:** Click the fourth button: **"⚠️ Transfer ₹65,000 (Review)"**.
- **Action 2:** Click **"✅ Confirm demo transfer"** in the staged card.
- **What Appears on Screen:** An amber alert card:
  - Heading: **"Review Required"**
  - Message explaining that transfers above ₹50,000.00 exceed the automated threshold and require supervisor review.
  - *Notice: Nila's balance remains ₹113,000.00. Zero funds were deducted.*
- **What You Say:**
  > *"Now let's test institutional risk limits. Nila has sufficient balance, but she requests a transfer of ₹65,000 to C1003. When we confirm, the Risk Agent flags that the amount exceeds the ₹50,000 institutional threshold. Instead of completing the transfer, the system safely halts the transaction in a 'REVIEW_REQUIRED' state. No money is moved."*

---

### Step 6: Credit & Loan Eligibility Pre-Screening (45 seconds)
- **Action:** Click the fifth button: **"📋 Loan Check C1001"** (Loan check for C1001 with ₹10,000 proposed EMI).
- **What Appears on Screen:** Green success card:
  - *Credit Score: `760`*
  - *Debt-to-Income (DTI): `21.4%`*
  - *Risk Rating: `LOW`*
  - Result: Loan application pre-approved.
- **What You Say:**
  > *"Now we explore loan underwriting. When Nila requests loan eligibility for a ₹10,000 monthly EMI, the request routes to the Credit Agent. The Credit Agent consults Nila's profile, calculates a 21.4% DTI ratio, notes her 760 credit score, and pre-approves her application."*

---

### Step 7: Restricted Account Loan Check & Credit-to-Risk Interaction (60 seconds)
- **Action 1:** Go to the sidebar and change the **Active Customer Account** to:
  **`C1002 — Rehan Thomas (Restricted)`**.
- **What Appears on Screen:** A yellow warning appears in the account overview: *"⚠️ Restricted Account: Transfers and loans are on hold for security screening."* Available balance shows ₹45,000.00.
- **Action 2:** Click the sixth button: **"⛔ Loan Check C1002"** (Loan check for C1002 with proposed EMI of ₹5,000).
- **What Appears on Screen:** Yellow alert card:
  - Heading: **"Application Notice"**
  - Status: `ON_HOLD`
  - Message explaining that the loan application is on hold due to security/compliance restrictions on the account.
  - In the Live Request Pipeline, both **Credit Agent** and **Risk Agent** are marked **Completed**.
- **What You Say:**
  > *"Here is the key architectural highlight: genuine inter-agent collaboration. Rehan Thomas has a healthy 680 credit score, which on paper might qualify for a small loan. However, the Credit Agent does not evaluate loans in isolation. It actively consults the Risk Agent to screen the applicant. The Risk Agent identifies that Rehan's account is flagged on a security blocklist, and immediately halts the loan with an 'ON_HOLD' status. This demonstrates cross-agent security defense."*

---

### Step 8: Live Request Pipeline & Audit Trace (45 seconds)
- **Action:** Scroll down and expand the section: **"🔍 How this request was handled"**.
- **What Appears on Screen:**
  - Request Metadata: Identified Request (`LOAN_ELIGIBILITY`), Intent Parser (`LOCAL_PARSER` or `GEMINI_LLM`), Explanation Engine (`LOCAL_EXPLANATION` or `GEMINI_EXPLANATION`), System Status (`ON_HOLD`).
  - Chronological Multi-Agent Trace:
    1. *🎯 Supervisor: Routing LOAN_ELIGIBILITY request for account C1002.*
    2. *📊 Credit Agent: Evaluating loan eligibility for account C1002 with proposed EMI of ₹5,000.00.*
    3. *🛡️ Risk Agent: Screening applicant C1002 for account restrictions.*
    4. *🛡️ Risk Agent: Account C1002 is flagged on security blocklist. Restriction enforced.*
    5. *📊 Credit Agent: Application placed ON_HOLD due to Risk Agent restriction.*
  - Collapsible JSON technical payload viewer.
- **What You Say:**
  > *"Every single request generates an immutable audit trace. When we expand 'How this request was handled', we see the exact chronological interaction: the Supervisor routes the request, the Credit Agent invokes the Risk Agent, the Risk Agent flags the restriction, and the final decision is collated. There is complete visibility into how the multi-agent system reached its decision."*

---

### Step 9: Gemini Response Generation & Deterministic Local Fallback (30 seconds)
- **Action:** Point out the caption above the result card:
  *"✨ Response generated by Gemini LLM (Natural Language)"* or *"⚡ Response generated by Local Fallback (Deterministic Plain-English)"*.
- **What You Say:**
  > *"Friends Bank is built with resilient dual-engine intelligence. When a Gemini API key is configured, Gemini translates complex multi-agent results into polite, plain English. But if the API key is omitted, the network fails, or quotas are exhausted, our deterministic local fallback immediately takes over with zero downtime and zero external dependencies."*

---

### Step 10: Conclusion, Automated Testing & Wrap-Up (30 seconds)
- **Action:** In the left sidebar, click **"🔄 Reset Demo Ledger"**.
- **What Appears on Screen:** Toast notification: *"Friends Bank demo ledger reset to initial values."*
- **What You Say:**
  > *"Finally, we can reset the demo ledger back to baseline at any time with a single click. The entire system is covered by an automated test suite with 53 passing unit and headless UI tests covering ledger safety, agent workflows, routing, and idempotency. Thank you for watching the Friends Bank demonstration!"*
