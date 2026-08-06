import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_DIRECTORY = (
    Path(__file__).resolve().parents[1]
)

PROJECT_DIRECTORY = (
    BACKEND_DIRECTORY.parent
)

sys.path.insert(
    0,
    str(BACKEND_DIRECTORY),
)

from app.services.fusion_service import (  # noqa: E402
    fuse_moderation_decision,
)


DATASET_PATH = (
    PROJECT_DIRECTORY
    / "datasets"
    / "text_dataset.csv"
)

REPORT_DIRECTORY = (
    BACKEND_DIRECTORY
    / "evaluation_reports"
)

SUMMARY_PATH = (
    REPORT_DIRECTORY
    / "text_evaluation_summary.json"
)

MISMATCH_PATH = (
    REPORT_DIRECTORY
    / "text_evaluation_mismatches.csv"
)


def load_dataset(
    limit: int | None,
) -> list[dict[str, str]]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            "Dataset not found: "
            f"{DATASET_PATH}"
        )

    with DATASET_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as dataset_file:
        records = list(
            csv.DictReader(
                dataset_file
            )
        )

    if limit is not None:
        records = records[:limit]

    return records


def safe_percentage(
    numerator: int,
    denominator: int,
) -> float:
    if denominator == 0:
        return 0.0

    return round(
        (
            numerator
            / denominator
        )
        * 100,
        2,
    )


def evaluate_records(
    records: list[dict[str, str]],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
]:
    total_records = len(records)
    correct_predictions = 0

    category_totals: dict[
        str,
        int,
    ] = defaultdict(int)

    category_correct: dict[
        str,
        int,
    ] = defaultdict(int)

    confusion_counts: dict[
        str,
        dict[str, int],
    ] = defaultdict(
        lambda: defaultdict(int)
    )

    mismatches: list[
        dict[str, Any]
    ] = []

    for position, record in enumerate(
        records,
        start=1,
    ):
        expected_category = (
            record.get(
                "category",
                "",
            ).strip()
        )

        content_text = (
            record.get(
                "text",
                "",
            ).strip()
        )

        source_context = (
            record.get(
                "source_context",
                "unknown",
            ).strip()
            or "unknown"
        )

        decision = (
            fuse_moderation_decision(
                text=content_text,
                source_context=(
                    source_context
                ),
                input_sources=["text"],
            )
        )

        predicted_category = str(
            decision.get(
                "category",
                "Unknown",
            )
        )

        category_totals[
            expected_category
        ] += 1

        confusion_counts[
            expected_category
        ][predicted_category] += 1

        is_correct = (
            predicted_category
            == expected_category
        )

        if is_correct:
            correct_predictions += 1

            category_correct[
                expected_category
            ] += 1

        else:
            mismatches.append(
                {
                    "id": record.get(
                        "id",
                        "",
                    ),
                    "text": content_text,
                    "expected_category": (
                        expected_category
                    ),
                    "predicted_category": (
                        predicted_category
                    ),
                    "predicted_confidence": (
                        decision.get(
                            "confidence",
                            0.0,
                        )
                    ),
                    "predicted_action": (
                        decision.get(
                            "action",
                            "",
                        )
                    ),
                    "matched_signals": (
                        " | ".join(
                            decision.get(
                                "matched_signals",
                                [],
                            )
                        )
                    ),
                }
            )

        print(
            f"[{position}/{total_records}] "
            f"Expected: {expected_category} | "
            f"Predicted: {predicted_category} | "
            f"{'PASS' if is_correct else 'FAIL'}"
        )

    category_results: dict[
        str,
        dict[str, Any],
    ] = {}

    for category in sorted(
        category_totals
    ):
        category_total = (
            category_totals[
                category
            ]
        )

        correct_total = (
            category_correct[
                category
            ]
        )

        category_results[
            category
        ] = {
            "total": category_total,
            "correct": correct_total,
            "incorrect": (
                category_total
                - correct_total
            ),
            "accuracy_percent": (
                safe_percentage(
                    correct_total,
                    category_total,
                )
            ),
        }

    confusion_matrix = {
        expected: dict(
            sorted(
                predictions.items()
            )
        )
        for expected, predictions in sorted(
            confusion_counts.items()
        )
    }

    summary = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "dataset": str(
            DATASET_PATH
        ),
        "records_evaluated": (
            total_records
        ),
        "correct_predictions": (
            correct_predictions
        ),
        "incorrect_predictions": (
            total_records
            - correct_predictions
        ),
        "overall_accuracy_percent": (
            safe_percentage(
                correct_predictions,
                total_records,
            )
        ),
        "category_results": (
            category_results
        ),
        "confusion_matrix": (
            confusion_matrix
        ),
    }

    return summary, mismatches


def save_reports(
    summary: dict[str, Any],
    mismatches: list[dict[str, Any]],
) -> None:
    REPORT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SUMMARY_PATH.open(
        "w",
        encoding="utf-8",
    ) as summary_file:
        json.dump(
            summary,
            summary_file,
            indent=2,
            ensure_ascii=False,
        )

    mismatch_columns = [
        "id",
        "text",
        "expected_category",
        "predicted_category",
        "predicted_confidence",
        "predicted_action",
        "matched_signals",
    ]

    with MISMATCH_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as mismatch_file:
        writer = csv.DictWriter(
            mismatch_file,
            fieldnames=(
                mismatch_columns
            ),
        )

        writer.writeheader()
        writer.writerows(
            mismatches
        )


def display_summary(
    summary: dict[str, Any],
    mismatch_count: int,
) -> None:
    print()
    print("=" * 60)
    print("TEXT MODERATION EVALUATION")
    print("=" * 60)

    print(
        "Records evaluated: "
        f"{summary['records_evaluated']}"
    )

    print(
        "Correct predictions: "
        f"{summary['correct_predictions']}"
    )

    print(
        "Incorrect predictions: "
        f"{summary['incorrect_predictions']}"
    )

    print(
        "Overall accuracy: "
        f"{summary['overall_accuracy_percent']}%"
    )

    print()
    print("CATEGORY RESULTS")
    print("-" * 60)

    for category, result in (
        summary[
            "category_results"
        ].items()
    ):
        print(
            f"{category}: "
            f"{result['correct']}/"
            f"{result['total']} "
            f"({result['accuracy_percent']}%)"
        )

    print()
    print(
        "Mismatch records saved: "
        f"{mismatch_count}"
    )

    print(
        "Summary report: "
        f"{SUMMARY_PATH}"
    )

    print(
        "Mismatch report: "
        f"{MISMATCH_PATH}"
    )


def parse_arguments() -> (
    argparse.Namespace
):
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the TrustScope "
            "moderation engine using the "
            "synthetic text dataset."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Optional number of dataset "
            "records to evaluate."
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    if (
        arguments.limit is not None
        and arguments.limit < 1
    ):
        raise ValueError(
            "--limit must be at least 1."
        )

    records = load_dataset(
        arguments.limit
    )

    if not records:
        raise ValueError(
            "The text dataset is empty."
        )

    summary, mismatches = (
        evaluate_records(
            records
        )
    )

    save_reports(
        summary,
        mismatches,
    )

    display_summary(
        summary,
        len(mismatches),
    )


if __name__ == "__main__":
    main()