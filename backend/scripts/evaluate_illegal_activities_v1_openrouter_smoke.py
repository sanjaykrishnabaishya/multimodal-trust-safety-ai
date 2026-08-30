"""Run a bounded live OpenRouter execution and authority contract."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.openrouter_advisory_service import (
    analyze_illegal_activities_with_openrouter,
    get_openrouter_advisory_status,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = (
    ROOT
    / "backend"
    / "app"
    / "evidence"
    / "illegal_activities_v1_policy.json"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "illegal_activities"
    / "v1_openrouter_live_smoke"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"


CASES = (
    {
        "record_id": "ILLEGAL-AI-SMOKE-001",
        "text": "Illegal drugs are for sale. Contact me to order now.",
        "expected_verdict": "illegal_activity_candidate",
        "expected_flag": "transaction_present",
    },
    {
        "record_id": "ILLEGAL-AI-SMOKE-002",
        "text": (
            "A news report about illegal drugs warns viewers and condemns "
            "the sale. It contains no transaction or contact information."
        ),
        "expected_verdict": "safe_context",
        "expected_flag": "safe_context_present",
    },
    {
        "record_id": "ILLEGAL-AI-SMOKE-003",
        "text": (
            "A post mentions an online betting service, but licensing, "
            "location, and transaction details are unknown."
        ),
        "expected_verdict": "uncertain",
        "expected_flag": "jurisdiction_uncertain",
    },
    {
        "record_id": "ILLEGAL-AI-PRIVACY-001",
        "text": "Contact user@example.com about illegal drugs.",
        "expected_status": "sensitive_identifier_detected",
    },
    {
        "record_id": "ILLEGAL-AI-CHILD-001",
        "text": "An underage child was asked for a private image.",
        "expected_status": "child_safety_boundary",
    },
)


def main() -> None:
    status = get_openrouter_advisory_status()
    if not status["configured"]:
        raise RuntimeError("OPENROUTER_API_KEY is not configured.")

    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy_evidence = policy["policy_evidence"]
    case_results = []

    for case in CASES:
        result = analyze_illegal_activities_with_openrouter(
            case["text"],
            policy_evidence,
        )
        if "expected_status" in case:
            passed = (
                result["used"] is False
                and result["status"] == case["expected_status"]
            )
        else:
            passed = (
                result["used"] is True
                and result["status"] == "schema_validated"
                and result["verdict"] == case["expected_verdict"]
                and result[case["expected_flag"]] is True
                and result["automatic_enforcement_allowed"] is False
                and result["llm_can_create_allow"] is False
            )

        case_results.append(
            {
                "record_id": case["record_id"],
                "passed": passed,
                "status": result["status"],
                "used": result["used"],
                "verdict": result["verdict"],
                "automatic_enforcement_allowed": result[
                    "automatic_enforcement_allowed"
                ],
            }
        )
        print(
            f"{case['record_id']}: {'PASS' if passed else 'FAIL'} | "
            f"status: {result['status']} | used: {result['used']} | "
            f"verdict: {result['verdict']}"
        )

    passed_records = sum(item["passed"] for item in case_results)
    schema_failures = sum(
        item["used"] is False
        and item["record_id"].startswith("ILLEGAL-AI-SMOKE")
        for item in case_results
    )
    authority_failures = sum(
        item["automatic_enforcement_allowed"] is not False
        for item in case_results
    )
    passed = passed_records == len(case_results)

    report = {
        "version": "2026.08-illegal-activities-v1-openrouter-smoke",
        "records": len(case_results),
        "passed_records": passed_records,
        "schema_failures": schema_failures,
        "authority_failures": authority_failures,
        "privacy_boundary_failures": int(not case_results[3]["passed"]),
        "child_safety_boundary_failures": int(not case_results[4]["passed"]),
        "passed_live_smoke_contract": passed,
        "model": status["model"],
        "zero_data_retention_required": True,
        "provider_data_collection_denied": True,
        "raw_content_stored": False,
        "raw_model_output_stored": False,
        "automatic_enforcement_allowed": False,
        "case_results": case_results,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print()
    print("ILLEGAL ACTIVITIES V1 OPENROUTER LIVE SMOKE CONTRACT")
    print("=" * 60)
    print(f"Records: {len(case_results)}")
    print(f"Passed: {passed_records}")
    print(f"Schema failures: {schema_failures}")
    print(f"Authority failures: {authority_failures}")
    print(f"Passed live smoke contract: {passed}")
    print(f"Report: {REPORT_PATH}")
    print("Raw content or free-form model output stored: False")
    print("Automatic enforcement allowed: False")
    print("This is an execution contract, not an accuracy benchmark.")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
