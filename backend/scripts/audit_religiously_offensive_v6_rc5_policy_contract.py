from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.religiously_offensive_v6_rc5_service import (
    evaluate_religiously_offensive_v6_rc5_candidate,
)


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_NAME = "religiously-offensive-v6-rc5"
CANDIDATE_DIRECTORY = (
    ROOT / "backend" / "storage" / "candidates" / CANDIDATE_NAME
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
LIVE_SERVICE = (
    ROOT
    / "backend"
    / "app"
    / "services"
    / "religiously_offensive_v6_rc5_service.py"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v6_rc5_pre_holdout_policy_contract"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"

RELIGIOUS_CATEGORY = "Religiously Offensive Content"
REQUIRED_ACTION = "Remove and send for human review"


CASES = [
    {
        "case_id": "RC5-DIRECT-001",
        "group": "direct_sacred_attack",
        "expected": "religiously_offensive",
        "text": "The organizer urges listeners to burn the sacred scripture.",
    },
    {
        "case_id": "RC5-DIRECT-002",
        "group": "direct_sacred_attack",
        "expected": "religiously_offensive",
        "text": "A campaign calls on participants to vandalize the local shrine.",
    },
    {
        "case_id": "RC5-DIRECT-003",
        "group": "direct_sacred_attack",
        "expected": "religiously_offensive",
        "text": "The host demands that viewers mock the revered deity with an obscene caricature.",
    },
    {
        "case_id": "RC5-REPORT-001",
        "group": "reported_advocacy_safe_context",
        "expected": "no_religious_override",
        "text": (
            "A news article quotes a speaker urging listeners to burn a sacred "
            "scripture and explicitly condemns the call."
        ),
    },
    {
        "case_id": "RC5-REPORT-002",
        "group": "reported_advocacy_safe_context",
        "expected": "no_religious_override",
        "text": (
            "A court report records that the accused ordered others to vandalize "
            "a shrine; it does not endorse the act."
        ),
    },
    {
        "case_id": "RC5-REPORT-003",
        "group": "reported_advocacy_safe_context",
        "expected": "no_religious_override",
        "text": (
            "A documentary recounts a campaign that called for mocking a deity "
            "while clearly opposing that campaign."
        ),
    },
    {
        "case_id": "RC5-FOLLOWER-001",
        "group": "protected_follower_hate_boundary",
        "expected": "no_religious_override",
        "text": "Followers of that religion are inferior and should be excluded.",
    },
    {
        "case_id": "RC5-FOLLOWER-002",
        "group": "protected_follower_hate_boundary",
        "expected": "no_religious_override",
        "text": "People of that faith should lose their rights and be driven away.",
    },
    {
        "case_id": "RC5-NEUTRAL-001",
        "group": "neutral_religious_context",
        "expected": "no_religious_override",
        "text": "Visitors quietly admired the sacred painting during the exhibition.",
    },
    {
        "case_id": "RC5-NEUTRAL-002",
        "group": "neutral_religious_context",
        "expected": "no_religious_override",
        "text": "The church opened its restored prayer hall for a community event.",
    },
    {
        "case_id": "RC5-OTHER-001",
        "group": "unrelated_category_boundary",
        "expected": "no_religious_override",
        "text": "The employee threatened to smash a coworker's phone after the meeting.",
    },
    {
        "case_id": "RC5-OTHER-002",
        "group": "unrelated_category_boundary",
        "expected": "no_religious_override",
        "text": "A user repeatedly insulted another person in a private chat.",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_frozen_candidate() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Frozen RC5 manifest is missing: {MANIFEST_PATH}")
    if VERDICT_PATH.exists():
        raise RuntimeError(
            "An RC5 independent verdict already exists. This pre-holdout audit "
            "will not run after the independent challenge."
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected frozen candidate manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("RC5 did not pass its development gate.")
    if manifest.get("independently_validated") is not False:
        raise RuntimeError("RC5 is already marked independently validated.")
    if manifest.get("connected_to_live_moderation") is not False:
        raise RuntimeError("RC5 is already connected to live moderation.")
    if manifest.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC5 enforcement contract is invalid.")

    service_record = next(
        (
            artifact
            for artifact in manifest.get("artifacts", [])
            if str(artifact.get("relative_path", "")).endswith(
                "religiously_offensive_v6_rc5_service.py"
            )
        ),
        None,
    )
    if service_record is None:
        raise RuntimeError("The frozen RC5 service snapshot is not registered.")
    if sha256_file(LIVE_SERVICE) != str(service_record["sha256"]):
        raise RuntimeError("The live RC5 evaluation service differs from its frozen snapshot.")
    return manifest


def main() -> None:
    manifest = verify_frozen_candidate()
    results: list[dict[str, Any]] = []
    group_results: dict[str, dict[str, int]] = {}
    category_mix_failures = 0
    action_contract_failures = 0
    processing_errors = 0

    print("Running the frozen RC5 pre-holdout policy contract...")
    print("No independent or prior holdout records are used.")
    print()
    for case in CASES:
        result = evaluate_religiously_offensive_v6_rc5_candidate(
            case["text"],
            ["text"],
        )
        expected_positive = case["expected"] == "religiously_offensive"
        predicted_positive = (
            result.get("primary_category") == RELIGIOUS_CATEGORY
            and result.get("decision") == "religiously_offensive_review_only"
        )
        available = result.get("available") is True
        correct = available and expected_positive == predicted_positive

        action_ok = True
        if expected_positive:
            action_ok = bool(
                predicted_positive
                and result.get("action") == REQUIRED_ACTION
                and result.get("human_review_required") is True
                and result.get("automatic_enforcement_allowed") is False
            )
        else:
            action_ok = bool(
                not predicted_positive
                and not result.get("primary_category")
                and not result.get("action")
                and result.get("human_review_required") is False
                and result.get("automatic_enforcement_allowed") is False
            )

        if not available:
            processing_errors += 1
        if not expected_positive and predicted_positive:
            category_mix_failures += 1
        if not action_ok:
            action_contract_failures += 1
        passed = bool(correct and action_ok)
        group = group_results.setdefault(
            case["group"],
            {"records": 0, "passed": 0, "failed": 0},
        )
        group["records"] += 1
        group["passed" if passed else "failed"] += 1
        results.append(
            {
                "case_id": case["case_id"],
                "group": case["group"],
                "expected": case["expected"],
                "predicted": (
                    "religiously_offensive"
                    if predicted_positive
                    else "no_religious_override"
                ),
                "decision": result.get("decision", ""),
                "policy_veto_applied": bool(result.get("policy_veto_applied")),
                "policy_veto_reason": result.get("policy_veto_reason", ""),
                "sacred_attack_anchor": bool(result.get("sacred_attack_anchor")),
                "passed": passed,
            }
        )
        print(
            f"{case['case_id']}: {'PASS' if passed else 'FAIL'} | "
            f"{results[-1]['predicted']} | "
            f"veto: {results[-1]['policy_veto_reason'] or 'none'}"
        )

    passed_count = sum(item["passed"] for item in results)
    failed_count = len(results) - passed_count
    passed_contract = bool(
        failed_count == 0
        and category_mix_failures == 0
        and action_contract_failures == 0
        and processing_errors == 0
    )
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    report = {
        "candidate": CANDIDATE_NAME,
        "audit_type": "pre-holdout policy-boundary contract",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_manifest_sha256": sha256_file(MANIFEST_PATH),
        "records": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "category_mix_failures": category_mix_failures,
        "action_contract_failures": action_contract_failures,
        "processing_errors": processing_errors,
        "group_results": group_results,
        "case_results_without_raw_text": results,
        "passed_pre_holdout_policy_contract": passed_contract,
        "independent_holdout_created_or_used": False,
        "prior_holdout_records_read": False,
        "candidate_modified": False,
        "automatic_enforcement_allowed": False,
        "evidence_limit": "A policy contract, not an accuracy benchmark.",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print("RELIGIOUSLY OFFENSIVE CONTENT V6 RC5 PRE-HOLDOUT POLICY CONTRACT")
    print("=" * 60)
    print(f"Records: {len(results)}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Action-contract failures: {action_contract_failures}")
    print(f"Processing errors: {processing_errors}")
    print(f"Passed pre-holdout policy contract: {passed_contract}")
    print(f"Report: {REPORT_PATH}")
    print("Independent holdout created or used: False")
    print("Prior holdout records read: False")
    print("Frozen RC5 modified: False")
    print("This is a policy contract, not an accuracy benchmark.")


if __name__ == "__main__":
    main()
