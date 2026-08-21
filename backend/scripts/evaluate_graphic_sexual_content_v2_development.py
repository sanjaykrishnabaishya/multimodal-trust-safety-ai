from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.graphic_sexual_content_v2_service import (
    HARASSMENT_ACTION,
    SEXUAL_ACTION,
    SEXUAL_CATEGORY,
    SEXUAL_HARASSMENT_CATEGORY,
    analyze_graphic_sexual_content_v2,
)


ROOT = Path(__file__).resolve().parents[2]
V1_DATASET_PATH = (
    ROOT
    / "datasets"
    / "development"
    / "graphic_sexual_content_v1"
    / "development.csv"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "development_v2"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.csv"


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def expected_boundary(expected_category: str) -> str:
    if expected_category == SEXUAL_CATEGORY:
        return "graphic_sexual_content"
    if expected_category == SEXUAL_HARASSMENT_CATEGORY:
        return "sexual_harassment"
    return "no_override"


def predicted_boundary(category: object) -> str:
    if category == SEXUAL_CATEGORY:
        return "graphic_sexual_content"
    if category == SEXUAL_HARASSMENT_CATEGORY:
        return "sexual_harassment"
    return "no_override"


def main() -> None:
    if not V1_DATASET_PATH.is_file():
        raise FileNotFoundError(f"V1 development dataset is missing: {V1_DATASET_PATH}")
    with V1_DATASET_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 140:
        raise RuntimeError(f"Expected 140 V1 development rows; found {len(rows)}")

    confusion: Counter[tuple[str, str]] = Counter()
    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    action_contract_failures = 0
    category_mix_failures = 0
    results: list[dict[str, Any]] = []

    for row in rows:
        expected = expected_boundary(row["expected_category"])
        existing_category = (
            row["expected_category"]
            if row["group"] == "unrelated_category_isolation"
            else "Normal/Ignore"
        )
        result = analyze_graphic_sexual_content_v2(
            row["text"],
            existing_category=existing_category,
        )
        predicted = predicted_boundary(result.get("category"))
        confusion[(expected, predicted)] += 1
        correct = expected == predicted
        group_totals[row["group"]] += 1
        group_correct[row["group"]] += int(correct)

        action_failure = False
        if predicted == "graphic_sexual_content":
            action_failure = bool(
                result.get("action") != SEXUAL_ACTION
                or result.get("human_review_required") is not True
                or result.get("automatic_enforcement_allowed") is not False
            )
        elif predicted == "sexual_harassment":
            action_failure = bool(
                result.get("action") != HARASSMENT_ACTION
                or result.get("human_review_required") is not True
                or result.get("automatic_enforcement_allowed") is not False
            )
        mix_failure = bool(
            row["group"] == "unrelated_category_isolation"
            and predicted != "no_override"
        )
        action_contract_failures += int(action_failure)
        category_mix_failures += int(mix_failure)
        results.append(
            {
                **row,
                "expected_boundary": expected,
                "predicted_boundary": predicted,
                "predicted_category": result.get("category"),
                "predicted_action": result.get("action"),
                "status": result.get("status"),
                "correct": correct,
                "action_contract_failure": action_failure,
                "category_mix_failure": mix_failure,
            }
        )

    labels = ["graphic_sexual_content", "sexual_harassment", "no_override"]
    label_results: dict[str, dict[str, float | int]] = {}
    for label in labels:
        tp = confusion[(label, label)]
        fp = sum(confusion[(other, label)] for other in labels if other != label)
        fn = sum(confusion[(label, other)] for other in labels if other != label)
        label_results[label] = {
            "support": sum(confusion[(label, other)] for other in labels),
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn),
        }
    group_results = {
        group: {
            "correct": group_correct[group],
            "records": total,
            "accuracy": ratio(group_correct[group], total),
        }
        for group, total in sorted(group_totals.items())
    }
    records = len(results)
    accuracy = ratio(sum(bool(item["correct"]) for item in results), records)
    minimum_group_accuracy = min(
        item["accuracy"] for item in group_results.values()
    )
    passed = bool(
        accuracy >= 0.85
        and label_results["graphic_sexual_content"]["precision"] >= 0.85
        and label_results["graphic_sexual_content"]["recall"] >= 0.85
        and label_results["sexual_harassment"]["precision"] >= 0.85
        and label_results["sexual_harassment"]["recall"] >= 0.85
        and label_results["no_override"]["recall"] >= 0.95
        and minimum_group_accuracy >= 0.85
        and action_contract_failures == 0
        and category_mix_failures == 0
    )

    report = {
        "component": "Graphic, Obscene & Sexual Content V2 boundary development",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "accuracy": accuracy,
        "label_results": label_results,
        "minimum_group_accuracy": minimum_group_accuracy,
        "group_results": group_results,
        "action_contract_failures": action_contract_failures,
        "category_mix_failures": category_mix_failures,
        "passed_development_gate": passed,
        "external_or_restricted_data_used": False,
        "explicit_descriptions_stored": False,
        "child_exploitation_boundary_output_enabled": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    fields = [
        "case_id",
        "group",
        "expected_boundary",
        "predicted_boundary",
        "predicted_category",
        "predicted_action",
        "status",
        "action_contract_failure",
        "category_mix_failure",
        "text",
    ]
    with MISMATCH_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in results:
            if not item["correct"] or item["action_contract_failure"]:
                writer.writerow({field: item.get(field) for field in fields})

    print("GRAPHIC/SEXUAL CONTENT & SEXUAL HARASSMENT V2 DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {records}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    for label in labels:
        metrics = label_results[label]
        print(
            f"{label}: precision {float(metrics['precision']) * 100:.2f}% | "
            f"recall {float(metrics['recall']) * 100:.2f}% | "
            f"F1 {float(metrics['f1']) * 100:.2f}%"
        )
    print(f"Action-contract failures: {action_contract_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, item in group_results.items():
        print(f"{group}: {item['correct']}/{item['records']}")
    print(f"\nPassed development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("External or restricted data used: False")
    print("Explicit sexual descriptions stored: False")
    print("Child Exploitation ownership preserved: True")
    print("The specialist is not connected to live moderation.")


if __name__ == "__main__":
    main()
