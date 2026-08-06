from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from app.policy_config import (
    normalize_category_name,
)
from app.services.fusion_service import (
    fuse_moderation_decision,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

TEST_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "hatexplain"
    / "test.csv"
)

REPORT_DIRECTORY = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "hatexplain"
)

REPORT_PATH = (
    REPORT_DIRECTORY
    / "baseline_report.json"
)

MISMATCH_PATH = (
    REPORT_DIRECTORY
    / "baseline_mismatches.csv"
)


EXPECTED_CATEGORIES = [
    "Normal/Ignore",
    "Abusive Words",
    "Hate Speech & Discrimination",
]


def parse_arguments() -> (
    argparse.Namespace
):
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate TrustScope against "
            "the HateXplain test split."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    return parser.parse_args()


def load_records(
    limit: int | None,
) -> list[dict[str, str]]:
    if not TEST_PATH.exists():
        raise FileNotFoundError(
            f"Test dataset missing: "
            f"{TEST_PATH}"
        )

    with TEST_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as input_file:
        records = list(
            csv.DictReader(
                input_file
            )
        )

    if limit is not None:
        if limit <= 0:
            raise ValueError(
                "--limit must be greater "
                "than zero."
            )

        records = records[:limit]

    if not records:
        raise RuntimeError(
            "No test records were loaded."
        )

    return records


def normalize_category(
    category: str,
) -> str:
    try:
        return normalize_category_name(
            category
        )

    except (
        ValueError,
        KeyError,
    ):
        return category.strip()


def evaluate_record(
    record: dict[str, str],
) -> dict[str, Any]:
    result = (
        fuse_moderation_decision(
            text=record["text"],
            source_context="user",
            input_sources=["text"],
        )
    )

    expected_category = (
        normalize_category(
            record["category"]
        )
    )

    predicted_category = (
        normalize_category(
            str(
                result.get(
                    "category",
                    "Normal/Ignore",
                )
            )
        )
    )

    return {
        "record_id": (
            record["record_id"]
        ),
        "expected_category": (
            expected_category
        ),
        "predicted_category": (
            predicted_category
        ),
        "correct": (
            expected_category
            == predicted_category
        ),
        "confidence": float(
            result.get(
                "confidence",
                0.0,
            )
        ),
        "action": str(
            result.get(
                "action",
                "",
            )
        ),
        "matched_signals": list(
            result.get(
                "matched_signals",
                [],
            )
        ),
        "decision_sources": list(
            result.get(
                "decision_sources",
                [],
            )
        ),
    }


def write_mismatches(
    evaluations: list[
        dict[str, Any]
    ],
) -> int:
    mismatches = [
        result
        for result in evaluations
        if not result["correct"]
    ]

    fieldnames = [
        "record_id",
        "expected_category",
        "predicted_category",
        "confidence",
        "action",
        "matched_signals",
        "decision_sources",
    ]

    with MISMATCH_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for mismatch in mismatches:
            row = {
                key: mismatch[key]
                for key in fieldnames
            }

            row["matched_signals"] = (
                json.dumps(
                    mismatch[
                        "matched_signals"
                    ],
                    ensure_ascii=False,
                )
            )

            row["decision_sources"] = (
                json.dumps(
                    mismatch[
                        "decision_sources"
                    ],
                    ensure_ascii=False,
                )
            )

            writer.writerow(row)

    return len(mismatches)


def main() -> None:
    arguments = parse_arguments()

    records = load_records(
        arguments.limit
    )

    REPORT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    evaluations: list[
        dict[str, Any]
    ] = []

    print(
        "Evaluating the HateXplain "
        "test split..."
    )

    print(
        f"Records: {len(records):,}"
    )

    for index, record in enumerate(
        records,
        start=1,
    ):
        evaluations.append(
            evaluate_record(record)
        )

        if (
            index % 100 == 0
            or index == len(records)
        ):
            print(
                f"Processed "
                f"{index:,}/"
                f"{len(records):,}"
            )

    expected = [
        result["expected_category"]
        for result in evaluations
    ]

    predicted = [
        result["predicted_category"]
        for result in evaluations
    ]

    accuracy = accuracy_score(
        expected,
        predicted,
    )

    macro_precision = (
        precision_score(
            expected,
            predicted,
            labels=EXPECTED_CATEGORIES,
            average="macro",
            zero_division=0,
        )
    )

    macro_recall = recall_score(
        expected,
        predicted,
        labels=EXPECTED_CATEGORIES,
        average="macro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        expected,
        predicted,
        labels=EXPECTED_CATEGORIES,
        average="macro",
        zero_division=0,
    )

    weighted_f1 = f1_score(
        expected,
        predicted,
        labels=EXPECTED_CATEGORIES,
        average="weighted",
        zero_division=0,
    )

    report_data = (
        classification_report(
            expected,
            predicted,
            labels=EXPECTED_CATEGORIES,
            output_dict=True,
            zero_division=0,
        )
    )

    matrix = confusion_matrix(
        expected,
        predicted,
        labels=EXPECTED_CATEGORIES,
    )

    confusion_data = {
        expected_category: {
            predicted_category: int(
                matrix[
                    expected_index,
                    predicted_index,
                ]
            )
            for (
                predicted_index,
                predicted_category,
            )
            in enumerate(
                EXPECTED_CATEGORIES
            )
        }
        for (
            expected_index,
            expected_category,
        )
        in enumerate(
            EXPECTED_CATEGORIES
        )
    }

    correct_count = sum(
        result["correct"]
        for result in evaluations
    )

    mismatch_count = (
        write_mismatches(
            evaluations
        )
    )

    category_results = {}

    for category in EXPECTED_CATEGORIES:
        result = report_data.get(
            category,
            {},
        )

        category_results[category] = {
            "support": int(
                result.get(
                    "support",
                    0,
                )
            ),
            "precision_percent": round(
                float(
                    result.get(
                        "precision",
                        0.0,
                    )
                )
                * 100,
                2,
            ),
            "recall_percent": round(
                float(
                    result.get(
                        "recall",
                        0.0,
                    )
                )
                * 100,
                2,
            ),
            "f1_percent": round(
                float(
                    result.get(
                        "f1-score",
                        0.0,
                    )
                )
                * 100,
                2,
            ),
        }

    report = {
        "benchmark": "HateXplain",
        "evaluation_type": (
            "public_human_labelled_"
            "official_test_split"
        ),
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "records_evaluated": len(
            evaluations
        ),
        "correct_predictions": int(
            correct_count
        ),
        "incorrect_predictions": (
            len(evaluations)
            - int(correct_count)
        ),
        "accuracy_percent": round(
            accuracy * 100,
            2,
        ),
        "macro_precision_percent": round(
            macro_precision * 100,
            2,
        ),
        "macro_recall_percent": round(
            macro_recall * 100,
            2,
        ),
        "macro_f1_percent": round(
            macro_f1 * 100,
            2,
        ),
        "weighted_f1_percent": round(
            weighted_f1 * 100,
            2,
        ),
        "category_results": (
            category_results
        ),
        "prediction_counts": dict(
            sorted(
                Counter(
                    predicted
                ).items()
            )
        ),
        "confusion_matrix": (
            confusion_data
        ),
        "mismatch_records": (
            mismatch_count
        ),
        "important_note": (
            "This is the pre-training "
            "baseline. The test split must "
            "not be used for training, RAG, "
            "threshold selection, or prompt "
            "construction."
        ),
    }

    with REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            report,
            output_file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print("HATEXPLAIN BASELINE RESULTS")
    print("=" * 60)

    print(
        f"Records evaluated: "
        f"{len(evaluations):,}"
    )

    print(
        f"Correct predictions: "
        f"{int(correct_count):,}"
    )

    print(
        f"Incorrect predictions: "
        f"{len(evaluations) - int(correct_count):,}"
    )

    print(
        f"Accuracy: "
        f"{accuracy * 100:.2f}%"
    )

    print(
        f"Macro precision: "
        f"{macro_precision * 100:.2f}%"
    )

    print(
        f"Macro recall: "
        f"{macro_recall * 100:.2f}%"
    )

    print(
        f"Macro F1: "
        f"{macro_f1 * 100:.2f}%"
    )

    print(
        f"Weighted F1: "
        f"{weighted_f1 * 100:.2f}%"
    )

    print()
    print("CATEGORY RESULTS")
    print("-" * 60)

    for category, result in (
        category_results.items()
    ):
        print(category)

        print(
            f"  Support: "
            f"{result['support']:,}"
        )

        print(
            f"  Precision: "
            f"{result['precision_percent']:.2f}%"
        )

        print(
            f"  Recall: "
            f"{result['recall_percent']:.2f}%"
        )

        print(
            f"  F1: "
            f"{result['f1_percent']:.2f}%"
        )

    print()
    print(
        f"Mismatches saved: "
        f"{MISMATCH_PATH}"
    )

    print(
        f"Report saved: "
        f"{REPORT_PATH}"
    )


if __name__ == "__main__":
    main()