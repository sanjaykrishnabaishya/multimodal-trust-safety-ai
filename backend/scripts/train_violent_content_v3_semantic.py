from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "datasets" / "development" / "violent_content_v3"
DATASET_PATH = DATASET_DIR / "development.csv"
OUTPUT_DIR = ROOT / "backend" / "storage" / "models" / "violent_content_v3"
REPORT_DIR = ROOT / "reports" / "evaluation" / "violent_content" / "v3_development"
MIN_PRECISION = 0.85
THRESHOLDS = tuple(round(value, 2) for value in np.arange(0.40, 0.96, 0.01))


def read_rows() -> list[dict[str, str]]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}. Run the V3 generator first."
        )
    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("The V3 development dataset is empty.")
    return rows


def select_thresholds(
    labels: list[str],
    truth: np.ndarray,
    probabilities: np.ndarray,
) -> dict[str, dict[str, float | int | bool]]:
    predicted_indexes = probabilities.argmax(axis=1)
    predicted_labels = np.array([labels[index] for index in predicted_indexes])
    confidence = probabilities.max(axis=1)
    settings: dict[str, dict[str, float | int | bool]] = {}

    for label in labels:
        best: dict[str, float | int | bool] | None = None
        for threshold in THRESHOLDS:
            accepted = (predicted_labels == label) & (confidence >= threshold)
            accepted_count = int(accepted.sum())
            if accepted_count == 0:
                continue
            correct_count = int((truth[accepted] == label).sum())
            precision = correct_count / accepted_count
            eligible_count = int((truth == label).sum())
            recall = correct_count / eligible_count if eligible_count else 0.0
            if precision < MIN_PRECISION:
                continue
            candidate = {
                "enabled": True,
                "threshold": float(threshold),
                "accepted": accepted_count,
                "precision": round(precision, 4),
                "selective_recall": round(recall, 4),
            }
            if best is None or (
                candidate["accepted"], candidate["precision"]
            ) > (best["accepted"], best["precision"]):
                best = candidate
        settings[label] = best or {
            "enabled": False,
            "threshold": 1.01,
            "accepted": 0,
            "precision": 0.0,
            "selective_recall": 0.0,
        }
    return settings


def main() -> None:
    rows = read_rows()
    train = [row for row in rows if row["split"] == "train"]
    validation = [row for row in rows if row["split"] == "validation"]
    if not train or not validation:
        raise RuntimeError("Both train and validation records are required.")

    train_families = {row["family_id"] for row in train}
    validation_families = {row["family_id"] for row in validation}
    overlap = sorted(train_families & validation_families)
    if overlap:
        raise RuntimeError(f"Family leakage detected: {overlap}")

    print(f"Loading semantic embedding model: {MODEL_NAME}")
    encoder = SentenceTransformer(MODEL_NAME, device="cpu")
    x_train = encoder.encode(
        [row["text"] for row in train],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    x_validation = encoder.encode(
        [row["text"] for row in validation],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    y_train = np.array([row["semantic_class"] for row in train])
    y_validation = np.array([row["semantic_class"] for row in validation])

    classifier = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        max_iter=3000,
        random_state=42,
    )
    classifier.fit(x_train, y_train)
    probabilities = classifier.predict_proba(x_validation)
    predictions = classifier.predict(x_validation)
    labels = list(classifier.classes_)
    accuracy = float(accuracy_score(y_validation, predictions))
    detailed = classification_report(
        y_validation,
        predictions,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )
    thresholds = select_thresholds(
        labels,
        y_validation,
        probabilities,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = OUTPUT_DIR / "classifier.joblib"
    config_path = OUTPUT_DIR / "config.json"
    report_path = REPORT_DIR / "validation_report.json"
    predictions_path = REPORT_DIR / "validation_predictions.csv"

    joblib.dump(classifier, artifact_path)
    config = {
        "candidate": "violent-content-v3-semantic-development-r2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "embedding_model": MODEL_NAME,
        "embedding_model_license": "Apache-2.0",
        "classes": labels,
        "thresholds": thresholds,
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "notice": (
            "Development candidate only. Low-confidence predictions must not "
            "override other policy specialists or trigger automatic action."
        ),
    }
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = {
        "candidate": config["candidate"],
        "records": len(validation),
        "train_records": len(train),
        "validation_records": len(validation),
        "family_overlap": overlap,
        "accuracy": round(accuracy, 4),
        "macro_f1": round(float(detailed["macro avg"]["f1-score"]), 4),
        "classification_report": detailed,
        "confusion_matrix": confusion_matrix(
            y_validation, predictions, labels=labels
        ).tolist(),
        "labels": labels,
        "thresholds": thresholds,
        "development_gate": {
            "accuracy_at_least_85_percent": accuracy >= 0.85,
            "every_class_f1_at_least_85_percent": all(
                float(detailed[label]["f1-score"]) >= 0.85 for label in labels
            ),
        },
        "notice": "Development score only; this is not independent accuracy.",
    }
    report["passed_development_gate"] = all(
        report["development_gate"].values()
    )
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with predictions_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "record_id",
                "family_id",
                "expected",
                "predicted",
                "confidence",
                "correct",
            ),
        )
        writer.writeheader()
        for row, predicted, probability_row in zip(
            validation, predictions, probabilities, strict=True
        ):
            writer.writerow(
                {
                    "record_id": row["record_id"],
                    "family_id": row["family_id"],
                    "expected": row["semantic_class"],
                    "predicted": predicted,
                    "confidence": round(float(probability_row.max()), 4),
                    "correct": predicted == row["semantic_class"],
                }
            )

    print("\nVIOLENT CONTENT V3 SEMANTIC DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Training records: {len(train)}")
    print(f"Validation records: {len(validation)}")
    print(f"Family overlap: {len(overlap)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Macro F1: {detailed['macro avg']['f1-score'] * 100:.2f}%")
    print("\nCLASS RESULTS")
    print("-" * 60)
    for label in labels:
        values = detailed[label]
        print(
            f"{label}: precision {values['precision'] * 100:.2f}% | "
            f"recall {values['recall'] * 100:.2f}% | "
            f"F1 {values['f1-score'] * 100:.2f}%"
        )
    print("\nSELECTIVE THRESHOLDS")
    print("-" * 60)
    for label in labels:
        print(f"{label}: {thresholds[label]}")
    print(f"\nPassed development gate: {report['passed_development_gate']}")
    print(f"Model artifact: {artifact_path}")
    print(f"Report: {report_path}")
    print("\nThis is development evidence, not independent accuracy.")
    print("The candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
