from __future__ import annotations

import ast
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datasets import load_dataset
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)

from app.services.private_information_service import (
    analyze_private_information,
)


DATASET_NAME = "nvidia/Nemotron-PII"
DATASET_SPLIT = "test"

MAX_RELEVANT_RECORDS = 2000

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "private_information"
    / "nemotron_external_report.json"
)


PRIVATE_CATEGORY = (
    "Publishing Private Information"
)

NORMAL_CATEGORY = "Normal/Ignore"

CATEGORIES = [
    NORMAL_CATEGORY,
    PRIVATE_CATEGORY,
]


SUPPORTED_LABEL_MAPPING = {
    "email": "email_address",
    "email_address": "email_address",
    "phone": "phone_number",
    "phone_number": "phone_number",
    "mobile_phone_number": (
        "phone_number"
    ),
    "account_number": (
        "bank_account_number"
    ),
    "bank_account_number": (
        "bank_account_number"
    ),
    "credit_card_number": (
        "payment_card_number"
    ),
    "payment_card_number": (
        "payment_card_number"
    ),
    "card_number": (
        "payment_card_number"
    ),
    "password": "credential",
    "pin": "credential",
    "cvv": "credential",
    "security_code": "credential",
    "api_key": "credential",
    "access_token": "credential",
    "ip_address": "ipv4_address",
    "ipv4_address": "ipv4_address",
    "coordinates": (
        "location_coordinates"
    ),
    "gps_coordinates": (
        "location_coordinates"
    ),
}


def normalize_label(
    value: str,
) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def parse_spans(
    value: Any,
) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [
            item
            for item in value
            if isinstance(item, dict)
        ]

    if not value:
        return []

    if isinstance(value, str):
        try:
            parsed = json.loads(value)

        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(
                    value
                )

            except (
                ValueError,
                SyntaxError,
            ):
                return []

        if isinstance(parsed, list):
            return [
                item
                for item in parsed
                if isinstance(item, dict)
            ]

    return []


def supported_expected_types(
    spans: list[dict[str, Any]],
) -> set[str]:
    supported_types: set[str] = set()

    for span in spans:
        source_label = normalize_label(
            span.get(
                "label",
                "",
            )
        )

        mapped_label = (
            SUPPORTED_LABEL_MAPPING.get(
                source_label
            )
        )

        if mapped_label:
            supported_types.add(
                mapped_label
            )

    return supported_types


def main() -> None:
    print(
        "Streaming NVIDIA Nemotron-PII "
        "validation records..."
    )

    dataset = load_dataset(
        DATASET_NAME,
        split=DATASET_SPLIT,
        streaming=True,
    )

    expected: list[str] = []
    predicted: list[str] = []

    expected_type_counts: Counter = (
        Counter()
    )

    detected_type_counts: Counter = (
        Counter()
    )

    prediction_counts: Counter = (
        Counter()
    )

    documents_examined = 0
    relevant_records = 0
    positive_records = 0
    negative_records = 0
    raw_storage_failures = 0

    for record in dataset:
        documents_examined += 1

        text = " ".join(
            str(
                record.get(
                    "text",
                    "",
                )
            ).split()
        )

        if not text:
            continue

        spans = parse_spans(
            record.get(
                "spans",
                [],
            )
        )

        expected_types = (
            supported_expected_types(
                spans
            )
        )

        # Records containing unsupported PII
        # are not treated as safe negatives.
        all_span_labels = {
            normalize_label(
                span.get(
                    "label",
                    "",
                )
            )
            for span in spans
        }

        unsupported_labels = {
            label
            for label in all_span_labels
            if (
                label
                and label
                not in (
                    SUPPORTED_LABEL_MAPPING
                )
            )
        }

        if (
            not expected_types
            and unsupported_labels
        ):
            continue

        if expected_types:
            expected_category = (
                PRIVATE_CATEGORY
            )

            positive_records += 1

            expected_type_counts.update(
                expected_types
            )

        else:
            expected_category = (
                NORMAL_CATEGORY
            )

            negative_records += 1

        result = (
            analyze_private_information(
                text
            )
        )

        predicted_category = str(
            result.get(
                "category",
                "Uncertain",
            )
        )

        expected.append(
            expected_category
        )

        predicted.append(
            predicted_category
        )

        prediction_counts.update(
            [predicted_category]
        )

        detected_type_counts.update(
            result.get(
                "information_types",
                [],
            )
        )

        if result.get(
            "raw_values_stored",
            False,
        ):
            raw_storage_failures += 1

        relevant_records += 1

        if (
            relevant_records % 100 == 0
        ):
            print(
                f"Evaluated "
                f"{relevant_records:,}/"
                f"{MAX_RELEVANT_RECORDS:,}"
            )

        if (
            relevant_records
            >= MAX_RELEVANT_RECORDS
        ):
            break

    if not expected:
        raise RuntimeError(
            "No relevant external "
            "benchmark records were found."
        )

    accuracy = accuracy_score(
        expected,
        predicted,
    )

    macro_precision = (
        precision_score(
            expected,
            predicted,
            labels=CATEGORIES,
            average="macro",
            zero_division=0,
        )
    )

    macro_recall = recall_score(
        expected,
        predicted,
        labels=CATEGORIES,
        average="macro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        expected,
        predicted,
        labels=CATEGORIES,
        average="macro",
        zero_division=0,
    )

    classification = (
        classification_report(
            expected,
            predicted,
            labels=CATEGORIES,
            output_dict=True,
            zero_division=0,
        )
    )

    category_results = {
        category: {
            "support": int(
                classification[
                    category
                ]["support"]
            ),
            "precision_percent": round(
                classification[
                    category
                ]["precision"]
                * 100,
                2,
            ),
            "recall_percent": round(
                classification[
                    category
                ]["recall"]
                * 100,
                2,
            ),
            "f1_percent": round(
                classification[
                    category
                ]["f1-score"]
                * 100,
                2,
            ),
        }
        for category in CATEGORIES
    }

    report = {
        "benchmark": (
            "NVIDIA Nemotron-PII "
            "external validation sample"
        ),
        "dataset": DATASET_NAME,
        "dataset_split": (
            DATASET_SPLIT
        ),
        "license": "CC BY 4.0",
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "documents_examined": (
            documents_examined
        ),
        "records_evaluated": (
            relevant_records
        ),
        "positive_records": (
            positive_records
        ),
        "negative_records": (
            negative_records
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
        "category_results": (
            category_results
        ),
        "expected_type_counts": dict(
            expected_type_counts
        ),
        "detected_type_counts": dict(
            detected_type_counts
        ),
        "prediction_counts": dict(
            prediction_counts
        ),
        "raw_storage_failures": (
            raw_storage_failures
        ),
        "source_text_saved": False,
        "limitations": [
            (
                "The benchmark is an external "
                "synthetic dataset, not real "
                "personal information."
            ),
            (
                "Only entity types supported "
                "by the current detector are "
                "included."
            ),
            (
                "The source text is streamed "
                "and is not written to reports."
            ),
            (
                "This evaluates PII pattern "
                "detection, not consent or "
                "ownership."
            ),
        ],
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
    print("NEMOTRON PII EXTERNAL RESULTS")
    print("=" * 60)

    print(
        f"Records evaluated: "
        f"{relevant_records:,}"
    )

    print(
        f"Positive records: "
        f"{positive_records:,}"
    )

    print(
        f"Negative records: "
        f"{negative_records:,}"
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

    for category, result in (
        category_results.items()
    ):
        print()
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
        f"Raw storage failures: "
        f"{raw_storage_failures}"
    )

    print(
        f"Report saved: "
        f"{REPORT_PATH}"
    )


if __name__ == "__main__":
    main()
