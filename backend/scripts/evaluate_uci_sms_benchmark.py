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

TEST_DATASET_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "uci_sms"
    / "test.csv"
)

REPORT_DIRECTORY = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "uci_sms"
)

REPORT_PATH = (
    REPORT_DIRECTORY
    / "baseline_report.json"
)

MISMATCH_PATH = (
    REPORT_DIRECTORY
    / "baseline_mismatches.csv"
)


NORMAL_CATEGORY = "Normal/Ignore"

SPAM_CATEGORY = (
    "Spam, Scam & Phishing"
)

EXPECTED_CATEGORIES = [
    NORMAL_CATEGORY,
    SPAM_CATEGORY,
]


def parse_arguments() -> (
    argparse.Namespace
):
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate TrustScope against the "
            "unseen UCI SMS test split."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Optionally test only the first N "
            "records. Omit this option for the "
            "complete benchmark."
        ),
    )

    return parser.parse_args()


def load_test_records(
    limit: int | None,
) -> list[dict[str, str]]:
    if not TEST_DATASET_PATH.exists():
        raise FileNotFoundError(
            "The UCI SMS test file does not "
            f"exist: {TEST_DATASET_PATH}"
        )

    with TEST_DATASET_PATH.open(
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
            "The test dataset contains "
            "no records."
        )

    return records


def normalize_prediction(
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
    expected_category = (
        normalize_prediction(
            record["category"]
        )
    )

    result = (
        fuse_moderation_decision(
            text=record["text"],
            source_context="user",
            input_sources=["text"],
        )
    )

    predicted_category = (
        normalize_prediction(
            str(
                result.get(
                    "category",
                    NORMAL_CATEGORY,
                )
            )
        )
    )

    return {
        "record_id": (
            record["record_id"]
        ),
        "text": record["text"],
        "original_label": (
            record["original_label"]
        ),
        "expected_category": (
            expected_category
        ),
        "predicted_category": (
            predicted_category
        ),
        "correct": (
            predicted_category
            == expected_category
        ),
        "severity": str(
            result.get(
                "severity",
                "",
            )
        ),
        "action": str(
            result.get(
                "action",
                "",
            )
        ),
        "confidence": float(
            result.get(
                "confidence",
                0.0,
            )
        ),
        "reason": str(
            result.get(
                "reason",
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


def safe_divide(
    numerator: int,
    denominator: int,
) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator


def build_category_results(
    evaluations: list[
        dict[str, Any]
    ],
) -> dict[str, dict[str, Any]]:
    results: dict[
        str,
        dict[str, Any]
    ] = {}

    observed_categories = sorted(
        {
            evaluation[
                "expected_category"
            ]
            for evaluation in evaluations
        }
        | set(EXPECTED_CATEGORIES)
    )

    for category in observed_categories:
        true_positive = sum(
            1
            for evaluation in evaluations
            if (
                evaluation[
                    "expected_category"
                ]
                == category
                and evaluation[
                    "predicted_category"
                ]
                == category
            )
        )

        false_positive = sum(
            1
            for evaluation in evaluations
            if (
                evaluation[
                    "expected_category"
                ]
                != category
                and evaluation[
                    "predicted_category"
                ]
                == category
            )
        )

        false_negative = sum(
            1
            for evaluation in evaluations
            if (
                evaluation[
                    "expected_category"
                ]
                == category
                and evaluation[
                    "predicted_category"
                ]
                != category
            )
        )

        support = sum(
            1
            for evaluation in evaluations
            if (
                evaluation[
                    "expected_category"
                ]
                == category
            )
        )

        precision = safe_divide(
            true_positive,
            (
                true_positive
                + false_positive
            ),
        )

        recall = safe_divide(
            true_positive,
            (
                true_positive
                + false_negative
            ),
        )

        f1 = (
            safe_divide(
                2 * precision * recall,
                precision + recall,
            )
            if (
                precision + recall
            ) > 0
            else 0.0
        )

        results[category] = {
            "support": support,
            "true_positive": (
                true_positive
            ),
            "false_positive": (
                false_positive
            ),
            "false_negative": (
                false_negative
            ),
            "precision_percent": round(
                precision * 100,
                2,
            ),
            "recall_percent": round(
                recall * 100,
                2,
            ),
            "f1_percent": round(
                f1 * 100,
                2,
            ),
        }

    return results


def write_mismatches(
    evaluations: list[
        dict[str, Any]
    ],
) -> int:
    mismatches = [
        evaluation
        for evaluation in evaluations
        if not evaluation["correct"]
    ]

    fieldnames = [
        "record_id",
        "text",
        "original_label",
        "expected_category",
        "predicted_category",
        "severity",
        "action",
        "confidence",
        "reason",
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
            output_record = {
                key: mismatch[key]
                for key in fieldnames
            }

            output_record[
                "matched_signals"
            ] = json.dumps(
                mismatch[
                    "matched_signals"
                ],
                ensure_ascii=False,
            )

            output_record[
                "decision_sources"
            ] = json.dumps(
                mismatch[
                    "decision_sources"
                ],
                ensure_ascii=False,
            )

            writer.writerow(
                output_record
            )

    return len(mismatches)


def main() -> None:
    arguments = parse_arguments()

    records = load_test_records(
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
        "Evaluating the unseen UCI SMS "
        "test split..."
    )

    print(
        f"Records: {len(records):,}"
    )

    print()

    for index, record in enumerate(
        records,
        start=1,
    ):
        evaluation = evaluate_record(
            record
        )

        evaluations.append(
            evaluation
        )

        if (
            index % 50 == 0
            or index == len(records)
        ):
            print(
                f"Processed "
                f"{index:,}/"
                f"{len(records):,}"
            )

    expected_values = [
        evaluation[
            "expected_category"
        ]
        for evaluation in evaluations
    ]

    predicted_values = [
        evaluation[
            "predicted_category"
        ]
        for evaluation in evaluations
    ]

    labels = sorted(
        set(expected_values)
        | set(predicted_values)
    )

    correct_count = sum(
        1
        for evaluation in evaluations
        if evaluation["correct"]
    )

    incorrect_count = (
        len(evaluations)
        - correct_count
    )

    accuracy = accuracy_score(
        expected_values,
        predicted_values,
    )

    macro_precision = precision_score(
        expected_values,
        predicted_values,
        average="macro",
        zero_division=0,
    )

    macro_recall = recall_score(
        expected_values,
        predicted_values,
        average="macro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        expected_values,
        predicted_values,
        average="macro",
        zero_division=0,
    )

    weighted_f1 = f1_score(
        expected_values,
        predicted_values,
        average="weighted",
        zero_division=0,
    )

    matrix = confusion_matrix(
        expected_values,
        predicted_values,
        labels=labels,
    )

    confusion_data = {
        expected_label: {
            predicted_label: int(
                matrix[
                    expected_index,
                    predicted_index,
                ]
            )
            for predicted_index, predicted_label
            in enumerate(labels)
        }
        for expected_index, expected_label
        in enumerate(labels)
    }

    mismatch_count = write_mismatches(
        evaluations
    )

    prediction_counts = dict(
        sorted(
            Counter(
                predicted_values
            ).items()
        )
    )

    report = {
        "benchmark": (
            "UCI SMS Spam Collection"
        ),
        "evaluation_type": (
            "unseen_public_human_labelled_test_set"
        ),
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "test_dataset": str(
            TEST_DATASET_PATH
        ),
        "records_evaluated": len(
            evaluations
        ),
        "correct_predictions": (
            correct_count
        ),
        "incorrect_predictions": (
            incorrect_count
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
            build_category_results(
                evaluations
            )
        ),
        "prediction_counts": (
            prediction_counts
        ),
        "confusion_matrix": (
            confusion_data
        ),
        "classification_report": (
            classification_report(
                expected_values,
                predicted_values,
                labels=labels,
                output_dict=True,
                zero_division=0,
            )
        ),
        "mismatch_records": (
            mismatch_count
        ),
        "important_note": (
            "This measures the current "
            "TrustScope rules and RAG system "
            "before supervised training. "
            "The test split must remain "
            "excluded from training and RAG."
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
    print("UCI SMS BASELINE RESULTS")
    print("=" * 60)

    print(
        f"Records evaluated: "
        f"{len(evaluations):,}"
    )

    print(
        f"Correct predictions: "
        f"{correct_count:,}"
    )

    print(
        f"Incorrect predictions: "
        f"{incorrect_count:,}"
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

    category_results = (
        report["category_results"]
    )

    for category, result in (
        category_results.items()
    ):
        print(category)

        print(
            "  Support: "
            f"{result['support']:,}"
        )

        print(
            "  Precision: "
            f"{result['precision_percent']:.2f}%"
        )

        print(
            "  Recall: "
            f"{result['recall_percent']:.2f}%"
        )

        print(
            "  F1: "
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