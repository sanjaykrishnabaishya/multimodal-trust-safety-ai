from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.calibration import (
    CalibratedClassifierCV,
)
from sklearn.feature_extraction.text import (
    TfidfVectorizer,
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import (
    FeatureUnion,
    Pipeline,
)
from sklearn.svm import LinearSVC


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

DATASET_DIRECTORY = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "hatexplain"
)

TRAIN_PATH = (
    DATASET_DIRECTORY
    / "train.csv"
)

VALIDATION_PATH = (
    DATASET_DIRECTORY
    / "validation.csv"
)

MODEL_DIRECTORY = (
    BACKEND_ROOT
    / "storage"
    / "models"
    / "hatexplain"
)

MODEL_PATH = (
    MODEL_DIRECTORY
    / "hatexplain_specialist.joblib"
)

METADATA_PATH = (
    MODEL_DIRECTORY
    / "hatexplain_specialist_metadata.json"
)


CATEGORIES = [
    "Normal/Ignore",
    "Abusive Words",
    "Hate Speech & Discrimination",
]

RANDOM_SEED = 42


def load_dataset(
    path: Path,
) -> tuple[
    list[str],
    np.ndarray,
]:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset missing: {path}"
        )

    texts: list[str] = []
    labels: list[str] = []

    with path.open(
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
            f"No valid records in {path}"
        )

    return (
        texts,
        np.asarray(
            labels,
            dtype=object,
        ),
    )


def build_model() -> (
    CalibratedClassifierCV
):
    word_features = (
        TfidfVectorizer(
            analyzer="word",
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.995,
            max_features=50000,
            sublinear_tf=True,
            norm="l2",
        )
    )

    character_features = (
        TfidfVectorizer(
            analyzer="char_wb",
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(3, 5),
            min_df=2,
            max_features=70000,
            sublinear_tf=True,
            norm="l2",
        )
    )

    features = FeatureUnion(
        transformer_list=[
            (
                "word_features",
                word_features,
            ),
            (
                "character_features",
                character_features,
            ),
        ],
        n_jobs=-1,
    )

    classifier = LinearSVC(
        C=2.0,
        class_weight="balanced",
        random_state=RANDOM_SEED,
        max_iter=5000,
    )

    pipeline = Pipeline(
        steps=[
            (
                "features",
                features,
            ),
            (
                "classifier",
                classifier,
            ),
        ]
    )

    return CalibratedClassifierCV(
        estimator=pipeline,
        method="sigmoid",
        cv=3,
        n_jobs=-1,
    )


def category_counts(
    labels: np.ndarray,
) -> dict[str, int]:
    return {
        category: int(
            np.sum(
                labels == category
            )
        )
        for category in CATEGORIES
    }


def percent(
    value: float,
) -> float:
    return round(
        float(value) * 100,
        2,
    )


def main() -> None:
    print(
        "Loading HateXplain training "
        "and validation records..."
    )

    train_texts, train_labels = (
        load_dataset(
            TRAIN_PATH
        )
    )

    (
        validation_texts,
        validation_labels,
    ) = load_dataset(
        VALIDATION_PATH
    )

    print(
        f"Training records: "
        f"{len(train_texts):,}"
    )

    print(
        f"Validation records: "
        f"{len(validation_texts):,}"
    )

    print()
    print(
        "Training the calibrated "
        "hate/abuse specialist..."
    )

    model = build_model()

    model.fit(
        train_texts,
        train_labels,
    )

    print(
        "Training completed."
    )

    predictions = model.predict(
        validation_texts
    )

    probabilities = (
        model.predict_proba(
            validation_texts
        )
    )

    maximum_probabilities = (
        probabilities.max(
            axis=1
        )
    )

    accuracy = accuracy_score(
        validation_labels,
        predictions,
    )

    macro_precision = (
        precision_score(
            validation_labels,
            predictions,
            labels=CATEGORIES,
            average="macro",
            zero_division=0,
        )
    )

    macro_recall = recall_score(
        validation_labels,
        predictions,
        labels=CATEGORIES,
        average="macro",
        zero_division=0,
    )

    macro_f1 = f1_score(
        validation_labels,
        predictions,
        labels=CATEGORIES,
        average="macro",
        zero_division=0,
    )

    weighted_f1 = f1_score(
        validation_labels,
        predictions,
        labels=CATEGORIES,
        average="weighted",
        zero_division=0,
    )

    report = classification_report(
        validation_labels,
        predictions,
        labels=CATEGORIES,
        output_dict=True,
        zero_division=0,
    )

    MODEL_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    package: dict[str, Any] = {
        "model": model,
        "categories": CATEGORIES,
        "model_version": "1.0.0",
        "training_source": (
            "HateXplain"
        ),
        "minimum_support_score": 0.55,
        "strong_support_score": 0.80,
    }

    joblib.dump(
        package,
        MODEL_PATH,
        compress=3,
    )

    category_results = {
        category: {
            "support": int(
                report[
                    category
                ]["support"]
            ),
            "precision_percent": (
                percent(
                    report[
                        category
                    ]["precision"]
                )
            ),
            "recall_percent": (
                percent(
                    report[
                        category
                    ]["recall"]
                )
            ),
            "f1_percent": (
                percent(
                    report[
                        category
                    ]["f1-score"]
                )
            ),
        }
        for category in CATEGORIES
    }

    metadata = {
        "model_name": (
            "TrustScope HateXplain "
            "Specialist"
        ),
        "model_version": "1.0.0",
        "model_type": (
            "calibrated_word_character_"
            "tfidf_linear_svm"
        ),
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "training_dataset": str(
            TRAIN_PATH
        ),
        "validation_dataset": str(
            VALIDATION_PATH
        ),
        "test_dataset_used": False,
        "training_records": len(
            train_texts
        ),
        "validation_records": len(
            validation_texts
        ),
        "training_category_counts": (
            category_counts(
                train_labels
            )
        ),
        "validation_category_counts": (
            category_counts(
                validation_labels
            )
        ),
        "validation_results": {
            "accuracy_percent": (
                percent(accuracy)
            ),
            "macro_precision_percent": (
                percent(
                    macro_precision
                )
            ),
            "macro_recall_percent": (
                percent(
                    macro_recall
                )
            ),
            "macro_f1_percent": (
                percent(macro_f1)
            ),
            "weighted_f1_percent": (
                percent(
                    weighted_f1
                )
            ),
            "average_maximum_probability": (
                round(
                    float(
                        maximum_probabilities
                        .mean()
                    ),
                    4,
                )
            ),
            "category_results": (
                category_results
            ),
        },
        "confidence_policy": {
            "minimum_support_score": (
                0.55
            ),
            "strong_support_score": (
                0.80
            ),
            "note": (
                "Model probability is "
                "supporting evidence and not "
                "a standalone enforcement "
                "decision."
            ),
        },
        "important_note": (
            "The official HateXplain test "
            "split was not used for training, "
            "calibration, model selection, "
            "threshold selection, or RAG."
        ),
    }

    with METADATA_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            metadata,
            output_file,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print("=" * 60)
    print("HATEXPLAIN VALIDATION RESULTS")
    print("=" * 60)

    print(
        f"Accuracy: "
        f"{percent(accuracy):.2f}%"
    )

    print(
        f"Macro precision: "
        f"{percent(macro_precision):.2f}%"
    )

    print(
        f"Macro recall: "
        f"{percent(macro_recall):.2f}%"
    )

    print(
        f"Macro F1: "
        f"{percent(macro_f1):.2f}%"
    )

    print(
        f"Weighted F1: "
        f"{percent(weighted_f1):.2f}%"
    )

    print()
    print("CATEGORY RESULTS")
    print("-" * 60)

    for category, result in (
        category_results.items()
    ):
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
        f"Model saved: {MODEL_PATH}"
    )

    print(
        f"Metadata saved: "
        f"{METADATA_PATH}"
    )

    print()
    print(
        "The official test split "
        "was not used."
    )


if __name__ == "__main__":
    main()