from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datasets import load_dataset

from app.services.private_information_service import (
    NORMAL_CATEGORY,
    analyze_private_information,
)


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent

REPORT_DIRECTORY = (
    PROJECT_DIRECTORY
    / "reports"
    / "evaluation"
    / "private_information"
)

REPORT_PATH = (
    REPORT_DIRECTORY
    / "ag_news_safe_benchmark.json"
)

FALSE_POSITIVE_PATH = (
    REPORT_DIRECTORY
    / "ag_news_safe_false_positives.csv"
)

DATASET_NAME = "fancyzhx/ag_news"
DATASET_SPLIT = "test"

TOPIC_NAMES = {
    0: "World",
    1: "Sports",
    2: "Business",
    3: "Science/Technology",
}


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate private-information false positives "
            "on external AG News safe content."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=2000,
        help=(
            "Maximum number of AG News test records "
            "to evaluate. Default: 2000."
        ),
    )

    return parser.parse_args()


def _percentage(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(
        (numerator / denominator) * 100,
        2,
    )


def _load_records(
    limit: int,
) -> list[dict[str, Any]]:
    print(
        "Streaming external AG News test records..."
    )

    dataset = load_dataset(
        DATASET_NAME,
        split=DATASET_SPLIT,
        streaming=True,
    )

    records: list[dict[str, Any]] = []

    for record in dataset:
        text = str(
            record.get("text", "")
        ).strip()

        if not text:
            continue

        records.append(
            {
                "text": text,
                "label": int(
                    record.get("label", -1)
                ),
            }
        )

        if len(records) >= limit:
            break

    return records


def _write_false_positives(
    rows: list[dict[str, Any]],
) -> None:
    REPORT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "record_number",
        "news_topic",
        "predicted_category",
        "confidence",
        "human_review_required",
        "match_count",
        "information_types",
        "exposure_context_detected",
        "safe_context_detected",
    ]

    with FALSE_POSITIVE_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def _write_report(
    report: dict[str, Any],
) -> None:
    REPORT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    with REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main() -> None:
    arguments = _parse_arguments()

    if arguments.limit <= 0:
        raise ValueError(
            "--limit must be greater than zero."
        )

    records = _load_records(
        arguments.limit
    )

    if not records:
        raise RuntimeError(
            "No AG News records were loaded."
        )

    print(
        f"Evaluating {len(records):,} safe records..."
    )
    print(
        "Source text will not be saved in reports."
    )

    true_negatives = 0
    false_positives = 0
    review_referrals = 0
    presidio_failures = 0
    raw_storage_failures = 0

    information_type_counts: Counter[str] = (
        Counter()
    )

    false_positive_topic_counts: Counter[str] = (
        Counter()
    )

    false_positive_rows: list[
        dict[str, Any]
    ] = []

    for index, record in enumerate(
        records,
        start=1,
    ):
        result = analyze_private_information(
            record["text"]
        )

        predicted_category = str(
            result.get(
                "category",
                NORMAL_CATEGORY,
            )
        )

        if result.get(
            "human_review_required",
            False,
        ):
            review_referrals += 1

        if not result.get(
            "presidio_available",
            False,
        ):
            presidio_failures += 1

        serialized_result = json.dumps(
            result,
            ensure_ascii=False,
        )

        if record["text"] in serialized_result:
            raw_storage_failures += 1

        if predicted_category == NORMAL_CATEGORY:
            true_negatives += 1
            continue

        false_positives += 1

        topic = TOPIC_NAMES.get(
            record["label"],
            "Unknown",
        )

        detected_types = [
            str(information_type)
            for information_type
            in result.get(
                "information_types",
                [],
            )
        ]

        information_type_counts.update(
            detected_types
        )

        false_positive_topic_counts.update(
            [topic]
        )

        false_positive_rows.append(
            {
                "record_number": index,
                "news_topic": topic,
                "predicted_category": (
                    predicted_category
                ),
                "confidence": result.get(
                    "confidence",
                    0.0,
                ),
                "human_review_required": (
                    result.get(
                        "human_review_required",
                        False,
                    )
                ),
                "match_count": result.get(
                    "match_count",
                    0,
                ),
                "information_types": "|".join(
                    detected_types
                ),
                "exposure_context_detected": (
                    result.get(
                        "exposure_context_detected",
                        False,
                    )
                ),
                "safe_context_detected": (
                    result.get(
                        "safe_context_detected",
                        False,
                    )
                ),
            }
        )

        if index % 100 == 0:
            print(
                f"Processed {index:,} records..."
            )

    records_evaluated = len(records)

    safe_specificity = _percentage(
        true_negatives,
        records_evaluated,
    )

    false_positive_rate = _percentage(
        false_positives,
        records_evaluated,
    )

    review_referral_rate = _percentage(
        review_referrals,
        records_evaluated,
    )

    passed_target = (
        safe_specificity >= 85.0
        and raw_storage_failures == 0
        and presidio_failures == 0
    )

    report = {
        "benchmark_name": (
            "AG News external safe-content "
            "private-information benchmark"
        ),
        "created_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "dataset": DATASET_NAME,
        "split": DATASET_SPLIT,
        "expected_category": NORMAL_CATEGORY,
        "records_evaluated": records_evaluated,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "safe_specificity_percent": (
            safe_specificity
        ),
        "false_positive_rate_percent": (
            false_positive_rate
        ),
        "review_referrals": review_referrals,
        "review_referral_rate_percent": (
            review_referral_rate
        ),
        "presidio_failures": presidio_failures,
        "raw_storage_failures": (
            raw_storage_failures
        ),
        "passed_85_percent_target": (
            passed_target
        ),
        "false_positive_information_types": (
            dict(
                information_type_counts.most_common()
            )
        ),
        "false_positive_topics": dict(
            false_positive_topic_counts.most_common()
        ),
        "limitations": [
            (
                "AG News is a news-topic dataset, not a "
                "human-labelled private-information "
                "policy benchmark."
            ),
            (
                "Some public news records may contain "
                "contact details, URLs, or other entities "
                "that Presidio correctly recognizes."
            ),
            (
                "This benchmark primarily measures the "
                "false-positive risk on ordinary public "
                "news containing names, locations, dates, "
                "and organizations."
            ),
            (
                "No AG News source text is saved in the "
                "report or false-positive CSV."
            ),
        ],
    }

    _write_false_positives(
        false_positive_rows
    )

    _write_report(report)

    print()
    print(
        "AG NEWS SAFE-CONTENT PII BENCHMARK"
    )
    print("=" * 60)
    print(
        f"Records evaluated: {records_evaluated:,}"
    )
    print(
        f"Correct Normal/Ignore: {true_negatives:,}"
    )
    print(
        f"False positives: {false_positives:,}"
    )
    print(
        f"Safe specificity: {safe_specificity:.2f}%"
    )
    print(
        "False-positive rate: "
        f"{false_positive_rate:.2f}%"
    )
    print(
        "Human-review referral rate: "
        f"{review_referral_rate:.2f}%"
    )
    print(
        f"Presidio failures: {presidio_failures:,}"
    )
    print(
        "Raw storage failures: "
        f"{raw_storage_failures:,}"
    )
    print(
        "Passed 85% safe-specificity target: "
        f"{passed_target}"
    )

    print()
    print(
        "MOST COMMON FALSE-POSITIVE ENTITY TYPES"
    )
    print("-" * 60)

    if information_type_counts:
        for information_type, count in (
            information_type_counts.most_common(15)
        ):
            print(
                f"{information_type}: {count:,}"
            )
    else:
        print("None")

    print()
    print(
        f"Report saved: {REPORT_PATH}"
    )
    print(
        "False-positive audit saved: "
        f"{FALSE_POSITIVE_PATH}"
    )


if __name__ == "__main__":
    main()