from __future__ import annotations

import csv
import itertools
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


MODEL_NAME = (
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

VALIDATION_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "hatexplain"
    / "validation.csv"
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "backend"
    / "storage"
    / "models"
    / "hatexplain_transformer"
)

RESULT_PATH = (
    OUTPUT_DIRECTORY
    / "validation_results.json"
)

MAX_LENGTH = 128
BATCH_SIZE = 8


def load_validation() -> tuple[
    list[str],
    list[str],
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

    if not texts:
        raise RuntimeError(
            "No validation records loaded."
        )

    return texts, labels


def predict_indexes(
    texts: list[str],
) -> tuple[
    list[int],
    list[list[float]],
    str,
    dict,
]:
    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Loading transformer on {device}..."
    )

    tokenizer = (
        AutoTokenizer.from_pretrained(
            MODEL_NAME
        )
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(
            MODEL_NAME
        )
    )

    model.to(device)
    model.eval()

    predicted_indexes: list[int] = []
    all_probabilities: list[
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
                name: value.to(device)
                for name, value
                in encoded.items()
            }

            output = model(**encoded)

            probabilities = torch.softmax(
                output.logits,
                dim=-1,
            )

            predicted_indexes.extend(
                probabilities.argmax(
                    dim=-1
                )
                .cpu()
                .tolist()
            )

            all_probabilities.extend(
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

    return (
        predicted_indexes,
        all_probabilities,
        str(device),
        dict(model.config.id2label),
    )


def determine_label_mapping(
    predicted_indexes: list[int],
    expected_labels: list[str],
) -> tuple[
    dict[int, str],
    float,
]:
    output_indexes = sorted(
        set(predicted_indexes)
    )

    if len(output_indexes) != 3:
        output_indexes = [0, 1, 2]

    best_mapping = None
    best_macro_f1 = -1.0

    for permutation in (
        itertools.permutations(
            CATEGORIES
        )
    ):
        mapping = {
            output_index: category
            for output_index, category
            in zip(
                output_indexes,
                permutation,
            )
        }

        predictions = [
            mapping[index]
            for index in predicted_indexes
        ]

        macro_f1 = f1_score(
            expected_labels,
            predictions,
            labels=CATEGORIES,
            average="macro",
            zero_division=0,
        )

        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            best_mapping = mapping

    if best_mapping is None:
        raise RuntimeError(
            "Label mapping could not "
            "be determined."
        )

    return (
        best_mapping,
        best_macro_f1,
    )


def main() -> None:
    texts, expected_labels = (
        load_validation()
    )

    print(
        f"Validation records: "
        f"{len(texts):,}"
    )

    (
        predicted_indexes,
        probabilities,
        device,
        configured_labels,
    ) = predict_indexes(texts)

    mapping, macro_f1 = (
        determine_label_mapping(
            predicted_indexes,
            expected_labels,
        )
    )

    predictions = [
        mapping[index]
        for index in predicted_indexes
    ]

    accuracy = accuracy_score(
        expected_labels,
        predictions,
    )

    report = classification_report(
        expected_labels,
        predictions,
        labels=CATEGORIES,
        output_dict=True,
        zero_division=0,
    )

    results = {
        "model_name": MODEL_NAME,
        "device": device,
        "records": len(texts),
        "configured_model_labels": (
            configured_labels
        ),
        "selected_label_mapping": {
            str(index): category
            for index, category
            in mapping.items()
        },
        "accuracy_percent": round(
            accuracy * 100,
            2,
        ),
        "macro_f1_percent": round(
            macro_f1 * 100,
            2,
        ),
        "category_results": {
            category: {
                "precision_percent": round(
                    report[
                        category
                    ]["precision"]
                    * 100,
                    2,
                ),
                "recall_percent": round(
                    report[
                        category
                    ]["recall"]
                    * 100,
                    2,
                ),
                "f1_percent": round(
                    report[
                        category
                    ]["f1-score"]
                    * 100,
                    2,
                ),
            }
            for category in CATEGORIES
        },
        "test_dataset_used": False,
    }

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    with RESULT_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            results,
            output_file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print("TRANSFORMER VALIDATION RESULTS")
    print("=" * 60)

    print(
        f"Accuracy: "
        f"{accuracy * 100:.2f}%"
    )

    print(
        f"Macro F1: "
        f"{macro_f1 * 100:.2f}%"
    )

    for category in CATEGORIES:
        category_result = (
            results[
                "category_results"
            ][category]
        )

        print()
        print(category)

        print(
            "  Precision: "
            f"{category_result['precision_percent']:.2f}%"
        )

        print(
            "  Recall: "
            f"{category_result['recall_percent']:.2f}%"
        )

        print(
            "  F1: "
            f"{category_result['f1_percent']:.2f}%"
        )

    print()
    print(
        f"Results saved: {RESULT_PATH}"
    )


if __name__ == "__main__":
    main()