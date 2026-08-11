from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report


CANDIDATE = "cyberbullying-v2-rc2-development"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
LABELS = ("targeted_threat", "abusive_words", "safe_or_other")
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "datasets" / "public" / "civil_comments_cyber"
MODEL_DIR = ROOT / "backend" / "storage" / "models" / "cyberbullying_v2_rc2"
REPORT_DIR = ROOT / "reports" / "evaluation" / "cyberbullying" / "v2_rc2_development"


def read_split(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / f"{name}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Imported Civil Comments split not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"Civil Comments {name} split is empty.")
    return rows


def aligned_probabilities(
    probabilities: np.ndarray,
    classifier_classes: np.ndarray,
) -> np.ndarray:
    indexes = [list(classifier_classes).index(label) for label in LABELS]
    return probabilities[:, indexes]


def main() -> None:
    train = read_split("train")
    validation = read_split("validation")
    # Deliberately do not open test.csv in this script.
    train_text = [row["text"] for row in train]
    validation_text = [row["text"] for row in validation]
    y_train = np.array([row["label"] for row in train])
    y_validation = np.array([row["label"] for row in validation])

    train_hashes = {row["source_text_sha256"] for row in train}
    validation_hashes = {row["source_text_sha256"] for row in validation}
    overlap = sorted(train_hashes & validation_hashes)
    if overlap:
        raise RuntimeError(f"Train/validation text leakage detected: {len(overlap)}")

    print("Training lexical Civil Comments classifier...")
    word_vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        ngram_range=(1, 2),
        min_df=2,
        max_features=35_000,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        ngram_range=(3, 5),
        min_df=2,
        max_features=45_000,
    )
    word_train = word_vectorizer.fit_transform(train_text)
    char_train = char_vectorizer.fit_transform(train_text)
    word_validation = word_vectorizer.transform(validation_text)
    char_validation = char_vectorizer.transform(validation_text)
    lexical_train = hstack((word_train, char_train), format="csr")
    lexical_validation = hstack((word_validation, char_validation), format="csr")
    lexical_classifier = LogisticRegression(
        C=4.0,
        class_weight="balanced",
        max_iter=4_000,
        random_state=42,
    )
    lexical_classifier.fit(lexical_train, y_train)
    lexical_probability = aligned_probabilities(
        lexical_classifier.predict_proba(lexical_validation),
        lexical_classifier.classes_,
    )

    print(f"Loading semantic model: {MODEL_NAME}")
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
    semantic_probability = aligned_probabilities(
        semantic_classifier.predict_proba(csr_matrix(semantic_validation)),
        semantic_classifier.classes_,
    )

    best: tuple[tuple[float, float, float], float, np.ndarray, dict[str, object]] | None = None
    for lexical_weight in np.arange(0.0, 1.01, 0.05):
        probability = (
            lexical_weight * lexical_probability
            + (1.0 - lexical_weight) * semantic_probability
        )
        predictions = np.array([LABELS[index] for index in probability.argmax(axis=1)])
        report = classification_report(
            y_validation,
            predictions,
            labels=list(LABELS),
            output_dict=True,
            zero_division=0,
        )
        every_label_passes = all(
            float(report[label][metric]) >= 0.85
            for label in LABELS
            for metric in ("precision", "recall", "f1-score")
        )
        accuracy = float(accuracy_score(y_validation, predictions))
        rank = (
            float(every_label_passes),
            float(report["macro avg"]["f1-score"]),
            accuracy,
        )
        candidate = (rank, float(lexical_weight), predictions, report)
        if best is None or rank > best[0]:
            best = candidate
    if best is None:
        raise RuntimeError("Unable to select an ensemble weight.")

    _, lexical_weight, predictions, report = best
    accuracy = float(accuracy_score(y_validation, predictions))
    macro_f1 = float(report["macro avg"]["f1-score"])
    every_label_passes = all(
        float(report[label][metric]) >= 0.85
        for label in LABELS
        for metric in ("precision", "recall", "f1-score")
    )
    passed = accuracy >= 0.85 and macro_f1 >= 0.85 and every_label_passes

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = MODEL_DIR / "classifier_bundle.joblib"
    config_path = MODEL_DIR / "config.json"
    report_path = REPORT_DIR / "validation_report.json"
    mismatch_path = REPORT_DIR / "validation_mismatches.csv"
    joblib.dump(
        {
            "word_vectorizer": word_vectorizer,
            "char_vectorizer": char_vectorizer,
            "lexical_classifier": lexical_classifier,
            "semantic_classifier": semantic_classifier,
        },
        artifact_path,
    )
    config = {
        "candidate": CANDIDATE,
        "embedding_model": MODEL_NAME,
        "embedding_model_revision": MODEL_REVISION,
        "labels": list(LABELS),
        "lexical_weight": round(lexical_weight, 2),
        "semantic_weight": round(1.0 - lexical_weight, 2),
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "test_split_read": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    report_payload = {
        "candidate": CANDIDATE,
        "training_records": len(train),
        "validation_records": len(validation),
        "train_validation_overlap": len(overlap),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "lexical_weight": round(lexical_weight, 2),
        "classification_report": report,
        "passed_development_gate": passed,
        "test_split_read": False,
        "limitations": (
            "This message-level classifier does not validate repetition, "
            "coordinated campaigns, or continued unwanted contact."
        ),
    }
    report_path.write_text(
        json.dumps(report_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with mismatch_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("record_id", "expected", "predicted", "text"),
        )
        writer.writeheader()
        for row, predicted in zip(validation, predictions, strict=True):
            if predicted != row["label"]:
                writer.writerow(
                    {
                        "record_id": row["record_id"],
                        "expected": row["label"],
                        "predicted": predicted,
                        "text": row["text"],
                    }
                )

    print("\nCIVIL COMMENTS CYBER/ABUSIVE RC2 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Training records: {len(train)}")
    print(f"Validation records: {len(validation)}")
    print(f"Train/validation overlap: {len(overlap)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Macro F1: {macro_f1 * 100:.2f}%")
    print(f"Lexical weight: {lexical_weight:.2f}")
    print(f"Semantic weight: {1.0 - lexical_weight:.2f}")
    print("\nLABEL RESULTS")
    print("-" * 60)
    for label in LABELS:
        values = report[label]
        print(
            f"{label}: precision {values['precision'] * 100:.2f}% | "
            f"recall {values['recall'] * 100:.2f}% | "
            f"F1 {values['f1-score'] * 100:.2f}%"
        )
    print(f"\nPassed development gate: {passed}")
    print(f"Artifact: {artifact_path}")
    print(f"Report: {report_path}")
    print("The external test split was not opened.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
