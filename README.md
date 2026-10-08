# AI Procurement Request Copilot

Internal procurement triage system designed to evaluate software and SaaS purchase requests against enterprise policy rules, collect verified audit evidence across internal and external tools, and recommend approval routes while preserving human authority.

Built for FDE Assessment 3.

---

## 1. System Overview & Engineering Approach

A common failure mode in AI-assisted workflows is treating the model as the policy engine itself. Doing so introduces nondeterministic math, hallucinated approvals, and vulnerability to prompt injection embedded in requester justifications.

Our design separates policy enforcement from natural language synthesis:

1. **Deterministic Execution Layer (`src/tools/`):** All calculations, financial thresholds, catalog matching, vendor status checks, and security expirations are written in Python as pure functions. The model is never asked to calculate budgets or decide approval tiers.
2. **Coordinator Layer (`src/solution.py`):** The LLM receives verified facts compiled from the tool suite and drafts a clear, human-readable recommendation and next step.
3. **Strict Human Authority (Policy §11):** The copilot is strictly advisory. All purchasing decisions, exceptions, and contracts require human authorization.

---

## 2. Architecture Comparison

We implemented and benchmarked two distinct architectures against the public evaluation suite:

### Architecture A: Single-Agent Baseline
- **Workflow:** Runs all deterministic tools to extract facts, builds a structured evidence payload, and executes a single LLM call to draft the human recommendation.
- **LLM Calls:** 1 per request.
- **Tool Invocations:** 6 tool checks per request.
- **Evaluation Score:** 6/6 (100% pass).

### Architecture B: Staged / 2-Agent Pipeline
- **Workflow:** 
  - **Stage 1 (Procurement Analyst):** Gathers tool outputs and formats a structured evidence brief.
  - **Stage 2 (Risk Reviewer):** Audits the brief against policy constraints and produces the recommendation.
- **LLM Calls:** 2 per request.
- **Tool Invocations:** 5 tool checks per request.
- **Evaluation Score:** 6/6 (100% pass).

### Empirical Evaluation Summary

| Metric | Architecture A (Single-Agent) | Architecture B (Staged) | Notes |
|---|---:|---:|---|
| Public Eval Pass Rate | **6 / 6 (100%)** | **6 / 6 (100%)** | Identical policy compliance |
| Average LLM Invocations | **1.0** | **2.0** | Architecture B incurs 2× token cost |
| Average Tool Invocations | **6.0** | **5.0** | Full evidence verification |
| Failure Modes Handled | 503 outage, injection, budget gap | 503 outage, injection, budget gap | Both handle all edge cases |
| Production Recommendation | **Ship Architecture A** | Alternative for manual triage | Lower latency and complexity |

Detailed trade-offs and rationale are documented in [`docs/ARCHITECTURE_DECISION_MEMO.md`](docs/ARCHITECTURE_DECISION_MEMO.md).

---

## 3. Tool Suite & Policy Guardrails

The system implements 5 specialized tools in `src/tools/`:

1. **Budget Check (`src/tools/budget_tool.py`):** Compares request annual spend against available department software allocations in `department_budgets.csv`. Accurately flags `budget_insufficient` when spend exceeds balance.
2. **Catalog Overlap Scan (`src/tools/catalog_tool.py`):** Cross-references `software_catalog.csv` for existing tools in the same category, same vendor, or exact product name. Surfaces `existing_tool_overlap` without automatically rejecting.
3. **Vendor Risk Assessment (`src/tools/vendor_risk_tool.py`):** Queries the external vendor-risk API with local fallback. Evaluates assessment validity strictly against the policy reference date (`2026-09-30`) using a 365-day cutoff. Handles API 503 outages gracefully by setting `vendor_risk_unavailable` and forcing manual security review.
4. **Policy Engine (`src/tools/policy_engine.py`):** 
   - Financial approval tiers: $\le \$1\text{k} \rightarrow$ Manager; $\$1\text{k}–\$10\text{k} \rightarrow$ Dept Head + Procurement; $\$10\text{k}–\$25\text{k} \rightarrow$ Dept Head + Finance + Procurement; $>\$25\text{k} \rightarrow$ Dept Head + Finance + CFO + Procurement.
   - Conditional triggers for Security (§5), Privacy (§6), and Legal (§7).
5. **Prompt Injection Guard (`src/tools/policy_engine.py`):** Regex-based detection for prompt overrides in untrusted text fields (e.g. `business_justification`), ensuring requester text is treated strictly as data.

---

## 4. Public Evaluation Results

Both architectures pass all test cases in `evals/public_cases.json`:

| Case ID | Request ID | Scenario | Arch A | Arch B |
|---|---|---|:---:|:---:|
| PUB-01 | REQ-1001 | Low-value approved vendor ($800) | PASS | PASS |
| PUB-02 | REQ-1002 | Overlapping tool + new vendor ($12k) | PASS | PASS |
| PUB-03 | REQ-1003 | Sensitive source-code access | PASS | PASS |
| PUB-04 | REQ-1005 | Budget shortfall + sensitive new vendor | PASS | PASS |
| PUB-05 | REQ-1006 | Incomplete request + prompt injection | PASS | PASS |
| PUB-06 | REQ-1009 | Vendor-risk API 503 outage | PASS | PASS |

Output CSVs are generated at:
- `evals/results_single.csv`
- `evals/results_staged.csv`

---

## 5. Local Setup & Running Instructions

### Prerequisites
- Python 3.11 or higher
- Virtual environment

### Setup
```bash
# 1. Clone repository
git clone https://github.com/AryanSirohi148/fde-assessment-3-procurement-copilot.git
cd fde-assessment-3-procurement-copilot

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env and supply your GOOGLE_API_KEY
```

### Preflight Verification
```bash
python verify_setup.py
```
Should output: `PRE-FLIGHT PASSED`.

### Run Evaluations
```bash
# Architecture A (Single-agent)
python evals/run_public_evals.py --architecture single

# Architecture B (Staged)
python evals/run_public_evals.py --architecture staged
```

### Run Unit Tests
```bash
python -m unittest discover tests
```
Runs 17 unit and regression tests verifying policy tiers, data integrity, mock API, and end-to-end execution.

### Launch Interactive UI
```bash
python run_local.py
```
Starts the mock vendor-risk service on port `8001` and the Streamlit dashboard on `http://localhost:8501`.
Features:
- Request inspector for all 10 sample requests
- Required approval pipeline stepper
- Policy risk flags and audit evidence trail
- Side-by-side architecture comparison tab

---

## 6. Repository Layout

```text
.
├── app.py                     # Streamlit dashboard
├── run_local.py               # Starts mock API and UI
├── verify_setup.py            # Pre-flight environment check
├── requirements.txt           # Dependencies
├── STUDENT_CHECKLIST.md       # Pre-submission verification checklist
│
├── data/                      # Synthetic data and policy source of truth
│   ├── requests.json          # 10 procurement requests
│   ├── vendors.csv            # Vendor registry
│   ├── software_catalog.csv   # Catalog items
│   ├── department_budgets.csv # Budget allocations
│   ├── vendor_risk.json       # Mock API data
│   └── procurement_policy.md  # Policy specification (v2026.09)
│
├── docs/                      # Documentation
│   └── ARCHITECTURE_DECISION_MEMO.md
│
├── evals/                     # Evaluation harness
│   ├── public_cases.json      # 6 public test cases
│   ├── run_public_evals.py    # Evaluation runner
│   ├── results_single.csv     # Architecture A results
│   └── results_staged.csv     # Architecture B results
│
├── mock_api/                  # External service simulation
│   └── app.py                 # FastAPI service simulating 503 outages
│
├── src/                       # Application code
│   ├── solution.py            # handle_request adapter (Arch A & B)
│   ├── contracts.py           # Pydantic data contracts
│   ├── data_access.py         # CSV/JSON loaders
│   ├── vendor_client.py       # Vendor API client
│   ├── telemetry.py           # Call and latency counter
│   └── tools/                 # Deterministic policy tools
│       ├── budget_tool.py     # Budget balance check
│       ├── catalog_tool.py    # Overlap detection
│       ├── vendor_risk_tool.py# 365-day expiry and 503 handling
│       └── policy_engine.py   # Tier validation & prompt injection filter
│
├── templates/
│   └── architecture_decision.md
│
└── tests/                     # Test suite
    ├── test_data_integrity.py
    ├── test_mock_api.py
    └── test_solution.py       # 7 end-to-end and unit test cases
```
