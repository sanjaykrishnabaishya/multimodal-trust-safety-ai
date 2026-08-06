from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

VALIDATION_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "hatexplain"
    / "validation.csv"
)

MODEL_PATH = (
    BACKEND_ROOT
    / "storage"
    / "models"
    / "hatexplain"
    / "hatexplain_specialist.joblib"
)

CALIBRATION_PATH = (
    BACKEND_ROOT
    / "storage"
    / "models"
    / "hatexplain"
    / "hatexplain_calibration.json"
)


CATEGORIES = [
    "Normal/Ignore",
    "Abusive Words",
    "Hate Speech & Discrimination",
]

TARGET_PRECISION = 0.85
MINIMUM_ACCEPTED_RECORDS = 20


def load_validation() -> tuple[
    list[str],
    np.ndarray,
]:
    if not VALIDATION_PATH.exists():
        raise FileNotFoundError(
            f"Validation file missing: "
            f"{VALIDATION_PATH}"
        )

    texts: list[str] = []
    labels: list[str] = []

    with VALIDATION_PATH.open(
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
            "No validation records loaded."
        )

    return (
        texts,
        np.asarray(
            labels,
            dtype=object,
        ),
    )


def find_category_policy(
    *,
    category: str,
    category_index: int,
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> dict[str, Any]:
    ordered_probabilities = (
        np.sort(
            probabilities,
            axis=1,
        )
    )

    maximum_probabilities = (
        ordered_probabilities[:, -1]
    )

    second_probabilities = (
        ordered_probabilities[:, -2]
    )

    margins = (
        maximum_probabilities
        - second_probabilities
    )

    predicted_indexes = (
        probabilities.argmax(
            axis=1
        )
    )

    best_policy: dict[
        str,
        Any,
    ] | None = None

    for threshold in np.arange(
        0.35,
        1.00,
        0.01,
    ):
        for minimum_margin in (
            0.00,
            0.05,
            0.10,
            0.15,
            0.20,
            0.25,
            0.30,
            0.35,
            0.40,
        ):
            accepted_mask = (
                (
                    predicted_indexes
                    == category_index
                )
                & (
                    maximum_probabilities
                    >= threshold
                )
                & (
                    margins
                    >= minimum_margin
                )
            )

            accepted_count = int(
                accepted_mask.sum()
            )

            if (
                accepted_count
                < MINIMUM_ACCEPTED_RECORDS
            ):
                continue

            correct_count = int(
                np.sum(
                    labels[
                        accepted_mask
                    ]
                    == category
                )
            )

            precision = (
                correct_count
                / accepted_count
            )

            total_category_records = int(
                np.sum(
                    labels == category
                )
            )

            recall = (
                correct_count
                / total_category_records
                if total_category_records
                else 0.0
            )

            if (
                precision
                < TARGET_PRECISION
            ):
                continue

            candidate = {
                "enabled": True,
                "probability_threshold": round(
                    float(threshold),
                    2,
                ),
                "minimum_margin": round(
                    float(
                        minimum_margin
                    ),
                    2,
                ),
                "accepted_records": (
                    accepted_count
                ),
                "correct_records": (
                    correct_count
                ),
                "precision_percent": round(
                    precision * 100,
                    2,
                ),
                "recall_percent": round(
                    recall * 100,
                    2,
                ),
            }

            if best_policy is None:
                best_policy = candidate
                continue

            current_score = (
                candidate[
                    "accepted_records"
                ],
                candidate[
                    "precision_percent"
                ],
                candidate[
                    "recall_percent"
                ],
            )

            best_score = (
                best_policy[
                    "accepted_records"
                ],
                best_policy[
                    "precision_percent"
                ],
                best_policy[
                    "recall_percent"
                ],
            )

            if current_score > best_score:
                best_policy = candidate

    if best_policy is not None:
        return best_policy

    return {
        "enabled": False,
        "probability_threshold": 1.01,
        "minimum_margin": 1.01,
        "accepted_records": 0,
        "correct_records": 0,
        "precision_percent": 0.0,
        "recall_percent": 0.0,
        "reason": (
            "No validation threshold met "
            "the minimum 85% precision and "
            "minimum accepted-record requirement."
        ),
    }


def evaluate_selective_policy(
    *,
    labels: np.ndarray,
    probabilities: np.ndarray,
    model_classes: list[str],
    policies: dict[
        str,
        dict[str, Any],
    ],
) -> dict[str, Any]:
    predicted_indexes = (
        probabilities.argmax(
            axis=1
        )
    )

    ordered_probabilities = (
        np.sort(
            probabilities,
            axis=1,
        )
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

    accepted_by_category = {
        category: 0
        for category in CATEGORIES
    }

    correct_by_category = {
        category: 0
        for category in CATEGORIES
    }

    for index, predicted_index in (
        enumerate(predicted_indexes)
    ):
        category = model_classes[
            int(predicted_index)
        ]

        policy = policies[
            category
        ]

        decision_is_accepted = (
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

        if not decision_is_accepted:
            uncertain += 1
            continue

        accepted += 1

        accepted_by_category[
            category
        ] += 1

        if labels[index] == category:
            correct += 1

            correct_by_category[
                category
            ] += 1

    total_records = len(labels)

    selective_accuracy = (
        correct / accepted
        if accepted
        else 0.0
    )

    coverage = (
        accepted / total_records
        if total_records
        else 0.0
    )

    return {
        "records": total_records,
        "accepted_records": accepted,
        "uncertain_records": uncertain,
        "correct_accepted_records": (
            correct
        ),
        "selective_accuracy_percent": round(
            selective_accuracy * 100,
            2,
        ),
        "coverage_percent": round(
            coverage * 100,
            2,
        ),
        "accepted_by_category": (
            accepted_by_category
        ),
        "correct_by_category": (
            correct_by_category
        ),
    }


def main() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model missing: {MODEL_PATH}"
        )

    texts, labels = (
        load_validation()
    )

    package = joblib.load(
        MODEL_PATH
    )

    model = package["model"]

    probabilities = (
        model.predict_proba(
            texts
        )
    )

    model_classes = [
        str(category)
        for category in model.classes_
    ]

    policies: dict[
        str,
        dict[str, Any],
    ] = {}

    for category in CATEGORIES:
        if category not in model_classes:
            raise RuntimeError(
                "Model class missing: "
                f"{category}"
            )

        category_index = (
            model_classes.index(
                category
            )
        )

        policies[category] = (
            find_category_policy(
                category=category,
                category_index=(
                    category_index
                ),
                labels=labels,
                probabilities=(
                    probabilities
                ),
            )
        )

    selective_results = (
        evaluate_selective_policy(
            labels=labels,
            probabilities=probabilities,
            model_classes=model_classes,
            policies=policies,
        )
    )

    package[
        "decision_policy"
    ] = policies

    package[
        "uncertain_category"
    ] = "Uncertain"

    package[
        "calibration_version"
    ] = "1.0.0"

    joblib.dump(
        package,
        MODEL_PATH,
        compress=3,
    )

    calibration = {
        "model": (
            "TrustScope HateXplain "
            "Specialist"
        ),
        "calibration_version": (
            "1.0.0"
        ),
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "validation_dataset": str(
            VALIDATION_PATH
        ),
        "test_dataset_used": False,
        "target_precision_percent": (
            TARGET_PRECISION * 100
        ),
        "minimum_accepted_records": (
            MINIMUM_ACCEPTED_RECORDS
        ),
        "category_policies": (
            policies
        ),
        "selective_results": (
            selective_results
        ),
        "meaning": (
            "Only predictions passing their "
            "category probability and margin "
            "requirements receive a suggested "
            "category. All other predictions "
            "must return Uncertain with no "
            "automatic enforcement."
        ),
    }

    with CALIBRATION_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            calibration,
            output_file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print("SELECTIVE CALIBRATION RESULTS")
    print("=" * 60)

    for category, policy in (
        policies.items()
    ):
        print()
        print(category)

        print(
            f"  Enabled: "
            f"{policy['enabled']}"
        )

        print(
            "  Probability threshold: "
            f"{policy['probability_threshold']}"
        )

        print(
            "  Minimum margin: "
            f"{policy['minimum_margin']}"
        )

        print(
            "  Accepted validation records: "
            f"{policy['accepted_records']}"
        )

        print(
            "  Precision: "
            f"{policy['precision_percent']:.2f}%"
        )

        print(
            "  Recall: "
            f"{policy['recall_percent']:.2f}%"
        )

    print()
    print("-" * 60)

    print(
        "Selective accuracy: "
        f"{selective_results['selective_accuracy_percent']:.2f}%"
    )

    print(
        "Coverage: "
        f"{selective_results['coverage_percent']:.2f}%"
    )

    print(
        "Accepted records: "
        f"{selective_results['accepted_records']:,}"
    )

    print(
        "Uncertain records: "
        f"{selective_results['uncertain_records']:,}"
    )

    print()
    print(
        f"Calibration saved: "
        f"{CALIBRATION_PATH}"
    )

    print(
        "The official test split "
        "was not used."
    )


if __name__ == "__main__":
    main()