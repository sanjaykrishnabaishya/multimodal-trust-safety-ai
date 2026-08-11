from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.services.hindi_abusive_context_service import (
    ABUSIVE_CATEGORY,
    CYBER_CATEGORY,
    LEXICON_PATH,
    analyze_hindi_abusive_context,
    load_lexicon,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    REPO_ROOT
    / "datasets"
    / "development"
    / "hindi_abusive_rc3"
    / "context_development.csv"
)
REPORT_DIRECTORY = (
    REPO_ROOT
    / "reports"
    / "evaluation"
    / "cyberbullying"
    / "hindi_abusive_rc3"
)
REPORT_PATH = REPORT_DIRECTORY / "context_development_report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "context_development_mismatches.csv"

NO_OVERRIDE = "No boundary override"


SAFE_AMBIGUOUS_CONTEXTS = [
    ("BC-SAFE-001", "I moved to BC, Canada last year."),
    ("BC-SAFE-002", "The inscription is dated 300 BC."),
    ("BC-SAFE-003", "Our BC plan covers business continuity."),
    ("BC-SAFE-004", "British Columbia is often shortened to BC."),
    ("BC-SAFE-005", "I stayed home bc it was raining."),
    ("MC-SAFE-001", "The MC introduced the next speaker."),
    ("MC-SAFE-002", "She is the master of ceremonies tonight."),
    ("MC-SAFE-003", "We joined a Minecraft server after school."),
    ("MC-SAFE-004", "The motorcycle club uses MC in its name."),
    ("RAND-SAFE-001", "Use the rand function to generate a number."),
    ("RAND-SAFE-002", "The South African rand changed in value."),
    ("LING-SAFE-001", "Dr Ling presented the research paper."),
    ("PAJI-SAFE-001", "Paji, please join us for tea."),
]


def build_records() -> list[dict[str, str]]:
    entries = load_lexicon()
    if not entries:
        raise RuntimeError(f"The imported lexicon was not found: {LEXICON_PATH}")

    records: list[dict[str, str]] = []
    for index, entry in enumerate(entries, start=1):
        term = entry["transliteration"]
        mode = entry["evidence_mode"]

        records.append(
            {
                "case_id": f"HIN-DIRECT-{index:03d}",
                "group": "direct_abusive_language",
                "expected_category": ABUSIVE_CATEGORY,
                "text": f"tu {term} hai",
                "term_mode": mode,
            }
        )
        records.append(
            {
                "case_id": f"HIN-REPORT-{index:03d}",
                "group": "reporting_and_education",
                "expected_category": NO_OVERRIDE,
                "text": f'The moderation guide says "{term}" is an abusive Hindi word.',
                "term_mode": mode,
            }
        )

        if index <= 60:
            records.append(
                {
                    "case_id": f"HIN-CYBER-{index:03d}",
                    "group": "repeated_cyberbullying",
                    "expected_category": CYBER_CATEGORY,
                    "text": f"tum har din mujhe {term} bolkar message karte ho",
                    "term_mode": mode,
                }
            )

    for case_id, text in SAFE_AMBIGUOUS_CONTEXTS:
        records.append(
            {
                "case_id": case_id,
                "group": "ambiguous_english_safe_context",
                "expected_category": NO_OVERRIDE,
                "text": text,
                "term_mode": "context_required",
            }
        )

    boundary_term = entries[0]["transliteration"]
    records.extend(
        [
            {
                "case_id": "HIN-BOUNDARY-HATE-001",
                "group": "category_isolation",
                "expected_category": NO_OVERRIDE,
                "text": f"This protected religious group is {boundary_term}.",
                "term_mode": "boundary",
            },
            {
                "case_id": "HIN-BOUNDARY-SEXUAL-001",
                "group": "category_isolation",
                "expected_category": NO_OVERRIDE,
                "text": f"He sent unwanted sexual messages and called her {boundary_term}.",
                "term_mode": "boundary",
            },
        ]
    )
    return records


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    records = build_records()
    write_csv(DATASET_PATH, records)

    group_results: dict[str, Counter[str]] = defaultdict(Counter)
    mismatches: list[dict[str, object]] = []
    masking_failures = 0
    category_mix_failures = 0

    for record in records:
        result = analyze_hindi_abusive_context(record["text"])
        predicted = result["primary_category"] if result["detected"] else NO_OVERRIDE
        correct = predicted == record["expected_category"]
        group_results[record["group"]]["total"] += 1
        group_results[record["group"]]["correct"] += int(correct)

        if result["detected"] and result["masked_text"] == record["text"]:
            masking_failures += 1
        if result["primary_category"] and len(result["supporting_categories"]) > 1:
            category_mix_failures += 1

        if not correct:
            mismatches.append(
                {
                    **record,
                    "predicted_category": predicted,
                    "decision_type": result["decision_type"],
                    "confidence": result["confidence"],
                    "reason": result["reason"],
                }
            )

    total = len(records)
    correct = total - len(mismatches)
    accuracy = correct / total if total else 0.0
    passed = (
        accuracy >= 0.85
        and masking_failures == 0
        and category_mix_failures == 0
        and all(
            values["correct"] / values["total"] >= 0.85
            for values in group_results.values()
        )
    )

    report = {
        "candidate": "hindi-abusive-context-rc3-development",
        "records": total,
        "correct": correct,
        "incorrect": len(mismatches),
        "accuracy_percent": round(accuracy * 100, 2),
        "masking_failures": masking_failures,
        "category_mix_failures": category_mix_failures,
        "group_results": {
            group: {
                "total": values["total"],
                "correct": values["correct"],
                "accuracy_percent": round(values["correct"] / values["total"] * 100, 2),
            }
            for group, values in sorted(group_results.items())
        },
        "passed_development_gate": passed,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "limitations": [
            "This is generated development data, not independent accuracy.",
            "The source lexicon has unknown redistribution rights.",
            "A licensed external Hinglish sentence dataset and untouched holdout are still required.",
        ],
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(MISMATCH_PATH, mismatches)

    print("HINDI/HINGLISH ABUSIVE CONTEXT RC3 DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {total}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Masking failures: {masking_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, values in sorted(group_results.items()):
        group_accuracy = values["correct"] / values["total"] * 100
        print(f"{group}: {values['correct']}/{values['total']} ({group_accuracy:.2f}%)")
    print()
    print(f"Passed development gate: {passed}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Live moderation changed: False")
    print("Frozen RC2 changed: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
