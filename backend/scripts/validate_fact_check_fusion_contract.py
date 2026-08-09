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
    / "fusion_contract"
    / "report.json"
)


CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "FUSION-FACT-SUPPORT-001",
        "claim": "Paris is the capital of France.",
        "expected_status": "SUPPORTS",
        "expected_category": "Normal/Ignore",
        "expected_action": "Allow",
        "expected_human_review": False,
    },
    {
        "case_id": "FUSION-FACT-REFUTE-001",
        "claim": "The Eiffel Tower is located in Berlin.",
        "expected_status": "REFUTES",
        "expected_category": "Misinformation & Fake News",
        "expected_action": "Refer to human review",
        "expected_human_review": True,
    },
    {
        "case_id": "FUSION-FACT-INDIA-001",
        "claim": (
            "In 2022, the Supreme Court ordered future elections "
            "to use ballot papers instead of EVMs."
        ),
        "expected_status": "REFUTES",
        "expected_category": "Misinformation & Fake News",
        "expected_action": "Refer to human review",
        "expected_human_review": True,
    },
)


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    result = fuse_moderation_decision(
        text=str(case["claim"]),
        source_context="user",
        input_sources=["text"],
    )

    fact_check = dict(result.get("fact_check", {}))
    analysis = dict(fact_check.get("analysis", {}))

    actual_status = str(
        fact_check.get("evidence_status", "NOT_EVALUATED")
    )
    actual_category = str(result.get("category", ""))
    actual_action = str(result.get("action", ""))
    actual_review = bool(result.get("human_review_required", False))
    confidence = float(result.get("confidence", 0.0))
    fact_check_used = bool(result.get("fact_check_used", False))
    automatic_enforcement_allowed = bool(
        fact_check.get("automatic_enforcement_allowed", False)
    )

    checks = {
        "fact_check_used": fact_check_used,
        "status": actual_status == case["expected_status"],
        "category": actual_category == case["expected_category"],
        "action": actual_action == case["expected_action"],
        "human_review": actual_review == case["expected_human_review"],
        "confidence_cap": 0.0 <= confidence <= 0.80,
        "no_automatic_enforcement": not automatic_enforcement_allowed,
    }

    return {
        "case_id": case["case_id"],
        "expected_status": case["expected_status"],
        "actual_status": actual_status,
        "expected_category": case["expected_category"],
        "actual_category": actual_category,
        "expected_action": case["expected_action"],
        "actual_action": actual_action,
        "expected_human_review": case["expected_human_review"],
        "actual_human_review": actual_review,
        "confidence": confidence,
        "fact_check_used": fact_check_used,
        "engine_version": analysis.get("engine_version"),
        "stable_knowledge_eligible": analysis.get(
            "stable_knowledge_eligible"
        ),
        "approved_pib_cache_used": analysis.get(
            "approved_pib_cache_used"
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    results: list[dict[str, Any]] = []

    print("Running RC2 fact-check fusion contract tests...")
    print("Live evidence retrieval may take several minutes.\n")

    for case in CASES:
        result = evaluate_case(case)
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"{result['case_id']}: {status} | "
            f"{result['actual_status']} | "
            f"{result['actual_category']} | "
            f"confidence: {result['confidence']:.2f}"
        )

    passed_count = sum(bool(item["passed"]) for item in results)
    failed_count = len(results) - passed_count
    passed_gate = failed_count == 0

    report = {
        "version": "2026.08-rc2-fusion-contract-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_type": "development_integration_contract",
        "uses_rc2_holdout_records": False,
        "uses_rc2_holdout_predictions": False,
        "uses_rc2_holdout_mismatches": False,
        "records": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "passed_fusion_contract_gate": passed_gate,
        "results": results,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("RC2 FACT-CHECK FUSION CONTRACT RESULTS")
    print("=" * 60)
    print(f"Records: {len(results)}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Passed fusion contract gate: {passed_gate}")
    print(f"Report saved: {REPORT_PATH}")
    print("RC2 holdout records and mismatches were not used.")

    if not passed_gate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
