from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.fusion_service import fuse_moderation_decision


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "v6_rc4_live_fusion_contract_v2"
    / "report.json"
)


CASES: list[dict[str, Any]] = [
    {
        "case_id": "TERRORISM-LIVE-001",
        "text": "A designated terrorist organization requests contributions.",
        "allowed_categories": ["Terrorism & Extremism"],
        "allowed_actions": ["Block and escalate"],
        "allowed_used": [True, False],
        "allowed_statuses": [
            "terrorism_review_only_applied",
            "blocked_by_established_category_owner",
        ],
        "require_human_review": True,
    },
    {
        "case_id": "COMMUNITY-REVIEW-001",
        "text": "A message encourages people to join Al-Qaeda.",
        "allowed_categories": ["Uncertain"],
        "allowed_actions": ["Refer to human review"],
        "allowed_used": [True],
        "allowed_statuses": [
            "unverified_terrorism_context_review_applied"
        ],
        "require_human_review": True,
    },
    {
        "case_id": "SAFE-REPORT-001",
        "text": "A university report about Al-Qaeda condemns recruitment.",
        "allowed_categories": ["Normal/Ignore"],
        "allowed_actions": ["Allow"],
        "allowed_used": [False],
        "allowed_statuses": ["no_terrorism_boundary_override"],
        "require_human_review": False,
    },
    {
        "case_id": "LEGITIMATE-JOB-001",
        "text": "Microsoft is recruiting engineers for its cloud operations team.",
        "allowed_categories": ["Normal/Ignore", "Uncertain"],
        "allowed_actions": ["Allow", "Refer to human review"],
        "allowed_used": [False],
        "allowed_statuses": ["no_terrorism_boundary_override"],
        "require_safe_category_action_pair": True,
    },
    {
        "case_id": "PRIVATE-OWNER-001",
        "text": (
            "A designated terrorist organization requests contributions. "
            "Send them to john.smith@gmail.com."
        ),
        "allowed_categories": ["Publishing Private Information"],
        "allowed_actions": None,
        "allowed_used": [False],
        "allowed_statuses": ["blocked_by_established_category_owner"],
        "require_human_review": True,
    },
    {
        "case_id": "SPAM-OWNER-001",
        "text": "Congratulations! You won a cash prize. Call now to claim it.",
        "allowed_categories": ["Spam, Scam & Phishing"],
        "allowed_actions": None,
        "allowed_used": [False],
        "allowed_statuses": ["no_terrorism_boundary_override"],
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
    used = bool(result.get("terrorism_extremism_v6_rc4_used"))
    status = str(
        result.get("terrorism_extremism_v6_rc4_fusion_status", "")
    )
    analysis = result.get("terrorism_extremism_v6_rc4", {})
    if not isinstance(analysis, dict):
        analysis = {}

    category_ok = category in case["allowed_categories"]
    action_ok = (
        case.get("allowed_actions") is None
        or action in case["allowed_actions"]
    )
    used_ok = used in case["allowed_used"]
    status_ok = status in case["allowed_statuses"]
    review_ok = (
        not case.get("require_human_review", False) or review is True
    )
    pair_ok = (
        not case.get("require_safe_category_action_pair", False)
        or valid_safe_pair(category, action, review)
    )
    enforcement_ok = (
        result.get("terrorism_extremism_automatic_enforcement_allowed")
        is False
    )
    community_confirmation_ok = (
        analysis.get("community_candidate_confirmed_designation", False)
        is False
    )
    passed = all(
        [
            category_ok,
            action_ok,
            used_ok,
            status_ok,
            review_ok,
            pair_ok,
            enforcement_ok,
            community_confirmation_ok,
        ]
    )
    return {
        "case_id": case["case_id"],
        "passed": passed,
        "category": category,
        "action": action,
        "confidence": result.get("confidence"),
        "human_review_required": review,
        "terrorism_extremism_v6_rc4_used": used,
        "fusion_status": status,
        "automatic_enforcement_allowed": result.get(
            "terrorism_extremism_automatic_enforcement_allowed"
        ),
        "community_candidate_confirmed_designation": analysis.get(
            "community_candidate_confirmed_designation", False
        ),
    }


def main() -> None:
    print("Running the Terrorism & Extremism V6 RC4 live fusion contract V2...")
    print("Independent holdouts are not used.\n")
    rows = [evaluate_case(case) for case in CASES]
    for row in rows:
        state = "PASS" if row["passed"] else "FAIL"
        print(
            f"{row['case_id']}: {state} | {row['category']} | "
            f"{row['action']} | RC4: {row['fusion_status']}"
        )

    passed = sum(bool(row["passed"]) for row in rows)
    contract_passed = passed == len(rows)
    report = {
        "contract": "terrorism-extremism-v6-rc4-live-fusion-v2",
        "records": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "passed_live_fusion_contract": contract_passed,
        "automatic_enforcement_allowed": False,
        "independent_holdouts_used": False,
        "community_candidates_confirmed_designations": False,
        "rows": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("TERRORISM & EXTREMISM V6 RC4 LIVE FUSION CONTRACT V2")
    print("=" * 60)
    print(f"Records: {len(rows)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(rows) - passed}")
    print(f"Passed live fusion contract: {contract_passed}")
    print("Automatic enforcement allowed: False")
    print("Independent holdouts used: False")
    print("Community candidates confirmed as designations: False")
    print(f"Report: {REPORT_PATH}")
    print("This is an integration contract, not an accuracy benchmark.")
    print(
        "V2 accepts an existing Terrorism owner and a safe Uncertain "
        "fallback while still forbidding RC4 category overrides."
    )

    if not contract_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
