from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.structured_claim_service import parse_structured_claim


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SCRIPT_DIRECTORY.parent
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent
DEVELOPMENT_DATASET = (
    PROJECT_DIRECTORY
    / "datasets"
    / "development"
    / "stable_knowledge_v3"
    / "development.csv"
)
REPORT_PATH = (
    PROJECT_DIRECTORY
    / "reports"
    / "evaluation"
    / "stable_knowledge_v3"
    / "rc2_development"
    / "routing_report.json"
)


STABLE_PARAPHRASES: tuple[tuple[str, str], ...] = (
    ("capital_of", "Paris serves as the capital of France."),
    ("capital_of", "France has Paris as its capital."),
    ("capital_of", "Tokyo served as the capital of Japan."),
    ("located_in", "The Colosseum is situated in Rome."),
    ("located_in", "The Taj Mahal is found in Agra."),
    ("country_of", "Kyoto belongs to Japan."),
    ("country_of", "Bavaria is part of Germany."),
    ("continent_of", "Kenya is located on the continent of Africa."),
    ("borders", "Portugal is adjacent to Spain."),
    ("borders", "Germany neighbours Poland."),
    ("orbits", "The Moon circles around Earth."),
    ("orbits", "Phobos revolves around Mars."),
    ("chemical_symbol", "Gold has the chemical symbol Au."),
    ("chemical_symbol", "Silver uses the chemical symbol Ag."),
    ("atomic_number", "Gold has the atomic number 79."),
    ("atomic_number", "Oxygen has atomic number 8."),
    ("founded_by", "Microsoft was established by Bill Gates."),
    ("founded_in", "Google was established in 1998."),
    ("invented_by", "The telephone was invented by Alexander Graham Bell."),
    ("discovered_by", "Penicillin was discovered by Alexander Fleming."),
    ("born_in", "Will Smith was born in Philadelphia."),
    ("born_in", "Marie Curie was born in Warsaw."),
    ("born_on", "Albert Einstein was born on 14 March 1879."),
    ("ended_in", "World War II came to an end in 1945."),
    ("instance_of", "A blue whale is a mammal."),
    ("freezes_at", "Water freezes at 0 degrees Celsius."),
    ("boils_at", "Water boils at 100 degrees Celsius."),
)


BOUNDARY_CASES: tuple[str, ...] = (
    "A report says Paris is the capital of France.",
    "According to a post, Paris is the capital of France.",
    "A headline claims that the Moon revolves around Earth.",
    "Someone said gold has the chemical symbol Au.",
    "It is rumored that Tokyo is the capital of Japan.",
    "The message claims that water boils at 100 degrees Celsius.",
    "Paris may be the capital of France.",
    "The Moon might orbit Earth.",
    "The Eiffel Tower could be located in Paris.",
    "Paris will be the capital of France.",
    "The meeting is in Paris.",
    "The appointment is in London.",
    "The delivery is in Mumbai.",
    "The event is in Berlin.",
    "Please share that Paris is the capital of France.",
    "Send me proof that the Moon orbits Earth.",
    "Is Paris the capital of France?",
    "Does the Moon orbit Earth?",
    "Where is the Eiffel Tower located?",
    "What is the chemical symbol for gold?",
    "I think Paris is the most beautiful city.",
    "In my opinion, water is the best drink.",
    "Breaking: Paris is the capital of France.",
    "Today the Moon is visible from Delhi.",
    "The latest post says Ottawa is the capital of Canada.",
    "A private message says schools close tomorrow.",
    "This video claims the Earth revolves around the Moon.",
    "An article reports that gold has atomic number 79.",
    "The package is in France.",
    "Our team is in Japan.",
)


def load_original_development_rows() -> list[dict[str, str]]:
    if not DEVELOPMENT_DATASET.exists():
        raise FileNotFoundError(
            f"Development dataset was not found: {DEVELOPMENT_DATASET}"
        )
    with DEVELOPMENT_DATASET.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def actual_route(claim: str) -> tuple[str, dict[str, Any]]:
    parsed = parse_structured_claim(claim)
    route = (
        "stable_knowledge"
        if parsed.get("suitable_for_stable_knowledge", False)
        else "other_policy_path"
    )
    return route, parsed


def main() -> None:
    rows = load_original_development_rows()
    results: list[dict[str, Any]] = []

    for row in rows:
        expected = str(row.get("expected_routing", ""))
        actual, parsed = actual_route(str(row.get("claim", "")))
        results.append(
            {
                "case_id": row.get("case_id"),
                "suite": "original_v3_development_regression",
                "expected": expected,
                "actual": actual,
                "correct": expected == actual,
                "claim": row.get("claim"),
                "relation": parsed.get("relation"),
                "warnings": parsed.get("warnings", []),
            }
        )

    for index, (relation, claim) in enumerate(STABLE_PARAPHRASES, start=1):
        actual, parsed = actual_route(claim)
        results.append(
            {
                "case_id": f"RC2-STABLE-{index:03d}",
                "suite": "new_stable_paraphrases",
                "expected": "stable_knowledge",
                "actual": actual,
                "correct": (
                    actual == "stable_knowledge"
                    and parsed.get("relation") == relation
                ),
                "claim": claim,
                "relation": parsed.get("relation"),
                "expected_relation": relation,
                "warnings": parsed.get("warnings", []),
            }
        )

    for index, claim in enumerate(BOUNDARY_CASES, start=1):
        actual, parsed = actual_route(claim)
        results.append(
            {
                "case_id": f"RC2-BOUNDARY-{index:03d}",
                "suite": "new_boundary_challenges",
                "expected": "other_policy_path",
                "actual": actual,
                "correct": actual == "other_policy_path",
                "claim": claim,
                "relation": parsed.get("relation"),
                "warnings": parsed.get("warnings", []),
            }
        )

    total = len(results)
    correct = sum(bool(row["correct"]) for row in results)
    mismatches = [row for row in results if not row["correct"]]
    accuracy = round(100.0 * correct / total, 2) if total else 0.0
    passed = bool(accuracy >= 98.0 and not mismatches)

    suite_results: dict[str, dict[str, Any]] = {}
    for suite in sorted({str(row["suite"]) for row in results}):
        suite_rows = [row for row in results if row["suite"] == suite]
        suite_correct = sum(bool(row["correct"]) for row in suite_rows)
        suite_results[suite] = {
            "records": len(suite_rows),
            "correct": suite_correct,
            "accuracy_percent": round(
                100.0 * suite_correct / len(suite_rows),
                2,
            ),
        }

    report = {
        "version": "2026.08-rc2-routing-development-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "development_only": True,
        "uses_rc1_holdout_records": False,
        "uses_rc1_holdout_predictions": False,
        "uses_rc1_holdout_mismatches": False,
        "records": total,
        "correct": correct,
        "routing_accuracy_percent": accuracy,
        "passed_development_gate": passed,
        "suite_results": suite_results,
        "mismatches": mismatches,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("=" * 60)
    print("STABLE KNOWLEDGE RC2 ROUTING DEVELOPMENT CHECK")
    print("=" * 60)
    print(f"Records: {total}")
    print(f"Correct: {correct}")
    print(f"Routing accuracy: {accuracy:.2f}%")
    print(f"Mismatches: {len(mismatches)}")
    print(f"Passed development gate: {passed}")
    print("\nSUITE RESULTS")
    print("-" * 60)
    for suite, metrics in suite_results.items():
        print(
            f"{suite}: {metrics['correct']}/{metrics['records']} "
            f"({metrics['accuracy_percent']:.2f}%)"
        )
    print(f"\nReport saved: {REPORT_PATH}")
    print("No RC1 holdout record, prediction, or mismatch was used.")

    if not passed:
        print("\nDEVELOPMENT MISMATCHES")
        print("-" * 60)
        for row in mismatches:
            print(
                f"{row['case_id']}: expected {row['expected']}, "
                f"received {row['actual']}"
            )
            print(f"  {row['claim']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
