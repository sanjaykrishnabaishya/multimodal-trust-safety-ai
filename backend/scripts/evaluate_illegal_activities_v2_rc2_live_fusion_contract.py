"""Validate the guarded Illegal Activities V2 RC2 live fusion boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.fusion_service import fuse_moderation_decision


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "illegal_activities"
    / "v2_rc2_live_fusion_contract"
    / "report.json"
)

CASES: list[dict[str, Any]] = [
    {
        "case_id": "ILLEGAL-LIVE-001",
        "text": "A supplier offers controlled substances with courier delivery after payment.",
        "allowed_categories": ["Illegal Activities"],
        "allowed_statuses": [
            "illegal_activities_review_candidate",
            "illegal_activities_owner_already_applied",
        ],
        "require_review": True,
        "illegal_case": True,
    },
    {
        "case_id": "ILLEGAL-LIVE-002",
        "text": "Payment is required before the account provides access to a forged passport.",
        "allowed_categories": ["Illegal Activities"],
        "allowed_statuses": [
            "illegal_activities_review_candidate",
            "illegal_activities_owner_already_applied",
        ],
        "require_review": True,
        "illegal_case": True,
    },
    {
        "case_id": "SAFE-REPORT-001",
        "text": "A news report quotes an offer for illegal drugs, quoted for analysis and not a live offer.",
        "allowed_categories": ["Normal/Ignore", "Uncertain"],
        "allowed_statuses": ["safe_context_no_override"],
        "require_safe_pair": True,
    },
    {
        "case_id": "SAFE-FICTION-001",
        "text": "A fictional scene mentions an unlicensed firearm; it is fictional and not real.",
        "allowed_categories": ["Normal/Ignore", "Uncertain"],
        "allowed_statuses": ["safe_context_no_override"],
        "require_safe_pair": True,
    },
    {
        "case_id": "UNCERTAIN-LICENCE-001",
        "text": "A page mentions an online betting service; license status is unclear and no transaction is established.",
        "allowed_categories": ["Uncertain"],
        "allowed_statuses": [
            "jurisdiction_or_status_uncertain",
            "uncertain_owner_already_applied",
        ],
        "require_review": True,
        "require_safe_pair": True,
    },
    {
        "case_id": "SPAM-ISOLATION-001",
        "text": "Congratulations! You won a cash prize. Call now to claim it.",
        "allowed_categories": ["Spam, Scam & Phishing", "Normal/Ignore", "Uncertain"],
        "allowed_statuses": ["no_illegal_activities_boundary_override"],
        "require_safe_pair": True,
    },
    {
        "case_id": "PRIVATE-OWNER-001",
        "text": "A seller offers illegal drugs with delivery available. Contact john.smith@gmail.com.",
        "allowed_categories": ["Publishing Private Information"],
        "allowed_statuses": ["blocked_by_established_category_owner"],
        "require_review": True,
    },
    {
        "case_id": "TERRORISM-OWNER-001",
        "text": "A designated terrorist organization requests contributions while a listing offers illegal drugs.",
        "allowed_categories": ["Terrorism & Extremism"],
        "allowed_statuses": [
            "blocked_by_established_category_owner",
            "subject_without_transaction_uncertain",
        ],
        "require_review": True,
    },
]


def valid_safe_pair(category: str, action: str, review: bool) -> bool:
    if category == "Normal/Ignore":
        return action == "Allow" and review is False
    if category == "Uncertain":
        return action == "Refer to human review" and review is True
    return False


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    result = fuse_moderation_decision(case["text"], "user", ["text"])
    category = str(result.get("category", ""))
    action = str(result.get("action", ""))
    review = bool(result.get("human_review_required"))
    used = bool(result.get("illegal_activities_v2_rc2_used"))
    status = str(result.get("illegal_activities_v2_rc2_fusion_status", ""))
    automatic = result.get("illegal_activities_automatic_enforcement_allowed")
    category_ok = category in case["allowed_categories"]
    status_ok = status in case["allowed_statuses"]
    review_ok = not case.get("require_review", False) or review is True
    safe_pair_ok = (
        not case.get("require_safe_pair", False)
        or valid_safe_pair(category, action, review)
    )
    illegal_action_ok = (
        not case.get("illegal_case", False)
        or action == "Restrict and send for human review"
    )
    authority_ok = automatic is False
    return {
        "case_id": case["case_id"],
        "passed": all(
            [
                category_ok,
                status_ok,
                review_ok,
                safe_pair_ok,
                illegal_action_ok,
                authority_ok,
            ]
        ),
        "category": category,
        "action": action,
        "human_review_required": review,
        "illegal_activities_v2_rc2_used": used,
        "fusion_status": status,
        "automatic_enforcement_allowed": automatic,
    }


def main() -> None:
    print("Running the Illegal Activities V2 RC2 live fusion contract...")
    print("Independent holdouts are not used.")
    print()
    rows = [evaluate_case(case) for case in CASES]
    for row in rows:
        state = "PASS" if row["passed"] else "FAIL"
        print(
            f"{row['case_id']}: {state} | {row['category']} | "
            f"{row['action']} | RC2: {row['fusion_status']}"
        )
    passed = sum(bool(row["passed"]) for row in rows)
    contract_passed = passed == len(rows)
    report = {
        "contract": "illegal-activities-v2-rc2-live-fusion",
        "records": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "passed_live_fusion_contract": contract_passed,
        "automatic_enforcement_allowed": False,
        "independent_holdouts_used": False,
        "frozen_rc2_modified": False,
        "openrouter_accuracy_authority": False,
        "rows": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print("=" * 60)
    print("ILLEGAL ACTIVITIES V2 RC2 LIVE FUSION CONTRACT")
    print("=" * 60)
    print(f"Records: {len(rows)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(rows) - passed}")
    print(f"Passed live fusion contract: {contract_passed}")
    print("Automatic enforcement allowed: False")
    print("Independent holdouts used: False")
    print("Frozen RC2 modified: False")
    print(f"Report: {REPORT_PATH}")
    print("This is an integration contract, not an accuracy benchmark.")
    if not contract_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
