from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[2]
CIVIL_DIRECTORY = ROOT / "datasets" / "public" / "civil_comments_hate_rc2"
HATEXPLAIN_DIRECTORY = ROOT / "datasets" / "public" / "hatexplain"
MODEL_DIRECTORY = ROOT / "backend" / "storage" / "models" / "hate_speech_v3"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v3_meta_calibration"
)
ARTIFACT_PATH = MODEL_DIRECTORY / "dual_head_bundle.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "development_config.json"
CALIBRATION_PATH = MODEL_DIRECTORY / "meta_calibration.json"
REPORT_PATH = REPORT_DIRECTORY / "calibration_report.json"

TARGET_OVERALL_PRECISION = 0.90
TARGET_SOURCE_PRECISION = 0.85
TARGET_SPECIFICITY = 0.95
MINIMUM_RECALL = 0.15
MINIMUM_ACCEPTED = 30
MINIMUM_CIVIL_ACCEPTED = 10
MINIMUM_HATEXPLAIN_ACCEPTED = 30

HATEXPLAIN_MAPPING = {
    "Hate Speech & Discrimination": True,
    "Abusive Words": False,
    "Normal/Ignore": False,
}


def load_validation() -> list[dict[str, Any]]:
    civil_path = CIVIL_DIRECTORY / "validation.csv"
    hatexplain_path = HATEXPLAIN_DIRECTORY / "validation.csv"
    for path in (civil_path, hatexplain_path):
        if not path.is_file():
            raise FileNotFoundError(f"Validation split was not found: {path}")

    rows: list[dict[str, Any]] = []
    with civil_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            label = str(row.get("label", ""))
            if text and label in {"hate_speech", "abusive_words", "safe_or_other"}:
                rows.append(
                    {
                        "text": text,
                        "is_hate": label == "hate_speech",
                        "source": "Civil Comments",
                    }
                )

    with hatexplain_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            category = str(row.get("category", ""))
            if text and category in HATEXPLAIN_MAPPING:
                rows.append(
                    {
                        "text": text,
                        "is_hate": HATEXPLAIN_MAPPING[category],
                        "source": "HateXplain",
                    }
                )
    if not rows:
        raise RuntimeError("No validation records were loaded.")
    return rows


def positive_probability(classifier: Any, features: Any) -> np.ndarray:
    classes = list(classifier.classes_)
    return classifier.predict_proba(features)[:, classes.index(1)]


def head_probability(
    bundle: dict[str, Any],
    policy: dict[str, Any],
    text: list[str],
    embeddings: np.ndarray,
) -> np.ndarray:
    lexical_features = hstack(
        (
            bundle["word_vectorizer"].transform(text),
            bundle["character_vectorizer"].transform(text),
        ),
        format="csr",
    )
    lexical = positive_probability(bundle["lexical_classifier"], lexical_features)
    semantic = positive_probability(
        bundle["semantic_classifier"],
        csr_matrix(embeddings),
    )
    return (
        float(policy["lexical_weight"]) * lexical
        + float(policy["semantic_weight"]) * semantic
    )


def evaluate(
    accepted: np.ndarray,
    truth: np.ndarray,
    sources: np.ndarray,
) -> dict[str, Any] | None:
    accepted_count = int(accepted.sum())
    if accepted_count < MINIMUM_ACCEPTED:
        return None
    correct = int((accepted & truth).sum())
    precision = correct / accepted_count
    actual_hate = int(truth.sum())
    recall = correct / actual_hate if actual_hate else 0.0
    non_hate = ~truth
    non_hate_count = int(non_hate.sum())
    false_positives = int((accepted & non_hate).sum())
    specificity = 1.0 - (
        false_positives / non_hate_count if non_hate_count else 0.0
    )
    if (
        precision < TARGET_OVERALL_PRECISION
        or recall < MINIMUM_RECALL
        or specificity < TARGET_SPECIFICITY
    ):
        return None

    source_metrics: dict[str, dict[str, float | int]] = {}
    for source, minimum in (
        ("Civil Comments", MINIMUM_CIVIL_ACCEPTED),
        ("HateXplain", MINIMUM_HATEXPLAIN_ACCEPTED),
    ):
        selected = accepted & (sources == source)
        count = int(selected.sum())
        source_correct = int((selected & truth).sum())
        source_precision = source_correct / count if count else 0.0
        if count < minimum or source_precision < TARGET_SOURCE_PRECISION:
            return None
        source_metrics[source] = {
            "accepted": count,
            "correct": source_correct,
            "precision": round(source_precision, 4),
        }

    return {
        "accepted": accepted_count,
        "correct": correct,
        "false_positives": false_positives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "source_metrics": source_metrics,
    }


def consider(
    best: tuple[tuple[float, int, float, float], dict[str, Any]] | None,
    policy: dict[str, Any],
    metrics: dict[str, Any] | None,
) -> tuple[tuple[float, int, float, float], dict[str, Any]] | None:
    if metrics is None:
        return best
    candidate = {**policy, **metrics}
    rank = (
        float(metrics["recall"]),
        int(metrics["accepted"]),
        float(metrics["precision"]),
        float(metrics["specificity"]),
    )
    if best is None or rank > best[0]:
        return rank, candidate
    return best


def main() -> None:
    for path in (ARTIFACT_PATH, CONFIG_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required V3 artifact was not found: {path}")

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("test_splits_opened") is not False:
        raise RuntimeError("The V3 development test contract is invalid.")

    rows = load_validation()
    text = [row["text"] for row in rows]
    truth = np.array([bool(row["is_hate"]) for row in rows])
    sources = np.array([str(row["source"]) for row in rows])

    print("Loading the V3 dual-head development candidate...")
    bundle = joblib.load(ARTIFACT_PATH)
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
    civil_probability = head_probability(
        bundle["civil_head"],
        config["civil_policy"],
        text,
        embeddings,
    )
    hatexplain_probability = head_probability(
        bundle["hatexplain_head"],
        config["hatexplain_policy"],
        text,
        embeddings,
    )

    best: tuple[tuple[float, int, float, float], dict[str, Any]] | None = None
    thresholds = np.arange(0.30, 0.991, 0.02)

    # Independent two-threshold agreement.
    for civil_threshold in thresholds:
        for hatexplain_threshold in thresholds:
            accepted = (
                (civil_probability >= civil_threshold)
                & (hatexplain_probability >= hatexplain_threshold)
            )
            metrics = evaluate(accepted, truth, sources)
            best = consider(
                best,
                {
                    "method": "dual_threshold_agreement",
                    "civil_threshold": round(float(civil_threshold), 2),
                    "hatexplain_threshold": round(float(hatexplain_threshold), 2),
                },
                metrics,
            )

    # Weighted score can retain cross-source evidence when one head is more
    # cautious, but it remains subject to every source and specificity gate.
    for civil_weight in np.arange(0.10, 0.91, 0.05):
        score = (
            civil_weight * civil_probability
            + (1.0 - civil_weight) * hatexplain_probability
        )
        for threshold in thresholds:
            accepted = score >= threshold
            metrics = evaluate(accepted, truth, sources)
            best = consider(
                best,
                {
                    "method": "weighted_probability",
                    "civil_weight": round(float(civil_weight), 2),
                    "hatexplain_weight": round(float(1.0 - civil_weight), 2),
                    "threshold": round(float(threshold), 2),
                },
                metrics,
            )

    if best is None:
        policy: dict[str, Any] = {
            "enabled": False,
            "method": "none",
            "accepted": 0,
            "correct": 0,
            "false_positives": 0,
            "precision": 0.0,
            "recall": 0.0,
            "specificity": 0.0,
            "source_metrics": {},
            "reason": "No meta-policy satisfied every validation safety gate.",
        }
    else:
        policy = {"enabled": True, **best[1]}

    passed = bool(policy["enabled"])
    report = {
        "candidate": "hate-speech-v3-dual-head-development",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "active_output_category": "Hate Speech & Discrimination",
        "meta_policy": policy,
        "gates": {
            "minimum_overall_precision": TARGET_OVERALL_PRECISION,
            "minimum_per_source_precision": TARGET_SOURCE_PRECISION,
            "minimum_specificity": TARGET_SPECIFICITY,
            "minimum_recall": MINIMUM_RECALL,
            "minimum_accepted": MINIMUM_ACCEPTED,
            "minimum_civil_accepted": MINIMUM_CIVIL_ACCEPTED,
            "minimum_hatexplain_accepted": MINIMUM_HATEXPLAIN_ACCEPTED,
        },
        "passed_meta_calibration_gate": passed,
        "test_splits_opened": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "other_category_behavior": "No hate override",
    }
    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CALIBRATION_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH V3 META-CALIBRATION RESULTS")
    print("=" * 60)
    print(f"Enabled: {policy['enabled']}")
    print(f"Method: {policy['method']}")
    if policy["enabled"]:
        if policy["method"] == "dual_threshold_agreement":
            print(f"Civil threshold: {policy['civil_threshold']}")
            print(f"HateXplain threshold: {policy['hatexplain_threshold']}")
        else:
            print(f"Civil weight: {policy['civil_weight']}")
            print(f"HateXplain weight: {policy['hatexplain_weight']}")
            print(f"Threshold: {policy['threshold']}")
        print(f"Accepted: {policy['accepted']}")
        print(f"Precision: {float(policy['precision']) * 100:.2f}%")
        print(f"Recall: {float(policy['recall']) * 100:.2f}%")
        print(f"Non-hate specificity: {float(policy['specificity']) * 100:.2f}%")
        for source, metrics in policy["source_metrics"].items():
            print(
                f"{source}: accepted {metrics['accepted']} | "
                f"precision {float(metrics['precision']) * 100:.2f}%"
            )
    print()
    print(f"Passed meta-calibration gate: {passed}")
    print(f"Calibration: {CALIBRATION_PATH}")
    print("Neither test split was opened.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
