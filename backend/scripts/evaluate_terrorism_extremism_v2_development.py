from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from app.services.terrorism_extremism_service import (
    analyze_terrorism_extremism,
    get_terrorism_extremism_status,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    ROOT
    / "datasets"
    / "development"
    / "terrorism_extremism_v1"
    / "development.csv"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "development_v2_behavior_only"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.csv"

EXPECTED_STATUS_BY_GROUP = {
    "recruitment_and_membership": "terrorism_behavior_review_only",
    "praise_glorification_and_propaganda": "terrorism_behavior_review_only",
    "funding_resources_and_operational_support": "terrorism_behavior_review_only",
    "unknown_or_unverified_organization": "organization_status_unverified",
    "reporting_education_history_and_condemnation": (
        "safe_reporting_education_history_or_condemnation"
    ),
    "unrelated_category_isolation": "no_boundary_override",
    "legitimate_recruitment_and_operations": (
        "legitimate_recruitment_or_operational_context"
    ),
}

MINIMUM_ACCURACY = 0.85
MINIMUM_TERRORISM_RECALL = 0.85
MINIMUM_SAFE_SPECIFICITY = 0.90
MINIMUM_UNKNOWN_REVIEW_RATE = 0.95
MINIMUM_ISOLATION_RATE = 0.95


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def load_rows() -> list[dict[str, str]]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            "The V1 development dataset is missing. Run "
            "scripts.evaluate_terrorism_extremism_v1_development first."
        )
    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    legitimate_cases = [
        "Microsoft is recruiting software engineers for its cloud team.",
        "A Microsoft recruiter invited candidates to apply for an engineering job.",
        "Microsoft asked applicants to submit resumes for open positions.",
        "The company is hiring interns for its summer programme.",
        "Our human resources team is recruiting candidates for an accounting role.",
        "The employer invites graduates to register for campus recruitment.",
        "A hospital is recruiting nurses for its emergency department.",
        "The university is recruiting researchers for a science project.",
        "The charity is recruiting volunteers for flood-relief work.",
        "The sports club asked new members to join its training programme.",
        "Microsoft provides operational support for its cloud customers.",
        "The software company offers technical support to business clients.",
        "A logistics company coordinates delivery operations for local stores.",
        "The project team requested operational assistance from its IT department.",
        "The charity provides material support to families after a flood.",
        "A humanitarian organization distributes supplies to disaster survivors.",
        "The school requested donations for new library books.",
        "The university raised funds for student scholarships.",
        "The community group shares resources for a neighbourhood food drive.",
        "The business funds employee training and workplace safety programmes.",
    ]
    start = len(rows) + 1
    for offset, text in enumerate(legitimate_cases):
        rows.append(
            {
                "case_id": f"TERROR-V2-ORG-{start + offset:03d}",
                "group": "legitimate_recruitment_and_operations",
                "text": text,
                "expected_category": "NO_OVERRIDE",
                "terrorism_violation": "False",
            }
        )
    return rows


def main() -> None:
    rows = load_rows()
    specialist_status = get_terrorism_extremism_status()
    results: list[dict[str, Any]] = []

    for row in rows:
        analysis = analyze_terrorism_extremism(row["text"])
        expected_status = EXPECTED_STATUS_BY_GROUP[row["group"]]
        if (
            row["terrorism_violation"] == "True"
            and not re.search(
                r"\b(?:designated|banned|proscribed|listed)\s+"
                r"(?:terrorist|extremist)\b",
                row["text"],
                flags=re.IGNORECASE,
            )
        ):
            expected_status = "possible_extremist_behavior_unverified"

        if row["group"] == "unrelated_category_isolation":
            correct = bool(
                analysis["category"] is None
                and analysis["action"] == "No boundary override"
            )
        else:
            correct = analysis["status"] == expected_status

        action_failure = False
        if expected_status == "terrorism_behavior_review_only":
            action_failure = bool(
                analysis["action"] != "Block and escalate"
                or analysis["human_review_required"] is not True
                or analysis["automatic_enforcement_allowed"] is not False
            )
        elif expected_status in {
            "organization_status_unverified",
            "possible_extremist_behavior_unverified",
            "conflicting_context_requires_review",
            "conflicting_legitimate_and_extremist_context",
        }:
            action_failure = bool(
                analysis["action"] != "Refer to human review"
                or analysis["human_review_required"] is not True
                or analysis["automatic_enforcement_allowed"] is not False
            )
        elif expected_status == "safe_reporting_education_history_or_condemnation":
            action_failure = bool(
                analysis["action"] != "Allow"
                or analysis["human_review_required"] is not False
                or analysis["automatic_enforcement_allowed"] is not False
            )
        else:
            action_failure = bool(
                analysis["category"] is not None
                or analysis["automatic_enforcement_allowed"] is not False
            )

        registry_failure = bool(
            analysis["organization_registry_used"] is not False
            or analysis["official_source_data_used"] is not False
        )
        results.append(
            {
                **row,
                "expected_status": expected_status,
                "predicted_status": analysis["status"],
                "predicted_category": analysis["category"] or "NO_OVERRIDE",
                "confidence": analysis["confidence"],
                "action": analysis["action"],
                "human_review_required": analysis["human_review_required"],
                "behavior_families": "|".join(analysis["behavior_families"]),
                "designation_evidence": analysis["designation_evidence"],
                "correct": correct,
                "action_contract_failure": action_failure,
                "registry_contract_failure": registry_failure,
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[result["group"]].append(result)

    group_results = {
        group: {
            "records": len(group_rows),
            "correct": sum(bool(row["correct"]) for row in group_rows),
            "accuracy": round(
                safe_divide(
                    sum(bool(row["correct"]) for row in group_rows),
                    len(group_rows),
                ),
                4,
            ),
        }
        for group, group_rows in sorted(grouped.items())
    }

    positive = [
        row
        for row in results
        if row["expected_status"] == "terrorism_behavior_review_only"
    ]
    safe = [
        row
        for row in results
        if row["group"] == "reporting_education_history_and_condemnation"
    ]
    unknown = [
        row
        for row in results
        if row["expected_status"]
        in {
            "organization_status_unverified",
            "possible_extremist_behavior_unverified",
            "conflicting_context_requires_review",
            "conflicting_legitimate_and_extremist_context",
        }
    ]
    isolation = [
        row for row in results if row["group"] == "unrelated_category_isolation"
    ]

    accuracy = safe_divide(sum(bool(row["correct"]) for row in results), len(results))
    terrorism_recall = safe_divide(
        sum(row["predicted_status"] == "terrorism_behavior_review_only" for row in positive),
        len(positive),
    )
    safe_specificity = safe_divide(
        sum(
            row["predicted_status"]
            == "safe_reporting_education_history_or_condemnation"
            for row in safe
        ),
        len(safe),
    )
    unknown_review_rate = safe_divide(
        sum(row["human_review_required"] is True for row in unknown), len(unknown)
    )
    isolation_rate = safe_divide(
        sum(
            row["predicted_category"] == "NO_OVERRIDE"
            and row["action"] == "No boundary override"
            for row in isolation
        ),
        len(isolation),
    )
    action_failures = sum(bool(row["action_contract_failure"]) for row in results)
    registry_failures = sum(bool(row["registry_contract_failure"]) for row in results)

    passed = bool(
        accuracy >= MINIMUM_ACCURACY
        and terrorism_recall >= MINIMUM_TERRORISM_RECALL
        and safe_specificity >= MINIMUM_SAFE_SPECIFICITY
        and unknown_review_rate >= MINIMUM_UNKNOWN_REVIEW_RATE
        and isolation_rate >= MINIMUM_ISOLATION_RATE
        and action_failures == 0
        and registry_failures == 0
    )

    mismatches = [row for row in results if not row["correct"]]
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with MISMATCH_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(mismatches)

    report = {
        "candidate": "terrorism-extremism-v2-behavior-only",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(results),
        "accuracy": round(accuracy, 4),
        "terrorism_recall": round(terrorism_recall, 4),
        "safe_specificity": round(safe_specificity, 4),
        "unknown_review_rate": round(unknown_review_rate, 4),
        "unrelated_category_isolation_rate": round(isolation_rate, 4),
        "action_contract_failures": action_failures,
        "registry_contract_failures": registry_failures,
        "group_results": group_results,
        "predicted_status_counts": dict(
            Counter(str(row["predicted_status"]) for row in results)
        ),
        "passed_development_gate": passed,
        "specialist_status": specialist_status,
        "official_organization_registry_used": False,
        "permission_restricted_source_used": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "independent_accuracy": False,
        "development_dataset": str(DATASET_PATH),
        "mismatches": str(MISMATCH_PATH),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("TERRORISM & EXTREMISM V2 BEHAVIOR-ONLY DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {len(results)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Terrorism recall: {terrorism_recall * 100:.2f}%")
    print(f"Safe specificity: {safe_specificity * 100:.2f}%")
    print(f"Unknown-status review rate: {unknown_review_rate * 100:.2f}%")
    print(f"Unrelated-category isolation: {isolation_rate * 100:.2f}%")
    print(f"Action-contract failures: {action_failures}")
    print(f"Registry-contract failures: {registry_failures}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, metrics in group_results.items():
        print(f"{group}: {metrics['correct']}/{metrics['records']}")
    print()
    print(f"Passed 85% development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Official organization registry used: False")
    print("Permission-restricted source used: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
