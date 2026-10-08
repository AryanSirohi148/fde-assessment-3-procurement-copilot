"""
Tool 1 (Deterministic): Budget Check
Compares the request's annual cost against the department's available software budget.
No LLM — pure arithmetic from the CSV data.
"""
from __future__ import annotations

from src.data_access import load_budgets, load_employees, get_request
from src.contracts import EvidenceItem


def check_budget(request_id: str) -> dict:
    """
    Returns a dict with:
      - within_budget (bool)
      - annual_cost_usd (float | None)
      - available_usd (float)
      - department (str)
      - evidence (EvidenceItem)
      - risk_flags (list[str])
    """
    req = get_request(request_id)
    employees = load_employees()
    budgets = load_budgets()

    # Resolve requester → department
    emp = employees[employees["employee_id"] == req["requester_id"]]
    if emp.empty:
        return {
            "within_budget": False,
            "annual_cost_usd": None,
            "available_usd": 0,
            "department": "Unknown",
            "evidence": EvidenceItem(
                source="budget_tool",
                finding="Requester employee ID not found in employee records.",
                reference=req["requester_id"],
            ),
            "risk_flags": ["missing_information"],
        }

    department = emp.iloc[0]["department"]

    # Get department budget row
    budget_row = budgets[budgets["department"] == department]
    if budget_row.empty:
        return {
            "within_budget": False,
            "annual_cost_usd": req.get("annual_cost_usd"),
            "available_usd": 0,
            "department": department,
            "evidence": EvidenceItem(
                source="budget_tool",
                finding=f"No budget record found for department: {department}.",
                reference=department,
            ),
            "risk_flags": ["missing_information"],
        }

    available = float(budget_row.iloc[0]["available_usd"])
    annual_budget = float(budget_row.iloc[0]["annual_software_budget_usd"])
    committed = float(budget_row.iloc[0]["committed_usd"])

    annual_cost = req.get("annual_cost_usd")

    # Missing cost — cannot do budget check
    if annual_cost is None:
        return {
            "within_budget": None,
            "annual_cost_usd": None,
            "available_usd": available,
            "department": department,
            "evidence": EvidenceItem(
                source="budget_tool",
                finding=(
                    f"{department} has ${available:,.0f} available of "
                    f"${annual_budget:,.0f} annual budget. "
                    "Request annual cost is missing — budget check cannot be completed."
                ),
                reference=f"department_budgets.csv:{department}",
            ),
            "risk_flags": ["missing_information"],
        }

    annual_cost = float(annual_cost)
    within_budget = annual_cost <= available

    finding = (
        f"Request annual cost ${annual_cost:,.0f}. "
        f"{department} available budget: ${available:,.0f} "
        f"(Annual: ${annual_budget:,.0f} − Committed: ${committed:,.0f}). "
        f"{'Within budget.' if within_budget else 'EXCEEDS available budget.'}"
    )

    return {
        "within_budget": within_budget,
        "annual_cost_usd": annual_cost,
        "available_usd": available,
        "department": department,
        "evidence": EvidenceItem(
            source="budget_tool",
            finding=finding,
            reference=f"department_budgets.csv:{department}",
        ),
        "risk_flags": [] if within_budget else ["budget_insufficient"],
    }
