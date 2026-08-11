from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.fusion_service import fuse_moderation_decision


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    REPO_ROOT
    / "reports"
    / "evaluation"
    / "cyberbullying"
    / "v2_rc2_live_fusion_contract"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"

CASES = (
    {
        "case_id": "CYBER-LIVE-001",
        "text": "Meet me outside and I will smash your face.",
        "expected_category": "Cyberbullying & Harassment",
        "expected_review": True,
    },
    {
        "case_id": "CYBER-LIVE-002",
        "text": "I keep sending you messages every night after you told me to stop.",
        "expected_category": "Cyberbullying & Harassment",
        "expected_review": True,
    },
    {
        "case_id": "ABUSE-LIVE-001",
        "text": "You are a disgusting idiot.",
        "expected_category": "Abusive Words",
        "expected_review": True,
    },
    {
        "case_id": "SAFE-LIVE-001",
        "text": "Thank you for helping me finish the project today.",
        "expected_category": "Normal/Ignore",
        "expected_review": False,
    },
    {
        "case_id": "SAFE-LIVE-002",
        "text": "Never share your OTP or password with anyone.",
        "expected_category": "Normal/Ignore",
        "expected_review": False,
    },
    {
        "case_id": "SAFE-LIVE-003",
        "text": "This is a clearly marked parody account.",
        "expected_category": "Normal/Ignore",
        "expected_review": False,
    },
    {
        "case_id": "VIOLENCE-ISOLATION-001",
        "text": "The image clearly shows a decapitated body.",
        "expected_category": "Violent Content",
        "expected_review": True,
    },
    {
        "case_id": "SPAM-ISOLATION-001",
        "text": "I am the official bank support agent. Send your OTP immediately.",
        "expected_category": "Spam, Scam & Phishing",
        "expected_review": True,
    },
    {
        "case_id": "PRIVATE-ISOLATION-001",
        "text": "His private email is john.smith@gmail.com.",
        "expected_category": "Publishing Private Information",
        "expected_review": True,
    },
)


def main() -> None:
    results: list[dict] = []
    passed = 0
    available_count = 0

    print("Running the RC2 live fusion contract...")
    print("The frozen external test split is not used.")
    print()

    for case in CASES:
        result = fuse_moderation_decision(
            text=case["text"],
            source_context="unknown",
            input_sources=["text"],
        )
        specialist = dict(result.get("cyberbullying_rc2", {}))
        specialist_available = bool(specialist.get("available", False))
        available_count += int(specialist_available)

        category_correct = result.get("category") == case["expected_category"]
        review_correct = (
            bool(result.get("human_review_required"))
            is case["expected_review"]
        )
        no_automatic_enforcement = (
            specialist.get("automatic_enforcement_allowed") is False
        )
        correct = bool(
            category_correct
            and review_correct
            and specialist_available
            and no_automatic_enforcement
        )
        passed += int(correct)

        record = {
            "case_id": case["case_id"],
            "expected_category": case["expected_category"],
            "predicted_category": result.get("category"),
            "expected_human_review": case["expected_review"],
            "predicted_human_review": result.get("human_review_required"),
            "action": result.get("action"),
            "confidence": result.get("confidence"),
            "specialist_available": specialist_available,
            "specialist_decision": specialist.get("decision"),
            "specialist_label": specialist.get("predicted_label"),
            "specialist_applied": result.get("cyberbullying_rc2_used", False),
            "fusion_status": result.get("cyberbullying_rc2_fusion_status"),
            "automatic_enforcement_allowed": specialist.get(
                "automatic_enforcement_allowed"
            ),
            "correct": correct,
        }
        results.append(record)
        print(
            f"{case['case_id']}: {'PASS' if correct else 'FAIL'} | "
            f"{record['predicted_category']} | {record['action']} | "
            f"RC2: {record['fusion_status']}"
        )

    failures = len(CASES) - passed
    gate_passed = bool(passed == len(CASES) and available_count == len(CASES))
    report = {
        "candidate": "cyberbullying-v2-rc2",
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_records": len(CASES),
        "passed": passed,
        "failed": failures,
        "specialist_available_records": available_count,
        "passed_live_fusion_contract": gate_passed,
        "automatic_enforcement_allowed": False,
        "external_test_split_used": False,
        "raw_text_stored": False,
        "record_level_results": results,
        "interpretation": (
            "This verifies runtime routing and category isolation. It is not an "
            "accuracy benchmark and does not change the frozen RC2 candidate."
        ),
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("CYBERBULLYING/ABUSIVE WORDS RC2 LIVE FUSION CONTRACT")
    print("=" * 60)
    print(f"Records: {len(CASES)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failures}")
    print(f"Specialist available: {available_count}/{len(CASES)}")
    print(f"Passed live fusion contract: {gate_passed}")
    print("Automatic enforcement allowed: False")
    print("External test split used: False")
    print("Frozen RC2 modified: False")
    print(f"Report: {REPORT_PATH}")
    print("This contract is not an accuracy benchmark.")

    if not gate_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
