from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.fusion_service import fuse_moderation_decision
from app.services.hate_speech_v7_service import get_hate_speech_v7_status


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "hate_speech"
    / "v7_live_fusion_contract_v2"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"

CASES = (
    {
        "case_id": "HATE-LIVE-001",
        "text": (
            "Muslims are disgusting parasites and every Muslim should be "
            "expelled from the country."
        ),
        "expected_category": "Hate Speech & Discrimination",
        "expected_hate_used": True,
        "expected_review": True,
        "expected_action": "Refer to human review",
    },
    {
        "case_id": "HATE-SAFE-001",
        "text": (
            "This article condemns hatred against Muslims and explains why "
            "religious discrimination is harmful."
        ),
        "forbidden_category": "Hate Speech & Discrimination",
        "expected_hate_used": False,
    },
    {
        "case_id": "ABUSE-ISOLATION-001",
        "text": "You are a stupid, pathetic idiot.",
        "expected_category": "Abusive Words",
        "expected_hate_used": False,
    },
    {
        "case_id": "CYBER-ISOLATION-001",
        "text": (
            "Every day I post humiliating messages about you under each of "
            "your photos, and I will continue doing it."
        ),
        "allowed_categories": (
            "Cyberbullying & Harassment",
            "Uncertain",
        ),
        "expected_hate_used": False,
        "expected_review": True,
    },
    {
        "case_id": "SPAM-ISOLATION-001",
        "text": (
            "Congratulations! You won a cash prize. Send your OTP now to "
            "claim the reward."
        ),
        "expected_category": "Spam, Scam & Phishing",
        "expected_hate_used": False,
    },
    {
        "case_id": "PRIVATE-ISOLATION-001",
        "text": "His private email address is john.smith@gmail.com.",
        "expected_category": "Publishing Private Information",
        "expected_hate_used": False,
        "expected_review": True,
    },
    {
        "case_id": "VIOLENCE-ISOLATION-001",
        "text": (
            "The footage graphically shows a victim being decapitated, with "
            "severe visible blood and bodily injury."
        ),
        "expected_category": "Violent Content",
        "expected_hate_used": False,
        "expected_review": True,
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
        checks["category_within_existing_component_contract"] = (
            decision.get("category") in set(case["allowed_categories"])
        )
    if "expected_hate_used" in case:
        checks["hate_specialist_usage"] = bool(
            decision.get("hate_speech_v7_used", False)
        ) is bool(case["expected_hate_used"])
    if "expected_review" in case:
        checks["human_review"] = bool(
            decision.get("human_review_required", False)
        ) is bool(case["expected_review"])
    if "expected_action" in case:
        checks["action"] = decision.get("action") == case["expected_action"]

    automatic_enforcement_safe = not (
        bool(decision.get("hate_speech_v7_used", False))
        and (
            decision.get("action") != "Refer to human review"
            or not bool(decision.get("human_review_required", False))
        )
    )
    checks["hate_action_contract"] = automatic_enforcement_safe
    passed = all(checks.values())
    return {
        "case_id": case["case_id"],
        "passed": passed,
        "checks": checks,
        "category": decision.get("category"),
        "action": decision.get("action"),
        "human_review_required": decision.get("human_review_required"),
        "hate_speech_v7_used": decision.get("hate_speech_v7_used", False),
        "hate_speech_v7_fusion_status": decision.get(
            "hate_speech_v7_fusion_status",
            "missing",
        ),
    }


def main() -> None:
    status = get_hate_speech_v7_status()
    if status.get("available") is not True:
        raise RuntimeError(f"Hate Speech V7 is unavailable: {status}")
    if status.get("independently_validated") is not True:
        raise RuntimeError("Hate Speech V7 is not independently validated.")
    if status.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The Hate Speech V7 enforcement contract is invalid.")

    print("Running the Hate Speech V7 live fusion contract...")
    print("Reserved test splits are not used.")
    print()
    results: list[dict[str, Any]] = []
    for case in CASES:
        result = evaluate_case(case)
        results.append(result)
        outcome = "PASS" if result["passed"] else "FAIL"
        print(
            f"{result['case_id']}: {outcome} | {result['category']} | "
            f"{result['action']} | hate used: {result['hate_speech_v7_used']} | "
            f"status: {result['hate_speech_v7_fusion_status']}"
        )

    passed_count = sum(bool(result["passed"]) for result in results)
    passed = passed_count == len(results)
    report = {
        "candidate": "hate-speech-v7-rc1",
        "contract_version": "v2-corrected-category-isolation-scope",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "passed_live_fusion_contract": passed,
        "automatic_enforcement_allowed": False,
        "reserved_test_splits_used": False,
        "frozen_candidate_modified": False,
        "raw_case_text_stored_in_report": False,
        "results": results,
        "note": "This is an integration contract, not an accuracy benchmark.",
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH V7 LIVE FUSION CONTRACT V2")
    print("=" * 60)
    print(f"Records: {len(results)}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {len(results) - passed_count}")
    print(f"Passed live fusion contract: {passed}")
    print("Automatic enforcement allowed: False")
    print("Reserved test splits used: False")
    print(f"Report: {REPORT_PATH}")
    print("This contract is not an accuracy benchmark.")
    print(
        "V2 accepts the independently valid Cyberbullying or Uncertain "
        "review-only outcomes while still forbidding a Hate override."
    )


if __name__ == "__main__":
    main()
