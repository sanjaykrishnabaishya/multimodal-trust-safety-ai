from __future__ import annotations

import csv
import itertools
import json
from pathlib import Path

import joblib
import numpy as np
import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


TRANSFORMER_NAME = (
    "Hate-speech-CNERG/"
    "bert-base-uncased-hatexplain"
)

CATEGORIES = [
    "Normal/Ignore",
    "Abusive Words",
    "Hate Speech & Discrimination",
]

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

CLASSICAL_MODEL_PATH = (
    BACKEND_ROOT
    / "storage"
    / "models"
    / "hatexplain"
    / "hatexplain_specialist.joblib"
)

OUTPUT_PATH = (
    BACKEND_ROOT
    / "storage"
    / "models"
    / "hatexplain_ensemble"
    / "validation_results.json"
)

BATCH_SIZE = 8
MAX_LENGTH = 128


def load_validation() -> tuple[
    list[str],
    np.ndarray,
]:
    texts: list[str] = []
    labels: list[str] = []

    with VALIDATION_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as input_file:
        for row in csv.DictReader(
            input_file
        ):
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

    return (
        texts,
        np.asarray(
            labels,
            dtype=object,
        ),
    )


def transformer_probabilities(
    texts: list[str],
) -> np.ndarray:
    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Transformer device: {device}"
    )

    tokenizer = (
        AutoTokenizer.from_pretrained(
            TRANSFORMER_NAME
        )
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(
            TRANSFORMER_NAME
        )
    )

    model.to(device)
    model.eval()

    results: list[
        list[float]
    ] = []

    with torch.inference_mode():
        for start in range(
            0,
            len(texts),
            BATCH_SIZE,
        ):
            batch = texts[
                start:
                start + BATCH_SIZE
            ]

            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            )

            encoded = {
                key: value.to(device)
                for key, value
                in encoded.items()
            }

            output = model(**encoded)

            probabilities = torch.softmax(
                output.logits,
                dim=-1,
            )

            results.extend(
                probabilities
                .cpu()
                .tolist()
            )

            completed = min(
                start + BATCH_SIZE,
                len(texts),
            )

            if (
                completed % 100 == 0
                or completed == len(texts)
            ):
                print(
                    f"Processed "
                    f"{completed:,}/"
                    f"{len(texts):,}"
                )

    return np.asarray(
        results,
        dtype=np.float32,
    )


def determine_transformer_mapping(
    probabilities: np.ndarray,
    expected: np.ndarray,
) -> dict[int, str]:
    indexes = probabilities.argmax(
        axis=1
    )

    best_mapping = None
    best_accuracy = -1.0

    for permutation in (
        itertools.permutations(
            CATEGORIES
        )
    ):
        mapping = {
            index: category
            for index, category
            in enumerate(permutation)
        }

        predictions = np.asarray(
            [
                mapping[int(index)]
                for index in indexes
            ],
            dtype=object,
        )

        accuracy = float(
            np.mean(
                predictions == expected
            )
        )

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_mapping = mapping

    if best_mapping is None:
        raise RuntimeError(
            "Transformer label mapping "
            "could not be determined."
        )

    return best_mapping


def main() -> None:
    texts, expected = (
        load_validation()
    )

    classical_package = joblib.load(
        CLASSICAL_MODEL_PATH
    )

    classical_model = (
        classical_package["model"]
    )

    classical_probabilities = (
        classical_model.predict_proba(
            texts
        )
    )

    classical_classes = [
        str(category)
        for category
        in classical_model.classes_
    ]

    classical_indexes = (
        classical_probabilities.argmax(
            axis=1
        )
    )

    classical_predictions = (
        np.asarray(
            [
                classical_classes[
                    int(index)
                ]
                for index
                in classical_indexes
            ],
            dtype=object,
        )
    )

    transformer_scores = (
        transformer_probabilities(
            texts
        )
    )

    transformer_mapping = (
        determine_transformer_mapping(
            transformer_scores,
            expected,
        )
    )

    transformer_indexes = (
        transformer_scores.argmax(
            axis=1
        )
    )

    transformer_predictions = (
        np.asarray(
            [
                transformer_mapping[
                    int(index)
                ]
                for index
                in transformer_indexes
            ],
            dtype=object,
        )
    )

    agreement_mask = (
        classical_predictions
        == transformer_predictions
    )

    accepted = int(
        agreement_mask.sum()
    )

    correct = int(
        np.sum(
            classical_predictions[
                agreement_mask
            ]
            == expected[
                agreement_mask
            ]
        )
    )

    total = len(expected)

    accuracy = (
        correct / accepted
        if accepted
        else 0.0
    )

    coverage = (
        accepted / total
        if total
        else 0.0
    )

    category_results = {}

    for category in CATEGORIES:
        category_mask = (
            agreement_mask
            & (
                classical_predictions
                == category
            )
        )

        category_accepted = int(
            category_mask.sum()
        )

        category_correct = int(
            np.sum(
                expected[
                    category_mask
                ]
                == category
            )
        )

        category_results[
            category
        ] = {
            "accepted": (
                category_accepted
            ),
            "correct": (
                category_correct
            ),
            "precision_percent": round(
                (
                    category_correct
                    / category_accepted
                    * 100
                )
                if category_accepted
                else 0.0,
                2,
            ),
        }

    result = {
        "records": total,
        "accepted_records": accepted,
        "uncertain_records": (
            total - accepted
        ),
        "agreement_accuracy_percent": round(
            accuracy * 100,
            2,
        ),
        "coverage_percent": round(
            coverage * 100,
            2,
        ),
        "category_results": (
            category_results
        ),
        "transformer_mapping": {
            str(index): category
            for index, category
            in transformer_mapping.items()
        },
        "test_dataset_used": False,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            result,
            output_file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print("ENSEMBLE VALIDATION RESULTS")
    print("=" * 60)

    print(
        f"Accepted records: "
        f"{accepted:,}"
    )

    print(
        f"Uncertain records: "
        f"{total - accepted:,}"
    )

    print(
        "Agreement accuracy: "
        f"{accuracy * 100:.2f}%"
    )

    print(
        f"Coverage: "
        f"{coverage * 100:.2f}%"
    )

    for category, values in (
        category_results.items()
    ):
        print()
        print(category)

        print(
            f"  Accepted: "
            f"{values['accepted']:,}"
        )

        print(
            "  Precision: "
            f"{values['precision_percent']:.2f}%"
        )

    print()
    print(
        f"Saved: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()