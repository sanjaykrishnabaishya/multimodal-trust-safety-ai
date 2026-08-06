from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

TEST_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "hatexplain"
    / "test.csv"
)

MODEL_PATH = (
    BACKEND_ROOT
    / "storage"
    / "models"
    / "hatexplain"
    / "hatexplain_specialist.joblib"
)

REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "hatexplain"
    / "selective_test_report.json"
)


CATEGORIES = [
    "Normal/Ignore",
    "Abusive Words",
    "Hate Speech & Discrimination",
]


def load_test_data() -> tuple[
    list[str],
    np.ndarray,
]:
    texts: list[str] = []
    labels: list[str] = []

    with TEST_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as input_file:
        reader = csv.DictReader(
            input_file
        )

        for row in reader:
            text = " ".join(
                row.get(
                    "text",
                    "",
                ).split()
            )

            category = row.get(
                "category",
                "",
            ).strip()

            if (
                text
                and category in CATEGORIES
            ):
                texts.append(text)
                labels.append(category)

    if not texts:
        raise RuntimeError(
            "No test records were loaded."
        )

    return (
        texts,
        np.asarray(
            labels,
            dtype=object,
        ),
    )


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model missing: {MODEL_PATH}"
        )

    texts, labels = load_test_data()

    package = joblib.load(
        MODEL_PATH
    )

    model = package["model"]

    policies = package.get(
        "decision_policy"
    )

    if not policies:
        raise RuntimeError(
            "The model has not been "
            "selectively calibrated."
        )

    probabilities = model.predict_proba(
        texts
    )

    model_classes = [
        str(category)
        for category in model.classes_
    ]

    predicted_indexes = (
        probabilities.argmax(
            axis=1
        )
    )

    ordered_probabilities = np.sort(
        probabilities,
        axis=1,
    )

    maximum_probabilities = (
        ordered_probabilities[:, -1]
    )

    margins = (
        ordered_probabilities[:, -1]
        - ordered_probabilities[:, -2]
    )

    accepted = 0
    correct = 0
    uncertain = 0

    category_results = {
        category: {
            "accepted": 0,
            "correct": 0,
            "incorrect": 0,
        }
        for category in CATEGORIES
    }

    for index, predicted_index in enumerate(
        predicted_indexes
    ):
        category = model_classes[
            int(predicted_index)
        ]

        policy = policies[
            category
        ]

        decision_accepted = (
            policy["enabled"]
            and maximum_probabilities[index]
            >= policy[
                "probability_threshold"
            ]
            and margins[index]
            >= policy[
                "minimum_margin"
            ]
        )

        if not decision_accepted:
            uncertain += 1
            continue

        accepted += 1

        category_results[
            category
        ]["accepted"] += 1

        if labels[index] == category:
            correct += 1

            category_results[
                category
            ]["correct"] += 1

        else:
            category_results[
                category
            ]["incorrect"] += 1

    total = len(labels)

    selective_accuracy = (
        correct / accepted
        if accepted
        else 0.0
    )

    coverage = (
        accepted / total
        if total
        else 0.0
    )

    for category, result in (
        category_results.items()
    ):
        category_accepted = (
            result["accepted"]
        )

        result[
            "accepted_precision_percent"
        ] = round(
            (
                result["correct"]
                / category_accepted
                * 100
            )
            if category_accepted
            else 0.0,
            2,
        )

    report = {
        "benchmark": (
            "HateXplain selective test"
        ),
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "records": total,
        "accepted_records": accepted,
        "uncertain_records": uncertain,
        "correct_accepted_records": (
            correct
        ),
        "incorrect_accepted_records": (
            accepted - correct
        ),
        "selective_accuracy_percent": round(
            selective_accuracy * 100,
            2,
        ),
        "coverage_percent": round(
            coverage * 100,
            2,
        ),
        "category_results": (
            category_results
        ),
        "decision_policies": (
            policies
        ),
        "test_used_for_tuning": False,
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
    print("HATEXPLAIN SELECTIVE TEST RESULTS")
    print("=" * 60)

    print(
        f"Records: {total:,}"
    )

    print(
        f"Accepted records: "
        f"{accepted:,}"
    )

    print(
        f"Uncertain records: "
        f"{uncertain:,}"
    )

    print(
        "Selective accuracy: "
        f"{selective_accuracy * 100:.2f}%"
    )

    print(
        f"Coverage: "
        f"{coverage * 100:.2f}%"
    )

    print()
    print("CATEGORY RESULTS")
    print("-" * 60)

    for category, result in (
        category_results.items()
    ):
        print(category)

        print(
            f"  Accepted: "
            f"{result['accepted']:,}"
        )

        print(
            "  Accepted precision: "
            f"{result['accepted_precision_percent']:.2f}%"
        )

    print()
    print(
        f"Report saved: {REPORT_PATH}"
    )

    print(
        "Do not adjust thresholds using "
        "these test results."
    )


if __name__ == "__main__":
    main()
