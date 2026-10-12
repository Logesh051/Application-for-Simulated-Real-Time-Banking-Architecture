# Multi-Agent Banking System — Final Master Plan

## 1. Project Objective

Build a working prototype of a simulated banking system in which a Supervisor coordinates three specialized agents, agents collaborate when necessary, and every sensitive financial operation is protected by deterministic Python rules.

**Constraints:** Python, Streamlit, optional Gemini API, approximately 5–6 hours, no real banking integration.

---

## 2. Architecture — Frozen

```text
┌──────────────────────────────────────────────┐
│                 Streamlit UI                 │
│ User prompt · Inputs · Results · Execution log│
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│          Optional LLM Intent Parser           │
│ Gemini when available; local fallback otherwise│
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│          Supervisor / Orchestrator             │
│ Validates intent · Selects workflow · Coordinates│
└───────────────┬──────────────┬────────────────┘
                │              │
        ┌───────▼────┐  ┌──────▼─────┐  ┌──────────────┐
        │   Banking  │  │    Risk    │  │ Credit / Loan│
        │   Agent    │  │   Agent    │  │    Agent     │
        └───────┬────┘  └──────┬─────┘  └──────┬───────┘
                │              │               │
                └──────────────┴───────────────┘
                               │
┌──────────────────────────────▼───────────────┐
│         Simulated Banking API / Ledger         │
│ Final validation · Balance changes · History   │
│                 Duplicate protection           │
└───────────────────────────────────────────────┘
```

**Architecture note:** The agents are separate logical components inside one Python application, not independently deployed microservices. This is appropriate for the time limit, provided the code demonstrates real coordination and communication between agents.

### Proposed project structure

```text
multi-agent-banking/
├── app.py
├── supervisor.py
├── agents.py
├── banking_api.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
└── test_banking.py
```

---

## 3. Request Workflows

The Risk Agent must not inspect every request indiscriminately. Use the appropriate workflow for each request type.

### A. Balance inquiry

`User → Supervisor → Banking Agent → Banking API → Result`

Read-only request. No unnecessary risk scan.

### B. Transaction statement

`User → Supervisor → Banking Agent → Banking API → Statement`

Read-only request; it does not mutate the balance.

### C. Money transfer

`User → Supervisor → Risk Agent pre-check → Banking Agent → Banking API final validation → Result`

The ledger independently enforces the rules, even if the Supervisor or Risk Agent makes a mistake.

### D. Loan eligibility

`User → Supervisor → Credit Agent → Risk Agent account-risk consultation → Credit decision`

A high-risk account can be placed **ON HOLD**. The Credit Agent evaluates underwriting rules separately. No money is transferred and no loan is disbursed.

This resolves the routing conflict: ordinary queries avoid unnecessary screening, transfers receive transaction-specific checks, and loan applications demonstrate inter-agent collaboration.

---

## 4. Agent Responsibilities

| Component | Must do | Must not do |
|---|---|---|
| Supervisor | Interpret validated requests, select workflows, coordinate agents, assemble execution trace | Directly modify balances |
| Banking Agent | Fetch account information and statements; initiate the transfer workflow | Bypass ledger validation |
| Risk Agent | Assess blocklist/account risk and screen transfers | Authorize transfers by itself |
| Credit Agent | Calculate credit eligibility and consult the Risk Agent | Override a high-risk hold |
| Banking API | Enforce account, amount, blocklist, balance, and duplicate-request rules | Trust the LLM or agents as its sole safeguard |

### Inter-agent collaboration

For the loan workflow, the Credit Agent must actually call the Risk Agent through a Python function or method. It receives the Risk Agent's structured response and uses it in the decision. Merely displaying “Risk Agent checked this” in the UI does not count as collaboration.

For this MVP, use deterministic, simulated risk signals such as blocklist status. Do **not** describe this as historical fraud detection unless meaningful historical fraud signals are implemented and tested.

### Risk Agent operations

Keep the two risk checks separate:

- `assess_account_risk(account_id)`: checks blocklist/profile risk. The Credit Agent can call this during loan eligibility checks.
- `precheck_transfer(account_id, amount)`: checks transfer-specific limits and risks.

This avoids applying transfer rules to unrelated queries.

---

## 5. Demo Accounts and Decision Rules

Use these three demo profiles:

| Account | Customer | Balance | Credit score | Monthly income | Existing EMI | Blocklisted |
|---|---|---:|---:|---:|---:|---|
| C1001 | Aarav Sharma | ₹125,000 | 780 | ₹95,000 | ₹15,000 | No |
| C1002 | Vikram Malhotra | ₹45,000 | 640 | ₹30,000 | ₹5,000 | Yes |
| C1003 | Priya Patel | ₹8,500 | 580 | ₹40,000 | ₹25,000 | No |

The ledger should have internally consistent transaction histories. For example, C1001 can start at ₹35,000, receive a ₹95,000 salary credit, then have a ₹5,000 utility debit, yielding ₹125,000.

### Transfer rules

1. Validate the account and amount. Reject invalid, non-finite, or non-positive amounts.
2. Reject blocked accounts.
3. Transfers **over ₹50,000** receive `REVIEW_REQUIRED` and do not execute.
4. Check sufficient balance before executing an otherwise permitted transfer.
5. Execute the balance change and transaction record only once per transaction ID.

For this prototype, amounts up to and including ₹50,000 may proceed if all other checks pass. These are demonstration rules, not real banking policy.

### Credit rules

Use the following illustrative formula:

\[
\text{DTI} = \frac{\text{Existing EMI} + \text{Proposed EMI}}{\text{Monthly Income}} \times 100
\]

An application meets the sample affordability criteria when:

- Credit score is at least **650**.
- DTI does not exceed **50%**.
- The Risk Agent does not return a high-risk status requiring a hold.

A proposed EMI must be supplied by the user or explicitly configured for the demo. Phrase the example as **“proposed monthly EMI of ₹10,000”**, rather than ambiguously calling ₹10,000 the loan amount.

Expected examples:

- **C1001:** can qualify under these assumptions for a proposed monthly EMI of ₹10,000. DTI = (₹15,000 + ₹10,000) / ₹95,000 × 100 ≈ 26.3%.
- **C1002:** placed **ON HOLD** because of its blocklist status.
- **C1003:** fails the credit-score criterion and exceeds the DTI threshold even before an additional EMI: ₹25,000 / ₹40,000 = 62.5%.

These decisions are simulated—not actual lending advice or an official bank's underwriting policy.

---

## 6. Experimental Model Strategy

The LLM is an optional natural-language interpretation layer, not the safety engine.

- Use a Gemini model that is available to the API key, with the model name configured outside the main application logic.
- Ask it to return a constrained intent and extracted fields, not to execute financial operations.
- Validate its response in Python before routing.
- If the API key, network, or quota fails, fall back to local intent parsing so the core demo still works.
- Measure latency if reporting latency. Do not claim “ultra-low-latency,” performance superiority, or token-generation benchmarks without actual measurements.

If the assignment explicitly requires experimental-model evaluation, include a small test comparing routing accuracy and observed response times over a fixed set of prompts. If time is too short, prioritize working agent workflows and transparent model integration over an elaborate benchmark.

---

## 7. Streamlit Reliability

The UI should display:

- Selected intent
- Agents called
- Checks performed
- Final outcome
- Reasons for a rejection or hold

Transfers must execute only after an explicit submission action. Store a unique transaction ID with each submitted operation and cache the result against that ID. If the same operation is processed again on a rerun, return the original result instead of deducting money twice.

The demo state may live in memory and reset when the app restarts. Document this as a prototype limitation.

---

## 8. Acceptance Tests — Definition of Done

### Core operations

- [ ] Balance inquiry returns the correct amount.
- [ ] Statement displays the correct transaction history.
- [ ] An allowed ₹12,000 transfer from C1001 leaves ₹113,000 after one execution.

### Safety

- [ ] A ₹65,000 transfer returns `REVIEW_REQUIRED` without changing the balance.
- [ ] A blocked-account transfer is rejected without changing the ledger.
- [ ] Invalid amounts and insufficient-funds transfers are rejected.
- [ ] Repeating a transaction ID does not deduct money twice.

### Multi-agent and credit

- [ ] Credit Agent calls Risk Agent and records the returned risk result.
- [ ] C1001 meets the sample loan criteria for a proposed monthly EMI of ₹10,000.
- [ ] C1002 is placed ON HOLD; C1003 is rejected under the sample credit rules.
- [ ] Unknown or incomplete requests produce a safe, understandable response.

### Demo readiness

- [ ] LLM failure triggers the local routing fallback.
- [ ] UI shows the agent execution trace and decision reasons.
- [ ] Application starts using the README instructions from a clean setup.

---

## 9. Deliverables and Six-Hour Schedule

### Deliverables

- Python source files
- `requirements.txt`
- `README.md` with architecture, setup, sample prompts, demo rules, and limitations
- `.env.example` with no real API key
- `.gitignore` excluding `.env` and `.venv/`
- Architecture diagram
- Automated tests for critical paths
- GitHub repository
- Demo recording

### Suggested schedule

| Time | Priority |
|---|---|
| Hour 1 | Banking API and ledger safety |
| Hour 2 | Three agents and structured responses |
| Hour 3 | Supervisor, routing, and inter-agent communication |
| Hour 4 | Streamlit interface and execution trace |
| Hour 5 | Critical tests, README, and architecture diagram |
| Hour 6 | Demo recording, GitHub verification, optional LLM integration and polish |

Protect the final hour for testing and submission. Do not add RAG, databases, deployment, complex frameworks, or elaborate fraud models unless all required tests already pass.

### Demo sequence

1. Introduce the architecture and clarify that this is a simulated, single-process prototype.
2. Check a balance and show a statement.
3. Execute one permitted transfer.
4. Attempt a high-value transfer and show that the balance remains unchanged.
5. Apply the loan workflow and show the Credit Agent consulting the Risk Agent.
6. Show the execution trace and, if implemented, the LLM fallback.
7. Explain limitations honestly: in-memory state, simulated data/rules, no real bank connection, and no real loan disbursement.

---

## 10. Final Plan Decisions

- Freeze the architecture and avoid scope expansion during implementation unless a real test reveals a blocker.
- Build in dependency order: `banking_api.py` → `agents.py` → `supervisor.py` → `app.py` → tests and documentation.
- Keep the deterministic core functional even if Gemini is unavailable.
- Do not let the LLM authorize financial actions or bypass validation.
- Define “finished” by passing the acceptance tests—not by the number of frameworks or features added.

**Submission note:** The assignment deadline previously stated was **12 September 2026**. Confirm that late submissions are still accepted before investing the remaining time.

**Ready-to-execute condition:** Agree on whether a formal experimental-model benchmark is mandatory and confirm submission eligibility. Then implement the frozen plan one component at a time, checking the acceptance tests as you go.
