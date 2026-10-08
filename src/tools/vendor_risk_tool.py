"""
Tool 3 (External API + Deterministic): Vendor Risk Check
Calls the mock vendor-risk API and applies deterministic 365-day expiry logic.
Handles:
  - HTTP 503 outages → vendor_risk_unavailable flag
  - Expired reviews (>365 days from policy ref date 2026-09-30)
  - not_completed reviews
  - Conflicting internal vs. external evidence
"""
from __future__ import annotations

from datetime import date, timedelta

import requests

from src.data_access import load_vendors, get_request
from src.contracts import EvidenceItem
from src.vendor_client import get_vendor_risk

# Policy reference date — NEVER use runtime date
POLICY_REFERENCE_DATE = date(2026, 9, 30)
SECURITY_REVIEW_VALIDITY_DAYS = 365


def _is_review_current(last_review_date_str: str | None) -> bool:
    """Returns True if the review is within the 365-day validity window."""
    if not last_review_date_str:
        return False
    try:
        review_date = date.fromisoformat(last_review_date_str)
        cutoff = POLICY_REFERENCE_DATE - timedelta(days=SECURITY_REVIEW_VALIDITY_DAYS)
        return review_date >= cutoff
    except ValueError:
        return False


def check_vendor_risk(request_id: str) -> dict:
    """
    Returns a dict with:
      - api_available (bool)
      - vendor_name (str)
      - risk_level (str | None)
      - security_review_status (str | None)
      - review_current (bool)
      - processes_personal_data (bool)
      - stores_data_outside_region (bool)
      - is_new_vendor (bool)
      - evidence (EvidenceItem)
      - risk_flags (list[str])
    """
    req = get_request(request_id)
    vendor_name = req.get("vendor_name", "")

    # Check if vendor exists in internal vendor registry
    vendors_df = load_vendors()
    internal_vendor = vendors_df[
        vendors_df["vendor_name"].str.lower() == vendor_name.lower()
    ]
    is_new_vendor = internal_vendor.empty

    risk_flags = []

    # --- Call the external vendor-risk API ---
    try:
        api_data = get_vendor_risk(vendor_name)
        api_available = True
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 503:
            risk_flags.append("vendor_risk_unavailable")
            return {
                "api_available": False,
                "vendor_name": vendor_name,
                "risk_level": None,
                "security_review_status": None,
                "review_current": False,
                "processes_personal_data": None,
                "stores_data_outside_region": None,
                "is_new_vendor": is_new_vendor,
                "evidence": EvidenceItem(
                    source="vendor_risk_tool",
                    finding=(
                        f"Vendor-risk API returned 503 for '{vendor_name}'. "
                        "Security assessment cannot be verified. "
                        "Route to manual Security review — do not infer a favorable status."
                    ),
                    reference=f"mock_api:/vendor-risk/{vendor_name}",
                ),
                "risk_flags": ["vendor_risk_unavailable", "security_review_required"],
            }
        raise
    except Exception:
        risk_flags.append("vendor_risk_unavailable")
        return {
            "api_available": False,
            "vendor_name": vendor_name,
            "risk_level": None,
            "security_review_status": None,
            "review_current": False,
            "processes_personal_data": None,
            "stores_data_outside_region": None,
            "is_new_vendor": is_new_vendor,
            "evidence": EvidenceItem(
                source="vendor_risk_tool",
                finding=(
                    f"Vendor-risk API unavailable for '{vendor_name}'. "
                    "Cannot verify security assessment. Manual review required."
                ),
                reference=f"mock_api:/vendor-risk/{vendor_name}",
            ),
            "risk_flags": ["vendor_risk_unavailable", "security_review_required"],
        }

    # --- Parse API response ---
    risk_level = api_data.get("risk_level")
    security_status = api_data.get("security_review_status")
    last_review_date = api_data.get("last_review_date")
    processes_pii = api_data.get("processes_personal_data", False)
    stores_outside = api_data.get("stores_data_outside_region", False)
    api_notes = api_data.get("notes", "")

    # Deterministic: check 365-day validity
    review_current = _is_review_current(last_review_date)

    # --- Conflict detection: internal catalog vs. API ---
    internal_security_status = None
    if not internal_vendor.empty:
        internal_security_status = str(internal_vendor.iloc[0].get("security_review_status", "")).lower()

    conflict_detected = False
    if internal_security_status and security_status:
        # If internal says approved but API says not_completed or vice versa
        internal_ok = "approved" in internal_security_status
        api_ok = security_status == "approved"
        if internal_ok != api_ok:
            conflict_detected = True
            risk_flags.append("conflicting_vendor_evidence")

    # --- Build risk flags ---
    if security_status in ("not_completed", "expired") or not review_current:
        if security_status == "expired" or not review_current:
            risk_flags.append("vendor_review_expired")

    # Build a human-readable finding
    review_date_str = last_review_date or "never"
    days_since = None
    if last_review_date:
        try:
            rd = date.fromisoformat(last_review_date)
            days_since = (POLICY_REFERENCE_DATE - rd).days
        except ValueError:
            pass

    days_info = f" ({days_since} days before policy ref date)" if days_since is not None else ""
    current_str = "CURRENT" if review_current else "EXPIRED/MISSING"

    finding = (
        f"Vendor '{vendor_name}': risk={risk_level}, "
        f"security_review={security_status} ({current_str}), "
        f"last_reviewed={review_date_str}{days_info}. "
        f"PII processed: {processes_pii}. "
        f"Data outside region: {stores_outside}. "
        f"Notes: {api_notes}"
    )

    if conflict_detected:
        finding += " [WARNING: Internal registry and vendor-risk API disagree on security status.]"

    if is_new_vendor:
        finding += " [NEW VENDOR: Not in internal vendor registry.]"

    return {
        "api_available": api_available,
        "vendor_name": vendor_name,
        "risk_level": risk_level,
        "security_review_status": security_status,
        "review_current": review_current,
        "processes_personal_data": processes_pii,
        "stores_data_outside_region": stores_outside,
        "is_new_vendor": is_new_vendor,
        "evidence": EvidenceItem(
            source="vendor_risk_tool",
            finding=finding,
            reference=f"mock_api:/vendor-risk/{vendor_name}",
        ),
        "risk_flags": risk_flags,
    }
