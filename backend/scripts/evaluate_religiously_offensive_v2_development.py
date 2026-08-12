from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.religiously_offensive_v2_service import (
    HATE_CATEGORY,
    RELIGIOUS_CATEGORY,
    analyze_religiously_offensive_v2,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v1"
    / "development.csv"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "development_v2"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.csv"

MINIMUM_OVERALL_ACCURACY = 0.85
MINIMUM_RELIGIOUS_PRECISION = 0.85
MINIMUM_RELIGIOUS_RECALL = 0.85
MINIMUM_SAFE_SPECIFICITY = 0.85
MINIMUM_BOUNDARY_ACCURACY = 0.85
MAXIMUM_ACTION_CONTRACT_FAILURES = 0
MAXIMUM_CATEGORY_MIX_FAILURES = 0


def load_rows() -> list[dict[str, Any]]:
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(
            "The V1 development dataset was not found. Run the V1 baseline first."
        )
    rows: list[dict[str, Any]] = []
    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    **row,
                    "religious_violation": str(row["religious_violation"]).casefold()
                    == "true",
                }
            )
    return rows


def expected_component_decision(row: dict[str, Any]) -> str:
    if row["religious_violation"]:
        return "religiously_offensive_review_only"
    if row["expected_category"] == HATE_CATEGORY:
        return "protected_followers_hate_boundary"
    if row["group"] == "safe_reporting_education_criticism":
        return "safe_reporting_education_or_criticism"
    return "no_religious_boundary_override"


def main() -> None:
    rows = load_rows()
    results: list[dict[str, Any]] = []

    for row in rows:
        analysis = analyze_religiously_offensive_v2(str(row["text"]))
        expected_decision = expected_component_decision(row)
        correct = analysis["decision"] == expected_decision
        action_failure = bool(
            analysis["detected"]
            and (
                not analysis["human_review_required"]
                or analysis["action"] != "Remove and send for human review"
                or analysis["automatic_enforcement_allowed"]
            )
        )
        category_mix_failure = bool(
            analysis["detected"]
            and row["expected_category"] != RELIGIOUS_CATEGORY
        )
        results.append(
            {
                **row,
                "expected_component_decision": expected_decision,
                "predicted_component_decision": analysis["decision"],
                "predicted_category": analysis["primary_category"],
                "boundary_category": analysis["boundary_category"],
                "correct": correct,
                "action_contract_failure": action_failure,
                "category_mix_failure": category_mix_failure,
                "confidence": analysis["confidence"],
                "signals": "|".join(analysis["signals"]),
            }
        )

    total = len(results)
    correct_count = sum(row["correct"] for row in results)
    true_positives = sum(
        row["religious_violation"]
        and row["predicted_category"] == RELIGIOUS_CATEGORY
        for row in results
    )
    false_positives = sum(
        not row["religious_violation"]
        and row["predicted_category"] == RELIGIOUS_CATEGORY
        for row in results
    )
    false_negatives = sum(
        row["religious_violation"]
        and row["predicted_category"] != RELIGIOUS_CATEGORY
        for row in results
    )
    true_negatives = total - true_positives - false_positives - false_negatives
    precision = true_positives / (true_positives + false_positives) if (
        true_positives + false_positives
    ) else 0.0
    recall = true_positives / (true_positives + false_negatives) if (
        true_positives + false_negatives
    ) else 0.0
    specificity = true_negatives / (true_negatives + false_positives) if (
        true_negatives + false_positives
    ) else 0.0

    boundary_rows = [
        row for row in results if not row["religious_violation"]
    ]
    boundary_correct = sum(row["correct"] for row in boundary_rows)
    boundary_accuracy = boundary_correct / len(boundary_rows)
    action_failures = sum(row["action_contract_failure"] for row in results)
    category_mix_failures = sum(row["category_mix_failure"] for row in results)
    accuracy = correct_count / total

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[str(row["group"])].append(row)
    group_results = {
        group: {
            "records": len(group_rows),
            "correct": sum(row["correct"] for row in group_rows),
        }
        for group, group_rows in sorted(grouped.items())
    }
    passed = bool(
        accuracy >= MINIMUM_OVERALL_ACCURACY
        and precision >= MINIMUM_RELIGIOUS_PRECISION
        and recall >= MINIMUM_RELIGIOUS_RECALL
        and specificity >= MINIMUM_SAFE_SPECIFICITY
        and boundary_accuracy >= MINIMUM_BOUNDARY_ACCURACY
        and action_failures <= MAXIMUM_ACTION_CONTRACT_FAILURES
        and category_mix_failures <= MAXIMUM_CATEGORY_MIX_FAILURES
    )

    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    mismatches = [row for row in results if not row["correct"]]
    with MISMATCH_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(mismatches)

    report = {
        "candidate": "religiously-offensive-v2-development",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": total,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "boundary_accuracy": round(boundary_accuracy, 4),
        "true_positives": true_positives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "group_results": group_results,
        "passed_development_gate": passed,
        "live_moderation_changed": False,
        "automatic_enforcement_allowed": False,
        "independent_accuracy": False,
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("RELIGIOUSLY OFFENSIVE CONTENT V2 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Records: {total}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Precision: {precision * 100:.2f}%")
    print(f"Recall: {recall * 100:.2f}%")
    print(f"Safe specificity: {specificity * 100:.2f}%")
    print(f"Boundary accuracy: {boundary_accuracy * 100:.2f}%")
    print(f"False positives: {false_positives}")
    print(f"False negatives: {false_negatives}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, metrics in group_results.items():
        print(f"{group}: {metrics['correct']}/{metrics['records']}")
    print()
    print(f"Passed 85% development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Live moderation changed: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
