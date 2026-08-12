from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.fusion_service import fuse_moderation_decision
from app.services.religiously_offensive_v7_rc6_service import (
    get_religiously_offensive_v7_rc6_status,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v7_rc6_live_fusion_contract_v2"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"

RELIGIOUS_CATEGORY = "Religiously Offensive Content"
REQUIRED_ACTION = "Remove and send for human review"


CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "RELIGIOUS-LIVE-001",
        "text": "The organizer calls on listeners to burn the sacred manuscript.",
        "expected_category": RELIGIOUS_CATEGORY,
        "expected_religious_used": True,
        "expected_review": True,
        "expected_action": REQUIRED_ACTION,
    },
    {
        "case_id": "RELIGIOUS-LIVE-002",
        "text": "An online group urges its members to vandalize the neighborhood shrine.",
        "expected_category": RELIGIOUS_CATEGORY,
        "expected_religious_used": True,
        "expected_review": True,
        "expected_action": REQUIRED_ACTION,
    },
    {
        "case_id": "RELIGIOUS-LIVE-003",
        "text": (
            "The channel orders viewers to mock the revered deity with an "
            "obscene caricature."
        ),
        "expected_category": RELIGIOUS_CATEGORY,
        "expected_religious_used": True,
        "expected_review": True,
        "expected_action": REQUIRED_ACTION,
    },
    {
        "case_id": "RELIGIOUS-REPORT-001",
        "text": (
            "A news report quotes a speaker urging people to burn a sacred "
            "manuscript and explicitly condemns the statement."
        ),
        "forbidden_category": RELIGIOUS_CATEGORY,
        "expected_religious_used": False,
    },
    {
        "case_id": "RELIGIOUS-NEUTRAL-001",
        "text": "Visitors admired the restored sacred painting during the exhibition.",
        "forbidden_category": RELIGIOUS_CATEGORY,
        "expected_religious_used": False,
    },
    {
        "case_id": "HATE-OWNER-001",
        "text": (
            "Muslims are disgusting parasites and every Muslim should be "
            "expelled from the country."
        ),
        "expected_category": "Hate Speech & Discrimination",
        "expected_religious_used": False,
        "expected_review": True,
    },
    {
        "case_id": "FOLLOWER-HATE-BOUNDARY-001",
        "text": (
            "Followers of that religion are inferior and should be excluded "
            "from public life."
        ),
        "forbidden_category": RELIGIOUS_CATEGORY,
        "expected_religious_used": False,
        "expected_review": True,
    },
    {
        "case_id": "CYBER-OWNER-001",
        "text": "Meet me outside and I will smash your face.",
        "allowed_categories": ("Cyberbullying & Harassment", "Uncertain"),
        "expected_religious_used": False,
        "expected_review": True,
    },
    {
        "case_id": "SPAM-OWNER-001",
        "text": "I am official bank support. Send your OTP now to unlock the account.",
        "expected_category": "Spam, Scam & Phishing",
        "expected_religious_used": False,
    },
    {
        "case_id": "PRIVATE-OWNER-001",
        "text": "His private email address is john.smith@gmail.com.",
        "expected_category": "Publishing Private Information",
        "expected_religious_used": False,
        "expected_review": True,
    },
    {
        "case_id": "VIOLENCE-OWNER-001",
        "text": (
            "The footage graphically shows a victim being decapitated, with "
            "severe visible blood and bodily injury."
        ),
        "expected_category": "Violent Content",
        "expected_religious_used": False,
        "expected_review": True,
    },
    {
        "case_id": "SAFE-OWNER-001",
        "text": "Thank you for helping me finish the project today.",
        "expected_category": "Normal/Ignore",
        "expected_religious_used": False,
        "expected_review": False,
    },
)


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    decision = fuse_moderation_decision(
        text=str(case["text"]),
        source_context="unknown",
        input_sources=["text"],
    )
    checks: dict[str, bool] = {}
    if "expected_category" in case:
        checks["category"] = decision.get("category") == case["expected_category"]
    if "forbidden_category" in case:
        checks["forbidden_category_absent"] = (
            decision.get("category") != case["forbidden_category"]
        )
    if "allowed_categories" in case:
        checks["category_within_owner_contract"] = decision.get("category") in set(
            case["allowed_categories"]
        )
    if "expected_religious_used" in case:
        checks["religious_specialist_usage"] = bool(
            decision.get("religiously_offensive_v7_rc6_used", False)
        ) is bool(case["expected_religious_used"])
    if "expected_review" in case:
        checks["human_review"] = bool(
            decision.get("human_review_required", False)
        ) is bool(case["expected_review"])
    if "expected_action" in case:
        checks["action"] = decision.get("action") == case["expected_action"]

    religious_used = bool(decision.get("religiously_offensive_v7_rc6_used", False))
    checks["review_only_contract"] = not religious_used or bool(
        decision.get("category") == RELIGIOUS_CATEGORY
        and decision.get("action") == REQUIRED_ACTION
        and decision.get("human_review_required") is True
    )
    specialist = dict(decision.get("religiously_offensive_v7_rc6", {}))
    checks["no_automatic_enforcement"] = (
        specialist.get("automatic_enforcement_allowed") is False
    )
    passed = all(checks.values())
    return {
        "case_id": case["case_id"],
        "passed": passed,
        "checks": checks,
        "category": decision.get("category"),
        "action": decision.get("action"),
        "human_review_required": decision.get("human_review_required"),
        "religious_used": religious_used,
        "religious_decision": specialist.get("decision", "missing"),
        "religious_decision_path": specialist.get("decision_path", ""),
        "religious_policy_veto": specialist.get("policy_veto_reason", ""),
        "religious_fusion_status": decision.get(
            "religiously_offensive_v7_rc6_fusion_status", "missing"
        ),
    }


def main() -> None:
    status = get_religiously_offensive_v7_rc6_status()
    if status.get("available") is not True:
        raise RuntimeError(f"Religiously Offensive RC6 is unavailable: {status}")
    if status.get("independently_validated") is not True:
        raise RuntimeError("Religiously Offensive RC6 is not independently validated.")
    if status.get("eligible_for_guarded_live_integration") is not True:
        raise RuntimeError("Religiously Offensive RC6 is not integration-eligible.")
    if status.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The RC6 automatic-enforcement contract is invalid.")

    print("Running the Religiously Offensive Content V7 RC6 live fusion contract...")
    print("Independent holdouts are not used.")
    print()
    results: list[dict[str, Any]] = []
    for case in CASES:
        result = evaluate_case(case)
        results.append(result)
        print(
            f"{result['case_id']}: {'PASS' if result['passed'] else 'FAIL'} | "
            f"{result['category']} | {result['action']} | "
            f"RC6: {result['religious_fusion_status']}"
        )

    passed_count = sum(bool(result["passed"]) for result in results)
    failed_count = len(results) - passed_count
    passed = failed_count == 0
    report = {
        "candidate": "religiously-offensive-v7-rc6",
        "contract_version": "2026.08-v2-owner-policy-scope",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "passed_live_fusion_contract": passed,
        "automatic_enforcement_allowed": False,
        "independent_holdouts_used": False,
        "frozen_candidate_modified": False,
        "raw_case_text_stored": False,
        "results_without_raw_text": results,
        "note": (
            "This validates RC6 integration behavior, not model accuracy. "
            "V2 does not impose a human-review rule on an unrelated category "
            "when RC6 made no decision."
        ),
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print("RELIGIOUSLY OFFENSIVE CONTENT V7 RC6 LIVE FUSION CONTRACT V2")
    print("=" * 60)
    print(f"Records: {len(results)}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Passed live fusion contract: {passed}")
    print("Automatic enforcement allowed: False")
    print("Independent holdouts used: False")
    print("Frozen RC6 modified: False")
    print(f"Report: {REPORT_PATH}")
    print("This is an integration contract, not an accuracy benchmark.")
    print(
        "V2 preserves the established Spam policy while verifying that RC6 "
        "does not override it."
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
