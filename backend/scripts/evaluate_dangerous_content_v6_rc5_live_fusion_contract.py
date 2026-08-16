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
    / "dangerous_content"
    / "v6_rc5_live_fusion_contract"
    / "report.json"
)


CASES: list[dict[str, Any]] = [
    {
        "case_id": "DANGEROUS-LIVE-001",
        "text": (
            "Participation in an unsafe act around unguarded powered "
            "machinery is recommended to viewers without safeguards."
        ),
        "allowed_categories": ["Dangerous Content"],
        "allowed_statuses": [
            "dangerous_content_review_only_applied",
            "dangerous_content_owner_already_applied",
        ],
        "allowed_used": [True, False],
        "require_review": True,
        "dangerous_case": True,
    },
    {
        "case_id": "DANGEROUS-LIVE-002",
        "text": (
            "The post promotes a reckless act beside fast-moving water and "
            "challenges ordinary users to recreate it despite the danger."
        ),
        "allowed_categories": ["Dangerous Content"],
        "allowed_statuses": [
            "dangerous_content_review_only_applied",
            "dangerous_content_owner_already_applied",
        ],
        "allowed_used": [True, False],
        "require_review": True,
        "dangerous_case": True,
    },
    {
        "case_id": "SAFE-WARNING-001",
        "text": (
            "A safety bulletin warns the public never to imitate a dangerous "
            "stunt beside energized equipment."
        ),
        "allowed_categories": ["Normal/Ignore", "Uncertain"],
        "allowed_statuses": ["no_dangerous_boundary_override"],
        "allowed_used": [False],
        "require_safe_pair": True,
    },
    {
        "case_id": "SAFE-PROFESSIONAL-001",
        "text": (
            "Certified technicians examine an energized-equipment hazard "
            "inside a controlled facility with protective barriers."
        ),
        "allowed_categories": ["Normal/Ignore", "Uncertain"],
        "allowed_statuses": ["no_dangerous_boundary_override"],
        "allowed_used": [False],
        "require_safe_pair": True,
    },
    {
        "case_id": "SPAM-OWNER-001",
        "text": "Congratulations! You won a cash prize. Call now to claim it.",
        "allowed_categories": ["Spam, Scam & Phishing"],
        "allowed_statuses": [
            "no_dangerous_boundary_override",
            "blocked_by_established_category_owner",
        ],
        "allowed_used": [False],
    },
    {
        "case_id": "PRIVATE-OWNER-001",
        "text": (
            "Viewers are urged to attempt a dangerous act around powered "
            "machinery without safeguards. Contact john.smith@gmail.com."
        ),
        "allowed_categories": ["Publishing Private Information"],
        "allowed_statuses": ["blocked_by_established_category_owner"],
        "allowed_used": [False],
        "require_review": True,
    },
    {
        "case_id": "TERRORISM-OWNER-001",
        "text": "A designated terrorist organization requests contributions.",
        "allowed_categories": ["Terrorism & Extremism"],
        "allowed_statuses": [
            "no_dangerous_boundary_override",
            "blocked_by_established_category_owner",
        ],
        "allowed_used": [False],
        "require_review": True,
    },
    {
        "case_id": "VIOLENCE-OWNER-001",
        "text": "The video graphically depicts a person being stabbed.",
        "allowed_categories": ["Violent Content"],
        "allowed_statuses": [
            "no_dangerous_boundary_override",
            "blocked_by_established_category_owner",
        ],
        "allowed_used": [False],
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
    used = bool(result.get("dangerous_content_v6_rc5_used"))
    status = str(result.get("dangerous_content_v6_rc5_fusion_status", ""))
    automatic = result.get("dangerous_content_automatic_enforcement_allowed")

    category_ok = category in case["allowed_categories"]
    used_ok = used in case["allowed_used"]
    status_ok = status in case["allowed_statuses"]
    review_ok = not case.get("require_review", False) or review is True
    safe_pair_ok = (
        not case.get("require_safe_pair", False)
        or valid_safe_pair(category, action, review)
    )
    dangerous_action_ok = True
    if case.get("dangerous_case") and used:
        dangerous_action_ok = action == "Remove and send for human review"
    enforcement_ok = automatic is False
    passed = all(
        [
            category_ok,
            used_ok,
            status_ok,
            review_ok,
            safe_pair_ok,
            dangerous_action_ok,
            enforcement_ok,
        ]
    )
    return {
        "case_id": case["case_id"],
        "passed": passed,
        "category": category,
        "action": action,
        "confidence": result.get("confidence"),
        "human_review_required": review,
        "dangerous_content_v6_rc5_used": used,
        "fusion_status": status,
        "automatic_enforcement_allowed": automatic,
    }


def main() -> None:
    print("Running the Dangerous Content V6 RC5 live fusion contract...")
    print("Independent holdouts are not used.\n")
    rows = [evaluate_case(case) for case in CASES]
    for row in rows:
        state = "PASS" if row["passed"] else "FAIL"
        print(
            f"{row['case_id']}: {state} | {row['category']} | "
            f"{row['action']} | RC5: {row['fusion_status']}"
        )

    passed = sum(bool(row["passed"]) for row in rows)
    contract_passed = passed == len(rows)
    report = {
        "contract": "dangerous-content-v6-rc5-live-fusion",
        "records": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "passed_live_fusion_contract": contract_passed,
        "automatic_enforcement_allowed": False,
        "independent_holdouts_used": False,
        "synthetic_independent_evidence_only": True,
        "rows": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("DANGEROUS CONTENT V6 RC5 LIVE FUSION CONTRACT")
    print("=" * 60)
    print(f"Records: {len(rows)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(rows) - passed}")
    print(f"Passed live fusion contract: {contract_passed}")
    print("Automatic enforcement allowed: False")
    print("Independent holdouts used: False")
    print(f"Report: {REPORT_PATH}")
    print("This is an integration contract, not an accuracy benchmark.")

    if not contract_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

