from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.fusion_service import fuse_moderation_decision


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SCRIPT_DIRECTORY.parent
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent
REPORT_PATH = (
    PROJECT_DIRECTORY
    / "reports"
    / "evaluation"
    / "stable_knowledge_v3"
    / "fusion_isolation"
    / "report.json"
)


CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "FUSION-SPAM-001",
        "text": (
            "Congratulations! You won a cash prize. "
            "Call now to claim your reward."
        ),
        "allowed_categories": ["Spam, Scam & Phishing"],
        "fact_check_must_be_skipped": True,
    },
    {
        "case_id": "FUSION-PRIVATE-001",
        "text": "His private email is john.smith@gmail.com.",
        "allowed_categories": ["Publishing Private Information"],
        "fact_check_must_be_skipped": True,
    },
    {
        "case_id": "FUSION-IDENTITY-001",
        "text": (
            "I am the official bank support agent. "
            "Send your OTP immediately."
        ),
        "allowed_categories": [
            "Spam, Scam & Phishing",
            "Identity Theft & Impersonation",
        ],
        "fact_check_must_be_skipped": True,
    },
    {
        "case_id": "FUSION-VIOLENCE-001",
        "text": "I will kill you tonight.",
        "allowed_categories": ["Violent Content"],
        "fact_check_must_be_skipped": True,
    },
    {
        "case_id": "FUSION-SAFE-001",
        "text": (
            "I visited the railway station with my family "
            "and took several photographs."
        ),
        "allowed_categories": ["Normal/Ignore"],
        "fact_check_must_be_skipped": True,
    },
    {
        "case_id": "FUSION-CONTEXT-001",
        "text": (
            "This is not a scam. Never share your OTP "
            "or password with anyone."
        ),
        "allowed_categories": ["Normal/Ignore"],
        "fact_check_must_be_skipped": True,
    },
    {
        "case_id": "FUSION-PARODY-001",
        "text": "This is a clearly marked parody account.",
        "allowed_categories": ["Normal/Ignore"],
        "fact_check_must_be_skipped": True,
    },
)


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    result = fuse_moderation_decision(
        text=str(case["text"]),
        source_context="user",
        input_sources=["text"],
    )

    category = str(result.get("category", ""))
    fact_check_used = bool(result.get("fact_check_used", False))
    allowed_categories = list(case["allowed_categories"])

    category_passed = category in allowed_categories
    isolation_passed = not fact_check_used
    passed = category_passed and isolation_passed

    return {
        "case_id": case["case_id"],
        "expected_categories": allowed_categories,
        "actual_category": category,
        "action": result.get("action"),
        "confidence": result.get("confidence"),
        "human_review_required": result.get(
            "human_review_required"
        ),
        "fact_check_used": fact_check_used,
        "fact_check_status": result.get(
            "fact_check",
            {},
        ).get("evidence_status"),
        "category_passed": category_passed,
        "isolation_passed": isolation_passed,
        "passed": passed,
    }


def main() -> None:
    results: list[dict[str, Any]] = []

    print("Running fact-check fusion category-isolation tests...")

    for case in CASES:
        result = evaluate_case(case)
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"{result['case_id']}: {status} | "
            f"{result['actual_category']} | "
            f"fact-check used: {result['fact_check_used']}"
        )

    passed_count = sum(bool(item["passed"]) for item in results)
    failed_count = len(results) - passed_count
    passed_gate = failed_count == 0

    report = {
        "version": "2026.08-rc2-fusion-isolation-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_type": "development_integration_check",
        "uses_rc2_holdout_records": False,
        "uses_rc2_holdout_predictions": False,
        "uses_rc2_holdout_mismatches": False,
        "records": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "passed_isolation_gate": passed_gate,
        "results": results,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("RC2 FACT-CHECK FUSION ISOLATION RESULTS")
    print("=" * 60)
    print(f"Records: {len(results)}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Passed isolation gate: {passed_gate}")
    print(f"Report saved: {REPORT_PATH}")
    print("RC2 holdout records and mismatches were not used.")

    if not passed_gate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
