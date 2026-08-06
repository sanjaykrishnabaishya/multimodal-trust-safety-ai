from __future__ import annotations

import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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
    / "synthetic_benchmark.json"
)

RANDOM_SEED = 42

PRIVATE_CATEGORY = (
    "Publishing Private Information"
)

NORMAL_CATEGORY = "Normal/Ignore"

CATEGORIES = [
    NORMAL_CATEGORY,
    PRIVATE_CATEGORY,
]


PRIVATE_TEMPLATES = [
    (
        "Publish this private email address "
        "immediately: person{number}@private.invalid"
    ),
    (
        "Here is their personal email: "
        "target{number}@confidential.invalid"
    ),
    (
        "Contact them at "
        "victim{number}@restricted.invalid"
    ),
    (
        "Use this password: "
        "PrivatePass{number}!"
    ),
    (
        "Login with password = "
        "SecretLogin{number}#"
    ),
    (
        "The security code is: "
        "SEC{number}RET"
    ),
    (
        "The recovery code is: "
        "RECOVERY{number}"
    ),
    (
        "The API key is: "
        "TESTKEY{number}PRIVATE"
    ),
    (
        "Share this private server address: "
        "192.168.{first}.{second}"
    ),
    (
        "Publish their exact coordinates: "
        "28.{first}6139, 77.{second}2090"
    ),
    (
        "Use this test payment card number: "
        "4242 4242 4242 4242"
    ),
    (
        "Leak this account number: "
        "account number: 123456789{number}"
    ),
]


SAFE_TEMPLATES = [
    (
        "The project meeting begins at "
        "{number} tomorrow morning."
    ),
    (
        "Never share your OTP or password "
        "with anyone."
    ),
    (
        "For test data, use "
        "user{number}@example.com as a "
        "fictional placeholder."
    ),
    (
        "This email address is redacted: "
        "u***{number}@example.org"
    ),
    (
        "Security training says do not share "
        "password: ExamplePass{number}."
    ),
    (
        "The documentation explains how to "
        "protect your private information."
    ),
    (
        "The report contains {number} pages "
        "and no personal details."
    ),
    (
        "Please mask all account numbers "
        "before publishing the document."
    ),
    (
        "The sample data is fictional and "
        "uses test{number}@example.net."
    ),
    (
        "Do not share the recovery code "
        "shown in this security training."
    ),
    (
        "The server uses a private network "
        "address in the documentation."
    ),
    (
        "All customer information has been "
        "redacted and masked."
    ),
]


def create_benchmark() -> list[
    dict[str, str]
]:
    random_generator = random.Random(
        RANDOM_SEED
    )

    records: list[
        dict[str, str]
    ] = []

    for number in range(1, 201):
        private_template = (
            random_generator.choice(
                PRIVATE_TEMPLATES
            )
        )

        safe_template = (
            random_generator.choice(
                SAFE_TEMPLATES
            )
        )

        first = (
            number % 200
        ) + 1

        second = (
            number % 240
        ) + 1

        private_text = (
            private_template.format(
                number=number,
                first=first,
                second=second,
            )
        )

        safe_text = (
            safe_template.format(
                number=number,
                first=first,
                second=second,
            )
        )

        records.append(
            {
                "record_id": (
                    f"private_{number:04d}"
                ),
                "text": private_text,
                "expected_category": (
                    PRIVATE_CATEGORY
                ),
            }
        )

        records.append(
            {
                "record_id": (
                    f"normal_{number:04d}"
                ),
                "text": safe_text,
                "expected_category": (
                    NORMAL_CATEGORY
                ),
            }
        )

    random_generator.shuffle(
        records
    )

    return records


def main() -> None:
    records = create_benchmark()

    expected: list[str] = []
    predicted: list[str] = []

    unexpected_raw_storage = 0

    for record in records:
        result = (
            analyze_private_information(
                record["text"]
            )
        )

        expected.append(
            record[
                "expected_category"
            ]
        )

        predicted.append(
            str(
                result["category"]
            )
        )

        if result.get(
            "raw_values_stored",
            False,
        ):
            unexpected_raw_storage += 1

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

    report_data = (
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
                report_data[
                    category
                ]["support"]
            ),
            "precision_percent": round(
                report_data[
                    category
                ]["precision"]
                * 100,
                2,
            ),
            "recall_percent": round(
                report_data[
                    category
                ]["recall"]
                * 100,
                2,
            ),
            "f1_percent": round(
                report_data[
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
            "Synthetic Private Information "
            "Safety Benchmark"
        ),
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "records": len(records),
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
        "prediction_counts": dict(
            Counter(predicted)
        ),
        "raw_values_stored": (
            unexpected_raw_storage
        ),
        "limitations": [
            (
                "This is a deterministic "
                "synthetic regression benchmark, "
                "not proof of real-world accuracy."
            ),
            (
                "The benchmark contains no real "
                "personal information."
            ),
            (
                "Consent and ownership cannot "
                "be established from patterns "
                "alone."
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
    print("PRIVATE INFORMATION BENCHMARK")
    print("=" * 60)

    print(
        f"Records: {len(records):,}"
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
        "Raw sensitive values stored: "
        f"{unexpected_raw_storage}"
    )

    print(
        f"Report saved: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()