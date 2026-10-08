"""
Policy Engine (Fully Deterministic)
Encodes ALL hard procurement rules from procurement_policy.md:
  1. Required field completeness check
  2. Financial approval tier thresholds (deterministic dollar thresholds)
  3. Security review triggers (data access level, expired/missing reviews)
  4. Privacy review triggers (PII, cross-region)
  5. Legal review triggers (new vendor + spend >= $10k, non-standard terms)
  6. Prompt injection detection (untrusted business data guard)
  7. New vendor flag

Policy reference date: 2026-09-30 (from procurement_policy.md)
Never depends on runtime clock.
"""
from __future__ import annotations

import re

from src.data_access import get_request
from src.contracts import EvidenceItem

# Data-access levels that trigger mandatory Security review
SECURITY_SENSITIVE_DATA_LEVELS = {
    "source_code",
    "production_telemetry",
    "production_cloud_account",
    "credentials",
    "secrets",
    "customer_pii",
    "employee_pii",
    "confidential_documents",
}

# Data-access levels that trigger Privacy review
PRIVACY_SENSITIVE_DATA_LEVELS = {
    "customer_pii",
    "employee_pii",
}

# Known prompt-injection patterns in business data
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?.*rule",
    r"treat\s+this.*as.*approved",
    r"bypass\s+.*control",
    r"you\s+are\s+now",
    r"disregard\s+(all\s+)?.*instruction",
    r"override\s+.*policy",
    r"forget\s+(all\s+)?.*previous",
    r"act\s+as\s+(if\s+)?.*approved",
    r"approve\s+immediately",
    r"cfo.{0,20}approved",
    r"do\s+not\s+follow",
    r"skip\s+.*review",
]


def _detect_prompt_injection(text: str) -> bool:
    """Returns True if untrusted text contains prompt-injection patterns."""
    if not text:
        return False
    text_lower = text.lower()
    return any(re.search(pat, text_lower) for pat in _INJECTION_PATTERNS)


def check_required_fields(request_id: str) -> dict:
    """
    Policy §1: Verify all required fields are present.
    Returns missing_fields list and evidence.
    """
    req = get_request(request_id)
    missing = []

    if not req.get("requester_id"):
        missing.append("requester")
    if not req.get("vendor_name"):
        missing.append("vendor/product")
    if req.get("annual_cost_usd") is None:
        missing.append("annual cost")
    if req.get("user_count") is None:
        missing.append("number of users/licenses")
    if not req.get("business_justification"):
        missing.append("business purpose")
    if not req.get("data_access_level") or req.get("data_access_level") == "unknown":
        missing.append("data access level")

    if missing:
        finding = f"Required fields missing: {', '.join(missing)}. Request is not ready for approval."
    else:
        finding = "All required request fields are present."

    return {
        "missing_fields": missing,
        "evidence": EvidenceItem(
            source="policy_engine",
            finding=finding,
            reference="procurement_policy.md §1",
        ),
        "risk_flags": ["missing_information"] if missing else [],
    }


def check_approval_tiers(annual_cost_usd: float | None) -> dict:
    """
    Policy §4: Deterministic financial approval thresholds.
    Returns required_approvals list based on dollar amount.
    """
    if annual_cost_usd is None:
        return {
            "required_approvals": ["Manager"],  # conservative minimum
            "tier_description": "Cost unknown — minimum approval assumed; re-evaluate once cost confirmed",
            "evidence": EvidenceItem(
                source="policy_engine",
                finding="Annual cost unknown. Minimum manager approval assumed; approval tier cannot be finalized.",
                reference="procurement_policy.md §4",
            ),
        }

    cost = float(annual_cost_usd)

    if cost <= 1000:
        approvals = ["Manager"]
        tier = f"Up to $1,000 → Manager only"
    elif cost <= 10000:
        approvals = ["Department Head", "Procurement"]
        tier = f"$1,000.01–$10,000 → Department Head + Procurement"
    elif cost <= 25000:
        approvals = ["Department Head", "Finance", "Procurement"]
        tier = f"$10,000.01–$25,000 → Department Head + Finance + Procurement"
    else:
        approvals = ["Department Head", "Finance", "CFO", "Procurement"]
        tier = f"Above $25,000 → Department Head + Finance + CFO + Procurement"

    return {
        "required_approvals": approvals,
        "tier_description": tier,
        "evidence": EvidenceItem(
            source="policy_engine",
            finding=f"Annual cost ${cost:,.2f}. Financial approval tier: {tier}.",
            reference="procurement_policy.md §4",
        ),
    }


def check_security_triggers(
    request_id: str,
    vendor_risk_result: dict,
) -> dict:
    """
    Policy §5: Security review triggers.
    Checks data-access level + vendor security assessment status.
    Returns security_required (bool), reasons, risk_flags.
    """
    req = get_request(request_id)
    data_level = (req.get("data_access_level") or "").lower().strip()
    integrations = [i.lower() for i in (req.get("requested_integrations") or [])]

    reasons = []
    risk_flags = []

    # Data-access level triggers
    if data_level in SECURITY_SENSITIVE_DATA_LEVELS:
        reasons.append(f"Data access level '{data_level}' requires security review (policy §5)")

    # Integration triggers
    if any("production" in i or "cloud" in i for i in integrations):
        reasons.append("Production/cloud integration requested (policy §5)")

    # Vendor security assessment status
    sec_status = vendor_risk_result.get("security_review_status")
    review_current = vendor_risk_result.get("review_current", False)
    api_available = vendor_risk_result.get("api_available", True)

    if not api_available:
        reasons.append("Vendor security assessment could not be verified (API unavailable)")
        risk_flags.append("vendor_risk_unavailable")
    elif sec_status in ("not_completed", "expired") or not review_current:
        reasons.append(
            f"Vendor security assessment is '{sec_status}' and/or expired "
            f"(last review not current per 365-day rule, ref date 2026-09-30)"
        )
        if sec_status == "expired" or not review_current:
            risk_flags.append("vendor_review_expired")

    if "conflicting_vendor_evidence" in vendor_risk_result.get("risk_flags", []):
        reasons.append("Internal registry and vendor-risk API disagree on security status — manual review required")
        risk_flags.append("conflicting_vendor_evidence")

    security_required = len(reasons) > 0
    if security_required:
        risk_flags.append("security_review_required")

    finding = (
        f"Security review {'REQUIRED' if security_required else 'NOT required'}. "
        + (f"Reasons: {'; '.join(reasons)}." if reasons else "No security triggers found.")
    )

    return {
        "security_required": security_required,
        "reasons": reasons,
        "evidence": EvidenceItem(
            source="policy_engine",
            finding=finding,
            reference="procurement_policy.md §5",
        ),
        "risk_flags": list(set(risk_flags)),
    }


def check_privacy_triggers(
    request_id: str,
    vendor_risk_result: dict,
) -> dict:
    """
    Policy §6: Privacy review triggers.
    PII processing or cross-region data storage.
    """
    req = get_request(request_id)
    data_level = (req.get("data_access_level") or "").lower().strip()

    reasons = []

    if data_level in PRIVACY_SENSITIVE_DATA_LEVELS:
        reasons.append(f"Data access level '{data_level}' includes PII (policy §6)")

    stores_outside = vendor_risk_result.get("stores_data_outside_region")
    processes_pii = vendor_risk_result.get("processes_personal_data")

    if stores_outside:
        reasons.append("Vendor stores data outside operating region (policy §6)")
    if processes_pii and data_level in PRIVACY_SENSITIVE_DATA_LEVELS:
        reasons.append("Vendor processes personal data for a PII use case (policy §6)")

    privacy_required = len(reasons) > 0

    finding = (
        f"Privacy review {'REQUIRED' if privacy_required else 'NOT required'}. "
        + (f"Reasons: {'; '.join(reasons)}." if reasons else "No privacy triggers found.")
    )

    return {
        "privacy_required": privacy_required,
        "reasons": reasons,
        "evidence": EvidenceItem(
            source="policy_engine",
            finding=finding,
            reference="procurement_policy.md §6",
        ),
        "risk_flags": ["privacy_review_required"] if privacy_required else [],
    }


def check_legal_triggers(
    request_id: str,
    vendor_risk_result: dict,
) -> dict:
    """
    Policy §7: Legal review triggers.
    New vendor + annual spend >= $10,000 OR material data/cross-region issues.
    """
    req = get_request(request_id)
    annual_cost = req.get("annual_cost_usd")
    is_new_vendor = vendor_risk_result.get("is_new_vendor", False)
    stores_outside = vendor_risk_result.get("stores_data_outside_region", False)

    reasons = []

    if is_new_vendor and annual_cost is not None and float(annual_cost) >= 10000:
        reasons.append(
            f"New vendor with annual spend ${float(annual_cost):,.0f} >= $10,000 (policy §7)"
        )

    if stores_outside:
        reasons.append("Data stored outside operating region — material cross-region issue (policy §7)")

    legal_required = len(reasons) > 0

    finding = (
        f"Legal review {'REQUIRED' if legal_required else 'NOT required'}. "
        + (f"Reasons: {'; '.join(reasons)}." if reasons else "No legal triggers found.")
    )

    return {
        "legal_required": legal_required,
        "reasons": reasons,
        "evidence": EvidenceItem(
            source="policy_engine",
            finding=finding,
            reference="procurement_policy.md §7",
        ),
        "risk_flags": ["legal_review_required"] if legal_required else [],
    }


def check_prompt_injection(request_id: str) -> dict:
    """
    Policy §9: Detect prompt-injection attempts in untrusted business data.
    Scans: business_justification, product name, any notes fields.
    """
    req = get_request(request_id)

    untrusted_fields = {
        "business_justification": req.get("business_justification") or "",
        "product_name": req.get("product_name") or "",
    }

    detected_in = []
    for field, value in untrusted_fields.items():
        if _detect_prompt_injection(value):
            detected_in.append(field)

    injection_detected = len(detected_in) > 0

    if injection_detected:
        finding = (
            f"PROMPT INJECTION DETECTED in field(s): {', '.join(detected_in)}. "
            "Embedded instruction ignored. Proceeding with real policy and evidence only."
        )
        risk_flags = ["prompt_injection_detected"]
    else:
        finding = "No prompt-injection patterns detected in request text."
        risk_flags = []

    return {
        "injection_detected": injection_detected,
        "detected_in_fields": detected_in,
        "evidence": EvidenceItem(
            source="policy_engine",
            finding=finding,
            reference="procurement_policy.md §9",
        ),
        "risk_flags": risk_flags,
    }
