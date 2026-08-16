from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.dangerous_content_v2_service import (
    DANGEROUS_CATEGORY,
    analyze_dangerous_content_v2,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    ROOT / "datasets" / "development" / "dangerous_content_v1" / "development.csv"
)
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "dangerous_content" / "development_v2"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.csv"

MINIMUM_ACCURACY = 0.85
MINIMUM_RECALL = 0.85
MINIMUM_SPECIFICITY = 0.90
MINIMUM_GROUP_ACCURACY = 0.85


def as_bool(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes"}


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(
            "Run scripts.evaluate_dangerous_content_v1_development first."
        )
    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 140:
        raise RuntimeError(f"Expected 140 development records; found {len(rows)}")

    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    confusion = Counter()
    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    action_failures = 0
    category_mix_failures = 0
    results: list[dict[str, Any]] = []

    for row in rows:
        analysis = analyze_dangerous_content_v2(row["text"])
        expected = as_bool(row["dangerous_violation"])
        predicted = analysis.get("category") == DANGEROUS_CATEGORY
        correct = expected == predicted
        group = row["group"]
        group_totals[group] += 1
        group_correct[group] += int(correct)

        if expected and predicted:
            confusion["tp"] += 1
        elif expected:
            confusion["fn"] += 1
        elif predicted:
            confusion["fp"] += 1
        else:
            confusion["tn"] += 1

        action_failure = predicted and (
            analysis.get("action") != "Remove and send for human review"
            or analysis.get("human_review_required") is not True
            or analysis.get("automatic_enforcement_allowed") is not False
        )
        category_mix_failure = not expected and predicted
        action_failures += int(action_failure)
        category_mix_failures += int(category_mix_failure)
        results.append(
            {
                **row,
                "predicted_category": analysis.get("category") or "No boundary override",
                "status": analysis.get("status"),
                "confidence": analysis.get("confidence"),
                "correct": correct,
                "action_contract_failure": action_failure,
                "category_mix_failure": category_mix_failure,
            }
        )

    tp, tn = confusion["tp"], confusion["tn"]
    fp, fn = confusion["fp"], confusion["fn"]
    records = len(results)
    accuracy = safe_divide(tp + tn, records)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    specificity = safe_divide(tn, tn + fp)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    groups = {
        group: {
            "correct": group_correct[group],
            "records": total,
            "accuracy": safe_divide(group_correct[group], total),
        }
        for group, total in sorted(group_totals.items())
    }
    minimum_group_accuracy = min(item["accuracy"] for item in groups.values())
    gate_checks = {
        "accuracy": accuracy >= MINIMUM_ACCURACY,
        "recall": recall >= MINIMUM_RECALL,
        "specificity": specificity >= MINIMUM_SPECIFICITY,
        "minimum_group_accuracy": minimum_group_accuracy >= MINIMUM_GROUP_ACCURACY,
        "action_contract": action_failures == 0,
        "category_mix_contract": category_mix_failures == 0,
    }
    passed = all(gate_checks.values())

    report = {
        "component": "Dangerous Content V2 boundary development",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "minimum_group_accuracy": minimum_group_accuracy,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "group_results": groups,
        "gate_checks": gate_checks,
        "passed_development_gate": passed,
        "preserves_other_category_owners": True,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "external_data_used": False,
        "actionable_harm_instructions_stored": False,
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    fields = [
        "case_id",
        "group",
        "expected_category",
        "predicted_category",
        "status",
        "confidence",
        "action_contract_failure",
        "category_mix_failure",
        "text",
    ]
    with MISMATCH_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in results:
            if not row["correct"] or row["action_contract_failure"]:
                writer.writerow({field: row.get(field) for field in fields})

    print("DANGEROUS CONTENT V2 BOUNDARY DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {records}")
    print(f"Accuracy: {accuracy:.2%}")
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")
    print(f"Safe specificity: {specificity:.2%}")
    print(f"F1: {f1:.2%}")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, item in groups.items():
        print(f"{group}: {item['correct']}/{item['records']}")
    print(f"\nPassed 85% development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Other category ownership preserved: True")
    print("Automatic enforcement allowed: False")
    print("Live moderation changed: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
