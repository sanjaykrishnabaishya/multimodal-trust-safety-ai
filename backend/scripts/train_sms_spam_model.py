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
from sklearn.linear_model import (
    LogisticRegression,
)
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import (
    FeatureUnion,
    Pipeline,
)


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
    / "uci_sms"
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
    / "sms_spam"
)

MODEL_PATH = (
    MODEL_DIRECTORY
    / "sms_spam_model.joblib"
)

METADATA_PATH = (
    MODEL_DIRECTORY
    / "sms_spam_model_metadata.json"
)


RANDOM_SEED = 42

NORMAL_LABEL = 0
SPAM_LABEL = 1

NORMAL_CATEGORY = "Normal/Ignore"

SPAM_CATEGORY = (
    "Spam, Scam & Phishing"
)


def load_dataset(
    dataset_path: Path,
) -> tuple[
    list[str],
    np.ndarray,
]:
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset does not exist: "
            f"{dataset_path}"
        )

    texts: list[str] = []
    labels: list[int] = []

    with dataset_path.open(
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

            if not text:
                continue

            if category == SPAM_CATEGORY:
                label = SPAM_LABEL

            elif category == NORMAL_CATEGORY:
                label = NORMAL_LABEL

            else:
                continue

            texts.append(text)
            labels.append(label)

    if not texts:
        raise RuntimeError(
            "No valid records were loaded "
            f"from {dataset_path}."
        )

    return texts, np.asarray(
        labels,
        dtype=np.int64,
    )


def build_model() -> (
    CalibratedClassifierCV
):
    word_vectorizer = (
        TfidfVectorizer(
            analyzer="word",
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.995,
            max_features=40000,
            sublinear_tf=True,
            norm="l2",
        )
    )

    character_vectorizer = (
        TfidfVectorizer(
            analyzer="char_wb",
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(3, 5),
            min_df=2,
            max_features=50000,
            sublinear_tf=True,
            norm="l2",
        )
    )

    features = FeatureUnion(
        transformer_list=[
            (
                "word_features",
                word_vectorizer,
            ),
            (
                "character_features",
                character_vectorizer,
            ),
        ],
        n_jobs=-1,
    )

    classifier = (
        LogisticRegression(
            C=4.0,
            class_weight="balanced",
            solver="liblinear",
            max_iter=2000,
            random_state=RANDOM_SEED,
        )
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

    calibrated_model = (
        CalibratedClassifierCV(
            estimator=pipeline,
            method="sigmoid",
            cv=5,
            n_jobs=-1,
        )
    )

    return calibrated_model


def get_spam_probabilities(
    model: Any,
    texts: list[str],
) -> np.ndarray:
    probabilities = (
        model.predict_proba(
            texts
        )
    )

    class_values = list(
        model.classes_
    )

    if SPAM_LABEL not in class_values:
        raise RuntimeError(
            "The trained model has no "
            "spam class."
        )

    spam_index = class_values.index(
        SPAM_LABEL
    )

    return probabilities[
        :,
        spam_index,
    ]


def evaluate_threshold(
    labels: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> dict[str, float]:
    predictions = (
        probabilities >= threshold
    ).astype(np.int64)

    return {
        "threshold": threshold,
        "accuracy": accuracy_score(
            labels,
            predictions,
        ),
        "precision": precision_score(
            labels,
            predictions,
            zero_division=0,
        ),
        "recall": recall_score(
            labels,
            predictions,
            zero_division=0,
        ),
        "spam_f1": f1_score(
            labels,
            predictions,
            zero_division=0,
        ),
        "macro_f1": f1_score(
            labels,
            predictions,
            average="macro",
            zero_division=0,
        ),
    }


def choose_threshold(
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> dict[str, float]:
    threshold_results = [
        evaluate_threshold(
            labels=labels,
            probabilities=(
                probabilities
            ),
            threshold=round(
                threshold,
                2,
            ),
        )
        for threshold in np.arange(
            0.10,
            0.91,
            0.01,
        )
    ]

    preferred_results = [
        result
        for result in threshold_results
        if (
            result["precision"] >= 0.85
            and result["recall"] >= 0.80
        )
    ]

    if preferred_results:
        candidates = preferred_results
    else:
        candidates = threshold_results

    return max(
        candidates,
        key=lambda result: (
            result["macro_f1"],
            result["spam_f1"],
            result["recall"],
            result["precision"],
        ),
    )


def count_labels(
    labels: np.ndarray,
) -> dict[str, int]:
    return {
        NORMAL_CATEGORY: int(
            np.sum(
                labels == NORMAL_LABEL
            )
        ),
        SPAM_CATEGORY: int(
            np.sum(
                labels == SPAM_LABEL
            )
        ),
    }


def percentage(
    value: float,
) -> float:
    return round(
        value * 100,
        2,
    )


def main() -> None:
    print(
        "Loading UCI SMS training "
        "and validation data..."
    )

    train_texts, train_labels = (
        load_dataset(
            TRAIN_PATH
        )
    )

    validation_texts, validation_labels = (
        load_dataset(
            VALIDATION_PATH
        )
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
        "Training the word-and-character "
        "spam specialist..."
    )

    model = build_model()

    model.fit(
        train_texts,
        train_labels,
    )

    print(
        "Training completed."
    )

    validation_probabilities = (
        get_spam_probabilities(
            model,
            validation_texts,
        )
    )

    selected_result = (
        choose_threshold(
            labels=validation_labels,
            probabilities=(
                validation_probabilities
            ),
        )
    )

    selected_threshold = float(
        selected_result["threshold"]
    )

    validation_predictions = (
        validation_probabilities
        >= selected_threshold
    ).astype(np.int64)

    false_positives = int(
        np.sum(
            (
                validation_labels
                == NORMAL_LABEL
            )
            & (
                validation_predictions
                == SPAM_LABEL
            )
        )
    )

    false_negatives = int(
        np.sum(
            (
                validation_labels
                == SPAM_LABEL
            )
            & (
                validation_predictions
                == NORMAL_LABEL
            )
        )
    )

    MODEL_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_package = {
        "model": model,
        "threshold": (
            selected_threshold
        ),
        "normal_label": (
            NORMAL_LABEL
        ),
        "spam_label": (
            SPAM_LABEL
        ),
        "normal_category": (
            NORMAL_CATEGORY
        ),
        "spam_category": (
            SPAM_CATEGORY
        ),
        "model_version": "1.0.0",
        "training_source": (
            "UCI SMS Spam Collection"
        ),
    }

    joblib.dump(
        model_package,
        MODEL_PATH,
        compress=3,
    )

    metadata = {
        "model_name": (
            "TrustScope SMS Spam Specialist"
        ),
        "model_version": "1.0.0",
        "model_type": (
            "calibrated_word_character_"
            "tfidf_logistic_regression"
        ),
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "random_seed": (
            RANDOM_SEED
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
            count_labels(
                train_labels
            )
        ),
        "validation_category_counts": (
            count_labels(
                validation_labels
            )
        ),
        "selected_threshold": (
            selected_threshold
        ),
        "validation_results": {
            "accuracy_percent": (
                percentage(
                    selected_result[
                        "accuracy"
                    ]
                )
            ),
            "precision_percent": (
                percentage(
                    selected_result[
                        "precision"
                    ]
                )
            ),
            "recall_percent": (
                percentage(
                    selected_result[
                        "recall"
                    ]
                )
            ),
            "spam_f1_percent": (
                percentage(
                    selected_result[
                        "spam_f1"
                    ]
                )
            ),
            "macro_f1_percent": (
                percentage(
                    selected_result[
                        "macro_f1"
                    ]
                )
            ),
            "false_positives": (
                false_positives
            ),
            "false_negatives": (
                false_negatives
            ),
        },
        "feature_configuration": {
            "word_ngrams": [1, 2],
            "character_ngrams": [3, 5],
            "class_weight": "balanced",
            "probability_calibration": (
                "five-fold sigmoid"
            ),
        },
        "important_note": (
            "The UCI test split was not used "
            "for training, threshold selection, "
            "or calibration."
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
    print("VALIDATION RESULTS")
    print("=" * 60)

    print(
        f"Selected threshold: "
        f"{selected_threshold:.2f}"
    )

    print(
        "Accuracy: "
        f"{percentage(selected_result['accuracy']):.2f}%"
    )

    print(
        "Spam precision: "
        f"{percentage(selected_result['precision']):.2f}%"
    )

    print(
        "Spam recall: "
        f"{percentage(selected_result['recall']):.2f}%"
    )

    print(
        "Spam F1: "
        f"{percentage(selected_result['spam_f1']):.2f}%"
    )

    print(
        "Macro F1: "
        f"{percentage(selected_result['macro_f1']):.2f}%"
    )

    print(
        f"False positives: "
        f"{false_positives:,}"
    )

    print(
        f"False negatives: "
        f"{false_negatives:,}"
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
        "The test split was not used."
    )


if __name__ == "__main__":
    main()