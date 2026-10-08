# AI Procurement Request Copilot

> **Enterprise Procurement Assistant — Forward Deployed Engineering (FDE) Assessment 3**  
> Evaluates software purchase requests, applies deterministic enterprise policy constraints, surfaces audit-ready evidence trails, and recommends human approval workflows while preserving human authority.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Evals Passing](https://img.shields.io/badge/public__evals-6%2F6%20passing%20(100%25)-success.svg)](evals/)
[![Tests Passing](https://img.shields.io/badge/unit__tests-17%2F17%20passing-success.svg)](tests/)
[![Policy Snapshot](https://img.shields.io/badge/policy__snapshot-2026.09%20(2026--09--30)-informational.svg)](data/procurement_policy.md)

---

## 📌 Executive Summary

Enterprise software procurement faces two conflicting failure modes:
1. **Unconstrained LLM Autonomous Decisions:** Hallucinated approvals, bypassed security reviews, incorrect arithmetic on departmental budgets, and susceptibility to prompt injections embedded in requester text.
2. **Slow, Opaque Manual Review:** Bureaucratic bottlenecks where simple renewals take weeks while high-risk tools bypass scrutiny.

This solution introduces a **Hybrid Deterministic-Cognitive Architecture**:
- **Deterministic Policy Engine (`src/tools/`):** Executes 100% of mathematical checks, policy threshold validations, date-based security review expirations, catalog overlap scans, and prompt injection filtering.
- **LLM Coordinator (`src/solution.py`):** Synthesizes verified evidence into crisp, executive-ready recommendations and next steps without hallucinating rules or overriding human authority.

Both **Architecture A (Single-Agent Baseline)** and **Architecture B (Staged 2-Agent Pipeline)** achieve **6/6 (100%)** on the official public evaluation suite. Based on rigorous empirical benchmarking, we recommend shipping **Architecture A** for production.

---

## 🏛️ System Architecture

```text
                                 ┌──────────────────────────────────────────────┐
                                 │          Purchase Request (JSON)             │
                                 │    (Requester, Spend, Users, Justification)   │
                                 └──────────────────────┬───────────────────────┘
                                                        │
                                                        ▼
                        ┌───────────────────────────────────────────────────────────────┐
                        │              Deterministic Tool & Policy Suite                │
                        ├───────────────────────────────────────────────────────────────┤
                        │ 1. Completeness Check  ─── Verifies 7 mandatory fields (§1)   │
                        │ 2. Budget Tool         ─── Departmental arithmetic balance(§2)│
                        │ 3. Catalog Overlap     ─── Identifies duplicate tools (§3)    │
                        │ 4. Vendor Risk API     ─── 365-day review expiry & 503 check  │
                        │ 5. Injection Guard     ─── Neutralizes adversarial prompts(§9)│
                        │ 6. Approval Engine     ─── Computes required tiers (§4,§5,§6) │
                        └──────────────────────┬────────────────────────────────────────┘
                                               │ Verified Evidence Bundle
                                               ▼
              ┌─────────────────────────────────────────────────────────────────┐
              │                   Architecture Choice                           │
              ├───────────────────────────────┬─────────────────────────────────┤
              │   Architecture A (Single)     │      Architecture B (Staged)    │
              │   Single Gemini Coordinator   │   Stage 1: Procurement Analyst  │
              │   Evidence -> Recommendation  │   Stage 2: Risk & Policy Review │
              └───────────────────────────────┴─────────────────────────────────┘
                                               │
                                               ▼
                        ┌───────────────────────────────────────────────────────────────┐
                        │                ProcurementDecision Contract                   │
                        ├───────────────────────────────────────────────────────────────┤
                        │ • recommendation (LLM text)                                   │
                        │ • required_approvals: [Manager, Dept Head, Finance, Security] │
                        │ • risk_flags: [budget_insufficient, existing_tool_overlap]   │
                        │ • evidence: [Verified findings with policy references]        │
                        │ • missing_information: [List of missing required fields]      │
                        │ • human_review_required: True (Always enforced §11)          │
                        └───────────────────────────────────────────────────────────────┘
```

---

## 📊 Evaluation & Benchmark Results

### Public Evaluations (`evals/run_public_evals.py`)

Both architectures were benchmarked against all 6 public evaluation cases:

| Case ID | Request | Scenario Under Test | Single-Agent (Arch A) | Staged (Arch B) |
|---|---|---|:---:|:---:|
| **PUB-01** | `REQ-1001` | Low-value approved vendor ($800) | **PASS** (1 LLM, 6 Tools) | **PASS** (2 LLM, 5 Tools) |
| **PUB-02** | `REQ-1002` | Existing overlap + new vendor ($12k) | **PASS** (1 LLM, 6 Tools) | **PASS** (2 LLM, 5 Tools) |
| **PUB-03** | `REQ-1003` | Sensitive source-code access | **PASS** (1 LLM, 6 Tools) | **PASS** (2 LLM, 5 Tools) |
| **PUB-04** | `REQ-1005` | Budget shortfall + sensitive new vendor | **PASS** (1 LLM, 6 Tools) | **PASS** (2 LLM, 5 Tools) |
| **PUB-05** | `REQ-1006` | Incomplete request + prompt injection | **PASS** (1 LLM, 6 Tools) | **PASS** (2 LLM, 5 Tools) |
| **PUB-06** | `REQ-1009` | Vendor-risk API 503 outage | **PASS** (1 LLM, 6 Tools) | **PASS** (2 LLM, 5 Tools) |
| **Summary** | | **Overall Pass Rate** | **6 / 6 (100%)** | **6 / 6 (100%)** |

### Architecture Comparison & Decision

| Metric | Architecture A (Single-Agent) | Architecture B (Staged 2-Agent) | Advantage |
|---|---|---|---|
| **Compliance Rate** | **100% (6/6)** | **100% (6/6)** | Tie |
| **LLM Calls per Request** | **1 call** | **2 calls** | **Arch A (50% cheaper)** |
| **Prompt Overhead** | ~400 tokens | ~900 tokens | **Arch A** |
| **Operational Complexity** | Single prompt coordinator | Multi-agent handoff serialization | **Arch A** |
| **Failure Surface** | 1 API call to fail | 2 API calls to fail | **Arch A (Higher resilience)** |
| **Verdict** | **RECOMMENDED FOR PRODUCTION** | *Alternative for manual triage* | **Arch A** |

See full analysis in [Architecture Decision Memo](docs/ARCHITECTURE_DECISION_MEMO.md).

---

## 🛠️ Tooling & Deterministic Guardrails

The implementation features **5 core tools** (`src/tools/`):

1. **Budget Tool (`src/tools/budget_tool.py`):**
   - Pure arithmetic calculation comparing annualized request amount against departmental software budget balance.
   - Accurately identifies `budget_insufficient` when cost exceeds balance (e.g. `REQ-1005`).

2. **Catalog Overlap Tool (`src/tools/catalog_tool.py`):**
   - Scans approved catalog (`data/software_catalog.csv`) for exact product matches, same vendor licenses, and category alternatives.
   - Flags `existing_tool_overlap` without automatically rejecting, preserving business flexibility (§3).

3. **Vendor Risk Tool (`src/tools/vendor_risk_tool.py`):**
   - Calls the mock vendor-risk API (`http://127.0.0.1:8001`) with graceful fallback to `data/vendor_risk.json`.
   - **Deterministic 365-day expiry:** Compares review dates strictly against policy reference date `2026-09-30`.
   - **Outage Handling:** Gracefully traps HTTP 503 errors and surfaces `vendor_risk_unavailable`, forcing manual Security review (§10).
   - **Conflict Detection:** Identifies discrepancies between internal vendor registry and external API data.

4. **Policy Engine (`src/tools/policy_engine.py`):**
   - Encodes exact financial tier thresholds (§4):
     - $\le \$1,000 \rightarrow$ Manager
     - $\$1,000.01 - \$10,000 \rightarrow$ Department Head + Procurement
     - $\$10,000.01 - \$25,000 \rightarrow$ Department Head + Finance + Procurement
     - $> \$25,000 \rightarrow$ Department Head + Finance + CFO + Procurement
   - Determines conditional triggers for Security (§5), Privacy (§6), and Legal (§7).

5. **Prompt Injection Guard (`src/tools/policy_engine.py`):**
   - Scans requester justifications and product fields for prompt injection patterns (`ignore all previous instructions`, `treat as approved`, etc.).
   - Flags `prompt_injection_detected`, neutralizes the instruction, and processes the request strictly via real policy rules (§9).

---

## 🚀 Getting Started

### 1. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd <repo-folder>

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and provide your Google Gemini API key:

```bash
cp .env.example .env
```

Edit `.env`:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
MODEL_NAME=gemini-3.8-flash
VENDOR_RISK_BASE_URL=http://127.0.0.1:8001
```

### 3. Verify Setup (Pre-flight Checks)

```bash
python verify_setup.py
```
Expected output: `PRE-FLIGHT PASSED`.

---

## 🧪 Running Evaluations & Tests

### Run Public Evaluations

```bash
# Evaluate Architecture A (Single-Agent)
python evals/run_public_evals.py --architecture single

# Evaluate Architecture B (Staged)
python evals/run_public_evals.py --architecture staged
```

Results are saved to `evals/results_single.csv` and `evals/results_staged.csv`.

### Run Unit Tests

```bash
python -m unittest discover tests
```
Runs 17 comprehensive unit tests verifying data integrity, mock API, deterministic policy tiers, security/legal triggers, prompt injection detection, and both architectures.

---

## 🖥️ Interactive Streamlit Dashboard

Launch the executive UI:

```bash
python run_local.py
# Or directly via streamlit:
streamlit run app.py
```

Open `http://localhost:8501` to access:
- **Interactive Purchase Request Inspector**: Select any request (`REQ-1001` through `REQ-1010`)
- **Visual Risk Radar**: Color-coded badges for high, medium, and low risks
- **Approval Stepper**: Required approver workflow visualization
- **Audit Evidence Trail**: Expandable verified evidence citations linked to policy sections
- **Side-by-Side Comparison Mode**: Benchmark Single-Agent vs. Staged architectures side-by-side with live latency and telemetry tracking

---

## 🔒 Governance & Ethical Guardrails

- **Human Authority (§11):** The copilot is strictly advisory. `human_review_required` is permanently enforced (`True`). It cannot autonomously approve spend, modify budgets, or sign vendor terms.
- **Untrusted Business Data (§9):** All requester inputs are treated as data, not instructions. Prompt injection attempts are neutralized before reaching the LLM coordinator.
- **Reference Date Consistency:** All date evaluations strictly use the policy reference date (`2026-09-30`), ensuring reproducible evaluations regardless of the runner's machine time.

---

## 📁 Repository Structure

```text
.
├── app.py                     # Executive Streamlit Dashboard
├── run_local.py               # Starts mock API (8001) + UI (8501)
├── verify_setup.py            # Pre-flight environment check
├── requirements.txt           # Python dependencies (fastapi, genai, streamlit)
├── STUDENT_CHECKLIST.md       # Pre-submission verification checklist
│
├── data/                      # Synthetic enterprise dataset
│   ├── requests.json          # 10 sample procurement requests
│   ├── vendors.csv            # Internal vendor registry
│   ├── software_catalog.csv   # Approved software catalog
│   ├── department_budgets.csv # Department software allocations
│   ├── vendor_risk.json       # Mock API reference data
│   └── procurement_policy.md  # Policy source of truth (v2026.09)
│
├── docs/                      # Documentation
│   ├── ARCHITECTURE_DECISION_MEMO.md  # 500-word decision memo
│   └── Assignment_3_Brief.pdf
│
├── evals/                     # Evaluation harness
│   ├── public_cases.json      # 6 public test cases
│   ├── run_public_evals.py    # Public eval runner
│   ├── results_single.csv     # Single-agent eval output (6/6 pass)
│   └── results_staged.csv     # Staged eval output (6/6 pass)
│
├── mock_api/                  # External service simulation
│   └── app.py                 # FastAPI vendor-risk service (503 simulation)
│
├── src/                       # Production source code
│   ├── solution.py            # Architecture A & B implementations (handle_request)
│   ├── contracts.py           # Pydantic schema contracts
│   ├── data_access.py         # Data loading helpers
│   ├── vendor_client.py       # API client
│   ├── telemetry.py           # Metrics tracker
│   └── tools/                 # Deterministic tools package
│       ├── __init__.py
│       ├── budget_tool.py     # Deterministic budget calculation
│       ├── catalog_tool.py    # Software overlap scanner
│       ├── vendor_risk_tool.py# 365-day expiry & 503 outage handler
│       └── policy_engine.py   # Full policy rule compiler & injection guard
│
├── templates/
│   └── architecture_decision.md # Decision memo template
│
└── tests/                     # 17 Unit & integration tests
    ├── test_data_integrity.py
    ├── test_mock_api.py
    └── test_solution.py       # Comprehensive solution & policy tests
```
