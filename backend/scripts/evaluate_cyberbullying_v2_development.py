from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.services.cyberbullying_boundary_service import (
    ABUSIVE_CATEGORY,
    CYBER_CATEGORY,
    analyze_cyberbullying_boundary,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "datasets" / "development" / "cyberbullying_v1" / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "cyberbullying" / "development_v2"


ABUSIVE_CASES = (
    "You are a bitch.",
    "He is a motherfucker.",
    "You are a worthless loser.",
    "She called him a stupid idiot.",
    "That person is a disgusting asshole.",
    "You are pathetic and useless.",
    "He called the employee an ugly bastard.",
    "You stupid fucker.",
    "She told him, 'you are an idiot.'",
    "That user is a worthless bitch.",
    "You are an ugly loser.",
    "He called her a pathetic asshole.",
    "You useless bastard.",
    "She said that person was stupid.",
    "You are a disgusting motherfucker.",
    "He called the man a fucker.",
    "You pathetic idiot.",
    "That user is a stupid loser.",
    "She called him a worthless bastard.",
    "You are a disgusting bitch.",
)


def expected_for(group: str) -> str:
    if group in {"repeated_targeted_abuse", "unwanted_contact", "coordinated_harassment", "targeted_threat"}:
        return CYBER_CATEGORY
    return ""


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"Run the V1 development baseline first: {SOURCE}")
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    cases = [
        (row["case_id"], row["group"], row["text"], expected_for(row["group"]))
        for row in source_rows
    ]
    cases.extend(
        (f"CB-ABU-{index:03d}", "abusive_words_boundary", text, ABUSIVE_CATEGORY)
        for index, text in enumerate(ABUSIVE_CASES, 1)
    )

    results: list[dict[str, object]] = []
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    action_failures = masking_failures = category_mix_failures = 0
    for case_id, group, text, expected in cases:
        result = analyze_cyberbullying_boundary(text)
        predicted = str(result.get("primary_category", ""))
        correct = predicted == expected
        if predicted == CYBER_CATEGORY and not result.get("human_review_required"):
            action_failures += 1
        if predicted == ABUSIVE_CATEGORY:
            if "*" not in str(result.get("masked_text", "")):
                masking_failures += 1
            if result.get("human_review_required"):
                action_failures += 1
        if predicted == CYBER_CATEGORY and ABUSIVE_CATEGORY in result.get("supporting_categories", []):
            if result.get("primary_category") != CYBER_CATEGORY:
                category_mix_failures += 1
        groups[group]["total"] += 1
        groups[group]["correct"] += int(correct)
        results.append(
            {
                "case_id": case_id,
                "group": group,
                "expected_category": expected or "No boundary override",
                "predicted_category": predicted or "No boundary override",
                "correct": correct,
                "decision_type": result.get("decision_type", ""),
                "text": text,
            }
        )

    correct_count = sum(int(row["correct"]) for row in results)
    accuracy = correct_count / len(results)
    positive_labels = (CYBER_CATEGORY, ABUSIVE_CATEGORY)
    label_metrics: dict[str, dict[str, float | int]] = {}
    for label in positive_labels:
        tp = sum(row["expected_category"] == label and row["predicted_category"] == label for row in results)
        fp = sum(row["expected_category"] != label and row["predicted_category"] == label for row in results)
        fn = sum(row["expected_category"] == label and row["predicted_category"] != label for row in results)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        label_metrics[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(row["expected_category"] == label for row in results),
        }

    every_group_passes = all(
        values["correct"] / values["total"] >= 0.85
        for values in groups.values()
    )
    passed = (
        accuracy >= 0.85
        and all(
            float(label_metrics[label][metric]) >= 0.85
            for label in positive_labels
            for metric in ("precision", "recall", "f1")
        )
        and action_failures == 0
        and masking_failures == 0
        and category_mix_failures == 0
        and every_group_passes
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    mismatch_path = REPORT_DIR / "mismatches.csv"
    report_path = REPORT_DIR / "report.json"
    with mismatch_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(row for row in results if not row["correct"])
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(results),
        "accuracy": round(accuracy, 4),
        "label_metrics": label_metrics,
        "action_contract_failures": action_failures,
        "masking_failures": masking_failures,
        "category_mix_failures": category_mix_failures,
        "every_group_passes_85_percent": every_group_passes,
        "group_results": {
            group: {"correct": values["correct"], "total": values["total"]}
            for group, values in sorted(groups.items())
        },
        "passed_development_gate": passed,
        "policy_change": "Abusive Words now masks detected terms and limits distribution.",
        "notice": "Development evidence only; not independent accuracy.",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("CYBERBULLYING & ABUSIVE-WORD BOUNDARY V2 DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {len(results)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    for label in positive_labels:
        values = label_metrics[label]
        print(
            f"{label}: precision {values['precision'] * 100:.2f}% | "
            f"recall {values['recall'] * 100:.2f}% | F1 {values['f1'] * 100:.2f}%"
        )
    print(f"Action-contract failures: {action_failures}")
    print(f"Masking failures: {masking_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, values in sorted(groups.items()):
        print(f"{group}: {values['correct']}/{values['total']}")
    print(f"\nPassed development gate: {passed}")
    print(f"Report: {report_path}")
    print(f"Mismatches: {mismatch_path}")
    print("The specialist is not connected to live moderation.")


if __name__ == "__main__":
    main()
