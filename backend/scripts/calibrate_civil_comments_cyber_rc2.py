from __future__ import annotations

import csv
import json
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sentence_transformers import SentenceTransformer


TARGET_PRECISION = 0.90
LABELS = ("targeted_threat", "abusive_words", "safe_or_other")
ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "datasets" / "public" / "civil_comments_cyber" / "validation.csv"
MODEL_DIR = ROOT / "backend" / "storage" / "models" / "cyberbullying_v2_rc2"
REPORT_DIR = ROOT / "reports" / "evaluation" / "cyberbullying" / "v2_rc2_selective"


def aligned(probability: np.ndarray, classes: np.ndarray) -> np.ndarray:
    indexes = [list(classes).index(label) for label in LABELS]
    return probability[:, indexes]


def select_threshold(
    label: str,
    truth: np.ndarray,
    predictions: np.ndarray,
    confidence: np.ndarray,
) -> dict[str, float | int | bool]:
    best: tuple[int, float, float] | None = None
    best_result: dict[str, float | int | bool] | None = None
    for threshold in np.arange(0.34, 1.0, 0.01):
        accepted = (predictions == label) & (confidence >= threshold)
        accepted_count = int(accepted.sum())
        if accepted_count == 0:
            continue
        correct = int((truth[accepted] == label).sum())
        precision = correct / accepted_count
        if precision < TARGET_PRECISION:
            continue
        support = int((truth == label).sum())
        selective_recall = correct / support if support else 0.0
        rank = (accepted_count, precision, -float(threshold))
        if best is None or rank > best:
            best = rank
            best_result = {
                "enabled": True,
                "threshold": round(float(threshold), 2),
                "accepted": accepted_count,
                "precision": round(precision, 4),
                "selective_recall": round(selective_recall, 4),
            }
    return best_result or {
        "enabled": False,
        "threshold": 1.01,
        "accepted": 0,
        "precision": 0.0,
        "selective_recall": 0.0,
    }


def main() -> None:
    if not DATA_PATH.is_file():
        raise FileNotFoundError(f"Validation split not found: {DATA_PATH}")
    artifact_path = MODEL_DIR / "classifier_bundle.joblib"
    config_path = MODEL_DIR / "config.json"
    if not artifact_path.is_file() or not config_path.is_file():
        raise FileNotFoundError("Train the Civil Comments RC2 ensemble first.")
    with DATA_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    truth = np.array([row["label"] for row in rows])
    text = [row["text"] for row in rows]
    bundle = joblib.load(artifact_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))

    word = bundle["word_vectorizer"].transform(text)
    char = bundle["char_vectorizer"].transform(text)
    lexical_features = hstack((word, char), format="csr")
    lexical_probability = aligned(
        bundle["lexical_classifier"].predict_proba(lexical_features),
        bundle["lexical_classifier"].classes_,
    )
    encoder = SentenceTransformer(
        config["embedding_model"],
        revision=config["embedding_model_revision"],
        device="cpu",
    )
    embeddings = encoder.encode(
        text,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    semantic_probability = aligned(
        bundle["semantic_classifier"].predict_proba(csr_matrix(embeddings)),
        bundle["semantic_classifier"].classes_,
    )
    lexical_weight = float(config["lexical_weight"])
    probability = (
        lexical_weight * lexical_probability
        + (1.0 - lexical_weight) * semantic_probability
    )
    prediction_indexes = probability.argmax(axis=1)
    predictions = np.array([LABELS[index] for index in prediction_indexes])
    confidence = probability.max(axis=1)
    thresholds = {
        label: select_threshold(label, truth, predictions, confidence)
        for label in LABELS
    }

    accepted = np.array(
        [
            bool(thresholds[label]["enabled"])
            and score >= float(thresholds[label]["threshold"])
            for label, score in zip(predictions, confidence, strict=True)
        ]
    )
    accepted_count = int(accepted.sum())
    correct_accepted = int((truth[accepted] == predictions[accepted]).sum())
    selective_accuracy = correct_accepted / accepted_count if accepted_count else 0.0
    coverage = accepted_count / len(rows)
    uncertain_count = len(rows) - accepted_count
    every_enabled = all(bool(thresholds[label]["enabled"]) for label in LABELS)
    every_precision_passes = all(
        float(thresholds[label]["precision"]) >= TARGET_PRECISION for label in LABELS
    )
    passed = (
        every_enabled
        and every_precision_passes
        and selective_accuracy >= TARGET_PRECISION
        and coverage >= 0.50
    )

    config["selective_thresholds"] = thresholds
    config["uncertain_behavior"] = {
        "category": "Uncertain",
        "action": "Refer to human review",
        "automatic_enforcement_allowed": False,
        "may_override_other_specialists": False,
    }
    config["selectively_calibrated"] = passed
    config["independently_validated"] = False
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    report = {
        "validation_records": len(rows),
        "target_precision": TARGET_PRECISION,
        "thresholds": thresholds,
        "accepted_records": accepted_count,
        "uncertain_records": uncertain_count,
        "selective_accuracy": round(selective_accuracy, 4),
        "coverage": round(coverage, 4),
        "passed_selective_development_gate": passed,
        "test_split_read": False,
        "limitations": (
            "Selective precision measures accepted message-level decisions only. "
            "It is not full cyberbullying-category recall or production accuracy."
        ),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "calibration_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("CIVIL COMMENTS RC2 SELECTIVE CALIBRATION")
    print("=" * 60)
    for label in LABELS:
        values = thresholds[label]
        print(f"{label}")
        print(f"  Enabled: {values['enabled']}")
        print(f"  Threshold: {values['threshold']}")
        print(f"  Accepted: {values['accepted']}")
        print(f"  Precision: {float(values['precision']) * 100:.2f}%")
        print(f"  Selective recall: {float(values['selective_recall']) * 100:.2f}%")
    print("\n" + "-" * 60)
    print(f"Selective accuracy: {selective_accuracy * 100:.2f}%")
    print(f"Coverage: {coverage * 100:.2f}%")
    print(f"Accepted records: {accepted_count}")
    print(f"Uncertain records: {uncertain_count}")
    print(f"Passed selective development gate: {passed}")
    print(f"Report: {report_path}")
    print("The external test split was not opened.")


if __name__ == "__main__":
    main()
