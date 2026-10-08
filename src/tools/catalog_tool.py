"""
Tool 2 (Deterministic): Software Catalog Overlap Check
Scans the approved software catalog for:
  - exact product/vendor match
  - same category tools
  - vendor already present in catalog
No LLM — pure string/category matching against catalog CSV.
"""
from __future__ import annotations

from src.data_access import load_software_catalog, get_request
from src.contracts import EvidenceItem


def check_catalog_overlap(request_id: str) -> dict:
    """
    Returns a dict with:
      - has_overlap (bool)
      - overlapping_products (list[dict])
      - evidence (EvidenceItem)
      - risk_flags (list[str])
    """
    req = get_request(request_id)
    catalog = load_software_catalog()

    requested_product = (req.get("product_name") or "").lower().strip()
    requested_vendor = (req.get("vendor_name") or "").lower().strip()
    requested_category = (req.get("category") or "").lower().strip()

    overlapping = []

    for _, row in catalog.iterrows():
        cat_product = str(row.get("product_name", "")).lower().strip()
        cat_vendor = str(row.get("vendor_name", "")).lower().strip()
        cat_category = str(row.get("category", "")).lower().strip()
        cat_status = str(row.get("status", "")).strip()

        reasons = []

        # Exact product name match
        if requested_product and requested_product in cat_product:
            reasons.append("exact product match")

        # Vendor already in catalog
        if requested_vendor and requested_vendor == cat_vendor:
            reasons.append("same vendor already licensed")

        # Same functional category
        if requested_category and requested_category == cat_category:
            reasons.append("same software category")

        if reasons:
            overlapping.append({
                "software_id": row.get("software_id", ""),
                "product_name": row.get("product_name", ""),
                "vendor_name": row.get("vendor_name", ""),
                "category": row.get("category", ""),
                "status": cat_status,
                "licensed_seats": row.get("licensed_seats", ""),
                "scope": row.get("scope", ""),
                "notes": row.get("notes", ""),
                "overlap_reasons": reasons,
            })

    has_overlap = len(overlapping) > 0

    if has_overlap:
        overlap_summary = "; ".join(
            f"{p['product_name']} ({p['status']}, {p['licensed_seats']} seats) — "
            f"{', '.join(p['overlap_reasons'])}"
            for p in overlapping
        )
        finding = (
            f"Found {len(overlapping)} existing catalog item(s) that may satisfy this need: "
            f"{overlap_summary}. Review whether existing capacity can be used before approving new purchase."
        )
    else:
        finding = (
            f"No existing catalog items found for product '{req.get('product_name')}', "
            f"vendor '{req.get('vendor_name')}', or category '{req.get('category')}'. "
            "No overlap detected."
        )

    return {
        "has_overlap": has_overlap,
        "overlapping_products": overlapping,
        "evidence": EvidenceItem(
            source="catalog_tool",
            finding=finding,
            reference="data/software_catalog.csv",
        ),
        "risk_flags": ["existing_tool_overlap"] if has_overlap else [],
    }
