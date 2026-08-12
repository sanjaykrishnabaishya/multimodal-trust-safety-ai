from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[2]
CIVIL_DIRECTORY = ROOT / "datasets" / "public" / "civil_comments_hate_rc2"
HATEXPLAIN_DIRECTORY = ROOT / "datasets" / "public" / "hatexplain"
MODEL_DIRECTORY = ROOT / "backend" / "storage" / "models" / "hate_speech_v2_rc2"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v2_rc2_calibration"
)
MODEL_PATH = MODEL_DIRECTORY / "classifier_bundle.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "development_config.json"
CALIBRATION_PATH = MODEL_DIRECTORY / "calibration.json"
REPORT_PATH = REPORT_DIRECTORY / "calibration_report.json"

LABELS = ("hate_speech", "abusive_words", "safe_or_other")
HATE_LABEL = "hate_speech"
HATEXPLAIN_MAPPING = {
    "Hate Speech & Discrimination": "hate_speech",
    "Abusive Words": "abusive_words",
    "Normal/Ignore": "safe_or_other",
}

TARGET_OVERALL_PRECISION = 0.90
TARGET_SOURCE_PRECISION = 0.85
TARGET_NON_HATE_SPECIFICITY = 0.90
MINIMUM_TOTAL_ACCEPTED = 30
MINIMUM_ACCEPTED_PER_SOURCE = 10


def load_validation() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    civil_path = CIVIL_DIRECTORY / "validation.csv"
    hatexplain_path = HATEXPLAIN_DIRECTORY / "validation.csv"
    for path in (civil_path, hatexplain_path):
        if not path.is_file():
            raise FileNotFoundError(f"Validation split not found: {path}")

    with civil_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            label = str(row.get("label", ""))
            if text and label in LABELS:
                rows.append({"text": text, "label": label, "source": "Civil Comments"})

    with hatexplain_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            label = HATEXPLAIN_MAPPING.get(str(row.get("category", "")))
            if text and label:
                rows.append({"text": text, "label": label, "source": "HateXplain"})

    if not rows:
        raise RuntimeError("No validation records were loaded.")
    return rows


def aligned(probabilities: np.ndarray, classes: np.ndarray) -> np.ndarray:
    indexes = [list(classes).index(label) for label in LABELS]
    return probabilities[:, indexes]


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    for path in (MODEL_PATH, CONFIG_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required development artifact not found: {path}")

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("test_splits_opened") is not False:
        raise RuntimeError("Development config does not preserve the test contract.")

    rows = load_validation()
    text = [row["text"] for row in rows]
    truth = np.array([row["label"] for row in rows])
    sources = np.array([row["source"] for row in rows])

    print("Loading the Hate Speech RC2 development ensemble...")
    bundle = joblib.load(MODEL_PATH)
    lexical_features = hstack(
        (
            bundle["word_vectorizer"].transform(text),
            bundle["character_vectorizer"].transform(text),
        ),
        format="csr",
    )
    lexical_probabilities = aligned(
        bundle["lexical_classifier"].predict_proba(lexical_features),
        bundle["lexical_classifier"].classes_,
    )

    encoder = SentenceTransformer(
        str(config["embedding_model"]),
        revision=str(config["embedding_model_revision"]),
        device="cpu",
    )
    embeddings = encoder.encode(
        text,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    semantic_probabilities = aligned(
        bundle["semantic_classifier"].predict_proba(csr_matrix(embeddings)),
        bundle["semantic_classifier"].classes_,
    )
    probabilities = (
        float(config["lexical_weight"]) * lexical_probabilities
        + float(config["semantic_weight"]) * semantic_probabilities
    )

    hate_index = LABELS.index(HATE_LABEL)
    predicted_index = probabilities.argmax(axis=1)
    top_score = probabilities.max(axis=1)
    ordered = np.sort(probabilities, axis=1)
    margin = ordered[:, -1] - ordered[:, -2]

    source_names = ("Civil Comments", "HateXplain")
    best: dict | None = None
    for threshold in np.arange(0.35, 0.991, 0.01):
        for minimum_margin in np.arange(0.0, 0.501, 0.02):
            accepted = (
                (predicted_index == hate_index)
                & (top_score >= threshold)
                & (margin >= minimum_margin)
            )
            accepted_count = int(accepted.sum())
            if accepted_count < MINIMUM_TOTAL_ACCEPTED:
                continue

            correct = accepted & (truth == HATE_LABEL)
            correct_count = int(correct.sum())
            precision = safe_divide(correct_count, accepted_count)
            if precision < TARGET_OVERALL_PRECISION:
                continue

            source_metrics: dict[str, dict[str, float | int]] = {}
            source_gate = True
            for source in source_names:
                source_accepted = accepted & (sources == source)
                source_count = int(source_accepted.sum())
                source_correct = int(
                    (source_accepted & (truth == HATE_LABEL)).sum()
                )
                source_precision = safe_divide(source_correct, source_count)
                source_metrics[source] = {
                    "accepted": source_count,
                    "correct": source_correct,
                    "precision": round(source_precision, 4),
                }
                if (
                    source_count < MINIMUM_ACCEPTED_PER_SOURCE
                    or source_precision < TARGET_SOURCE_PRECISION
                ):
                    source_gate = False
            if not source_gate:
                continue

            actual_hate = truth == HATE_LABEL
            hate_support = int(actual_hate.sum())
            recall = safe_divide(correct_count, hate_support)
            non_hate = truth != HATE_LABEL
            non_hate_support = int(non_hate.sum())
            false_positives = int((accepted & non_hate).sum())
            specificity = 1.0 - safe_divide(false_positives, non_hate_support)
            if specificity < TARGET_NON_HATE_SPECIFICITY:
                continue

            candidate = {
                "enabled": True,
                "probability_threshold": round(float(threshold), 2),
                "minimum_margin": round(float(minimum_margin), 2),
                "accepted": accepted_count,
                "correct": correct_count,
                "false_positives": false_positives,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "non_hate_specificity": round(specificity, 4),
                "source_metrics": source_metrics,
            }
            rank = (recall, accepted_count, precision, specificity)
            if best is None or rank > best["rank"]:
                best = {"rank": rank, "policy": candidate}

    if best is None:
        policy = {
            "enabled": False,
            "probability_threshold": 1.01,
            "minimum_margin": 1.01,
            "accepted": 0,
            "correct": 0,
            "false_positives": 0,
            "precision": 0.0,
            "recall": 0.0,
            "non_hate_specificity": 0.0,
            "source_metrics": {},
            "reason": "No validation threshold satisfied every safety gate.",
        }
    else:
        policy = best["policy"]

    passed = bool(policy["enabled"])
    calibration = {
        "candidate": "hate-speech-v2-rc2-development",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "active_output_category": "Hate Speech & Discrimination",
        "abusive_words_behavior": "No hate override; use the validated abusive-word specialist.",
        "safe_or_other_behavior": "No hate override.",
        "uncertain_behavior": "No automatic category replacement; refer ambiguous cases to human review.",
        "hate_policy": policy,
        "gates": {
            "minimum_overall_precision": TARGET_OVERALL_PRECISION,
            "minimum_per_source_precision": TARGET_SOURCE_PRECISION,
            "minimum_non_hate_specificity": TARGET_NON_HATE_SPECIFICITY,
            "minimum_total_accepted": MINIMUM_TOTAL_ACCEPTED,
            "minimum_accepted_per_source": MINIMUM_ACCEPTED_PER_SOURCE,
        },
        "passed_selective_development_gate": passed,
        "test_splits_opened": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CALIBRATION_PATH.write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH RC2 SELECTIVE CALIBRATION")
    print("=" * 60)
    print(f"Enabled: {policy['enabled']}")
    print(f"Probability threshold: {policy['probability_threshold']}")
    print(f"Minimum margin: {policy['minimum_margin']}")
    print(f"Accepted hate decisions: {policy['accepted']}")
    print(f"Precision: {float(policy['precision']) * 100:.2f}%")
    print(f"Recall: {float(policy['recall']) * 100:.2f}%")
    print(
        "Non-hate specificity: "
        f"{float(policy['non_hate_specificity']) * 100:.2f}%"
    )
    print()
    print("SOURCE RESULTS")
    print("-" * 60)
    for source, metrics in policy.get("source_metrics", {}).items():
        print(
            f"{source}: accepted {metrics['accepted']} | "
            f"precision {float(metrics['precision']) * 100:.2f}%"
        )
    print()
    print(f"Passed selective development gate: {passed}")
    print(f"Calibration: {CALIBRATION_PATH}")
    print("The Civil Comments and HateXplain test splits were not opened.")
    print("Only Hate Speech may become an active output from this candidate.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
