from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report


CANDIDATE = "hate-speech-v2-rc2-development"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
LABELS = ("hate_speech", "abusive_words", "safe_or_other")
ROOT = Path(__file__).resolve().parents[2]
CIVIL_DIRECTORY = ROOT / "datasets" / "public" / "civil_comments_hate_rc2"
HATEXPLAIN_DIRECTORY = ROOT / "datasets" / "public" / "hatexplain"
MODEL_DIRECTORY = ROOT / "backend" / "storage" / "models" / "hate_speech_v2_rc2"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v2_rc2_development"
)

MODEL_PATH = MODEL_DIRECTORY / "classifier_bundle.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "development_config.json"
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"

HATEXPLAIN_LABEL_MAPPING = {
    "Hate Speech & Discrimination": "hate_speech",
    "Abusive Words": "abusive_words",
    "Normal/Ignore": "safe_or_other",
}


def text_hash(text: str) -> str:
    normalized = " ".join(str(text or "").casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_civil_split(split: str) -> list[dict[str, str]]:
    path = CIVIL_DIRECTORY / f"{split}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Civil Comments {split} split not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = [
        {
            "record_id": str(row["record_id"]),
            "text": str(row["text"]).strip(),
            "label": str(row["label"]),
            "text_hash": str(row["source_text_sha256"]),
            "source": "Civil Comments",
        }
        for row in rows
        if str(row.get("text", "")).strip() and row.get("label") in LABELS
    ]
    if not result:
        raise RuntimeError(f"Civil Comments {split} split is empty.")
    return result


def load_hatexplain_split(split: str) -> list[dict[str, str]]:
    path = HATEXPLAIN_DIRECTORY / f"{split}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"HateXplain {split} split not found: {path}")
    result: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            label = HATEXPLAIN_LABEL_MAPPING.get(str(row.get("category", "")))
            if not text or not label:
                continue
            result.append(
                {
                    "record_id": str(row.get("record_id", "")),
                    "text": text,
                    "label": label,
                    "text_hash": text_hash(text),
                    "source": "HateXplain",
                }
            )
    if not result:
        raise RuntimeError(f"HateXplain {split} split is empty.")
    return result


def deduplicate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        digest = row["text_hash"]
        if digest in seen:
            continue
        seen.add(digest)
        selected.append(row)
    return selected


def aligned(probabilities: np.ndarray, classes: np.ndarray) -> np.ndarray:
    indexes = [list(classes).index(label) for label in LABELS]
    return probabilities[:, indexes]


def counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(row["label"] for row in rows).items()))


def main() -> None:
    # Deliberately load only train and validation. Neither test.csv is opened.
    civil_train = load_civil_split("train")
    civil_validation = load_civil_split("validation")
    hatexplain_train = load_hatexplain_split("train")
    hatexplain_validation = load_hatexplain_split("validation")

    train = deduplicate(civil_train + hatexplain_train)
    validation = deduplicate(civil_validation + hatexplain_validation)

    train_hashes = {row["text_hash"] for row in train}
    validation_hashes = {row["text_hash"] for row in validation}
    overlap = train_hashes & validation_hashes
    if overlap:
        raise RuntimeError(
            f"Train/validation text leakage detected: {len(overlap)} records."
        )

    train_text = [row["text"] for row in train]
    validation_text = [row["text"] for row in validation]
    y_train = np.array([row["label"] for row in train])
    y_validation = np.array([row["label"] for row in validation])

    print("HATE SPEECH RC2 DEVELOPMENT TRAINING")
    print("=" * 60)
    print(f"Training records: {len(train):,}")
    print(f"Validation records: {len(validation):,}")
    print(f"Train/validation overlap: {len(overlap)}")
    print(f"Training labels: {counts(train)}")
    print(f"Validation labels: {counts(validation)}")
    print("The Civil Comments and HateXplain test splits were not opened.")
    print()

    print("Training lexical word/character classifier...")
    word_vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        ngram_range=(1, 2),
        min_df=2,
        max_features=60_000,
    )
    character_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        ngram_range=(3, 5),
        min_df=2,
        max_features=80_000,
    )
    lexical_train = hstack(
        (
            word_vectorizer.fit_transform(train_text),
            character_vectorizer.fit_transform(train_text),
        ),
        format="csr",
    )
    lexical_validation = hstack(
        (
            word_vectorizer.transform(validation_text),
            character_vectorizer.transform(validation_text),
        ),
        format="csr",
    )
    lexical_classifier = LogisticRegression(
        C=4.0,
        class_weight="balanced",
        max_iter=4_000,
        random_state=42,
    )
    lexical_classifier.fit(lexical_train, y_train)
    lexical_probabilities = aligned(
        lexical_classifier.predict_proba(lexical_validation),
        lexical_classifier.classes_,
    )

    print(f"Loading semantic encoder: {MODEL_NAME}")
    encoder = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")
    semantic_train = encoder.encode(
        train_text,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    semantic_validation = encoder.encode(
        validation_text,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    semantic_classifier = LogisticRegression(
        C=2.0,
        class_weight="balanced",
        max_iter=4_000,
        random_state=42,
    )
    semantic_classifier.fit(csr_matrix(semantic_train), y_train)
    semantic_probabilities = aligned(
        semantic_classifier.predict_proba(csr_matrix(semantic_validation)),
        semantic_classifier.classes_,
    )

    best: tuple[tuple[float, float, float], float, dict] | None = None
    for lexical_weight in np.arange(0.0, 1.01, 0.05):
        probabilities = (
            lexical_weight * lexical_probabilities
            + (1.0 - lexical_weight) * semantic_probabilities
        )
        predictions = np.array(
            [LABELS[index] for index in probabilities.argmax(axis=1)]
        )
        report = classification_report(
            y_validation,
            predictions,
            labels=list(LABELS),
            output_dict=True,
            zero_division=0,
        )
        accuracy = float(accuracy_score(y_validation, predictions))
        macro_f1 = float(report["macro avg"]["f1-score"])
        every_label_passes = all(
            float(report[label][metric]) >= 0.85
            for label in LABELS
            for metric in ("precision", "recall", "f1-score")
        )
        rank = (float(every_label_passes), macro_f1, accuracy)
        candidate = (rank, float(lexical_weight), report)
        if best is None or rank > best[0]:
            best = candidate

    if best is None:
        raise RuntimeError("Unable to select a lexical/semantic ensemble weight.")

    _, lexical_weight, report = best
    probabilities = (
        lexical_weight * lexical_probabilities
        + (1.0 - lexical_weight) * semantic_probabilities
    )
    predictions = np.array(
        [LABELS[index] for index in probabilities.argmax(axis=1)]
    )
    accuracy = float(accuracy_score(y_validation, predictions))
    macro_f1 = float(report["macro avg"]["f1-score"])
    every_label_passes = all(
        float(report[label][metric]) >= 0.85
        for label in LABELS
        for metric in ("precision", "recall", "f1-score")
    )
    passed = bool(accuracy >= 0.85 and macro_f1 >= 0.85 and every_label_passes)

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "word_vectorizer": word_vectorizer,
            "character_vectorizer": character_vectorizer,
            "lexical_classifier": lexical_classifier,
            "semantic_classifier": semantic_classifier,
        },
        MODEL_PATH,
        compress=3,
    )
    config = {
        "candidate": CANDIDATE,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "labels": list(LABELS),
        "embedding_model": MODEL_NAME,
        "embedding_model_revision": MODEL_REVISION,
        "lexical_weight": round(lexical_weight, 2),
        "semantic_weight": round(1.0 - lexical_weight, 2),
        "training_sources": ["Civil Comments train", "HateXplain train"],
        "validation_sources": [
            "Civil Comments validation",
            "HateXplain validation",
        ],
        "test_splits_opened": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result = {
        "candidate": CANDIDATE,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_records": len(train),
        "validation_records": len(validation),
        "training_label_counts": counts(train),
        "validation_label_counts": counts(validation),
        "train_validation_overlap": len(overlap),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "lexical_weight": round(lexical_weight, 2),
        "semantic_weight": round(1.0 - lexical_weight, 2),
        "classification_report": report,
        "passed_development_gate": passed,
        "test_splits_opened": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "limitations": [
            "Development validation is not independent accuracy.",
            "Protected-class subtype coverage requires a separate boundary dataset.",
            "The candidate must be selectively calibrated and frozen before testing.",
        ],
    }
    REPORT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH RC2 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Macro F1: {macro_f1 * 100:.2f}%")
    print(f"Lexical weight: {lexical_weight:.2f}")
    print(f"Semantic weight: {1.0 - lexical_weight:.2f}")
    print()
    print("LABEL RESULTS")
    print("-" * 60)
    for label in LABELS:
        values = report[label]
        print(
            f"{label}: precision {values['precision'] * 100:.2f}% | "
            f"recall {values['recall'] * 100:.2f}% | "
            f"F1 {values['f1-score'] * 100:.2f}%"
        )
    print()
    print(f"Passed development gate: {passed}")
    print(f"Artifact: {MODEL_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("The Civil Comments and HateXplain test splits were not opened.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
