from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[2]
BASE_CANDIDATE_NAME = "religiously-offensive-v4-rc3"
BASE_CANDIDATE = (
    ROOT / "backend" / "storage" / "candidates" / BASE_CANDIDATE_NAME
)
BASE_MANIFEST = BASE_CANDIDATE / "manifest.json"
BASE_VERDICT = BASE_CANDIDATE / "independent_evaluation_verdict.json"
BASE_MODEL = BASE_CANDIDATE / "model" / "classifier.joblib"
BASE_CONFIG = BASE_CANDIDATE / "model" / "config.json"
VALIDATION_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v4_rc3"
    / "validation.csv"
)

CANDIDATE = "religiously-offensive-v5-rc4-development"
MODEL_DIRECTORY = (
    ROOT / "backend" / "storage" / "models" / "religiously_offensive_v5_rc4"
)
MODEL_ARTIFACT = MODEL_DIRECTORY / "classifier.joblib"
MODEL_CONFIG = MODEL_DIRECTORY / "config.json"
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v5_rc4_guard_development"
)
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"

RELIGIOUS_LABEL = "religiously_offensive"
NO_OVERRIDE = "no_religious_override"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required RC4 development file is missing: {path}")


def verify_base() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path in (
        BASE_MANIFEST,
        BASE_VERDICT,
        BASE_MODEL,
        BASE_CONFIG,
        VALIDATION_DATASET,
    ):
        require_file(path)
    manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    verdict = json.loads(BASE_VERDICT.read_text(encoding="utf-8"))
    config = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE_CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC3 base manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("The RC3 base model did not pass development.")
    if verdict.get("candidate") != BASE_CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC3 base verdict.")
    if verdict.get("passed_independent_readiness_gate") is not False:
        raise RuntimeError("RC4 guard development is only permitted after RC3 failure.")
    if verdict.get("eligible_for_guarded_live_integration") is not False:
        raise RuntimeError("The failed RC3 candidate must remain disconnected.")
    if verdict.get("holdout_may_modify_rc3") is not False:
        raise RuntimeError("The RC3 holdout contract is invalid.")
    for artifact in manifest.get("artifacts", []):
        path = BASE_CANDIDATE / str(artifact["relative_path"])
        require_file(path)
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen RC3 artifact hash mismatch: {path.name}")
    return manifest, verdict, config


def load_validation() -> list[dict[str, str]]:
    with VALIDATION_DATASET.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("The RC3 validation dataset is empty.")
    return rows


def predict_binary(
    probabilities: np.ndarray,
    classes: np.ndarray,
    threshold: float,
    margin: float,
) -> np.ndarray:
    religious_index = int(np.where(classes == RELIGIOUS_LABEL)[0][0])
    results: list[str] = []
    for scores in probabilities:
        religious_score = float(scores[religious_index])
        other_score = float(np.max(np.delete(scores, religious_index)))
        score_margin = religious_score - other_score
        results.append(
            RELIGIOUS_LABEL
            if religious_score >= threshold and score_margin >= margin
            else NO_OVERRIDE
        )
    return np.array(results)


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def metrics(truth: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    positive = truth == RELIGIOUS_LABEL
    predicted_positive = predicted == RELIGIOUS_LABEL
    tp = int(np.sum(positive & predicted_positive))
    tn = int(np.sum(~positive & ~predicted_positive))
    fp = int(np.sum(~positive & predicted_positive))
    fn = int(np.sum(positive & ~predicted_positive))
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    specificity = safe_divide(tn, tn + fp)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    return {
        "accuracy": round(safe_divide(tp + tn, len(truth)), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1": round(f1, 4),
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
    }


def choose_policy(
    truth: np.ndarray,
    probabilities: np.ndarray,
    classes: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray]:
    best: tuple[tuple[float, ...], dict[str, Any], np.ndarray] | None = None
    for threshold in np.arange(0.30, 0.96, 0.01):
        for margin in np.arange(0.00, 0.51, 0.01):
            predicted = predict_binary(
                probabilities,
                classes,
                float(threshold),
                float(margin),
            )
            result = metrics(truth, predicted)
            qualifies = bool(
                result["accuracy"] >= 0.95
                and result["precision"] >= 0.95
                and result["recall"] >= 0.92
                and result["specificity"] >= 0.98
                and result["false_positives"] == 0
            )
            policy = {
                "enabled": qualifies,
                "religious_probability_threshold": round(float(threshold), 2),
                "minimum_religious_margin": round(float(margin), 2),
                **result,
            }
            # Among passing policies, prefer the most conservative threshold/margin
            # while retaining the locked minimum recall.
            rank = (
                float(qualifies),
                float(result["precision"]),
                float(result["specificity"]),
                float(threshold + margin),
                float(result["recall"]),
                float(result["f1"]),
            )
            if best is None or rank > best[0]:
                best = (rank, policy, predicted)
    if best is None:
        raise RuntimeError("Unable to calibrate an RC4 religious-only guard.")
    return best[1], best[2]


def main() -> None:
    manifest, _, base_config = verify_base()
    rows = load_validation()
    classifier = joblib.load(BASE_MODEL)
    encoder = SentenceTransformer(
        str(base_config["embedding_model"]),
        revision=str(base_config["embedding_model_revision"]),
        device="cpu",
    )
    texts = [row["text"] for row in rows]
    truth = np.array(
        [
            RELIGIOUS_LABEL
            if row["label"] == RELIGIOUS_LABEL
            else NO_OVERRIDE
            for row in rows
        ]
    )
    embeddings = encoder.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    probabilities = classifier.predict_proba(embeddings)
    policy, predicted = choose_policy(truth, probabilities, classifier.classes_)

    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped_indices[row["family"]].append(index)
    family_results: dict[str, dict[str, Any]] = {}
    for family, indices in sorted(grouped_indices.items()):
        correct = sum(predicted[index] == truth[index] for index in indices)
        family_results[family] = {
            "records": len(indices),
            "correct": int(correct),
            "accuracy": round(correct / len(indices), 4),
        }
    minimum_family_accuracy = min(
        result["accuracy"] for result in family_results.values()
    )
    neutral_indices = [
        index
        for index, row in enumerate(rows)
        if row["family"] == "neutral_religious_validation"
    ]
    neutral_safe_rate = safe_divide(
        sum(predicted[index] == NO_OVERRIDE for index in neutral_indices),
        len(neutral_indices),
    )
    category_mix_failures = int(policy["false_positives"])
    passed = bool(
        policy["enabled"]
        and minimum_family_accuracy >= 0.80
        and neutral_safe_rate == 1.0
        and category_mix_failures == 0
    )
    policy["passed_development_gate"] = passed
    policy["minimum_family_accuracy"] = minimum_family_accuracy
    policy["neutral_religious_safe_rate"] = round(neutral_safe_rate, 4)
    policy["category_mix_failures"] = category_mix_failures

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BASE_MODEL, MODEL_ARTIFACT)
    config = {
        "candidate": CANDIDATE,
        "base_candidate": BASE_CANDIDATE_NAME,
        "base_classifier_sha256": sha256_file(BASE_MODEL),
        "embedding_model": base_config["embedding_model"],
        "embedding_model_revision": base_config["embedding_model_revision"],
        "classifier_classes": [str(label) for label in classifier.classes_],
        "religious_only_guard_policy": policy,
        "permitted_active_output": "Religiously Offensive Content only",
        "all_nonreligious_model_labels": "No religious-category override",
        "protected_follower_owner": "Hate Speech & Discrimination V7",
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "connected_to_live_moderation": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    MODEL_CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    report = {
        "candidate": CANDIDATE,
        "base_candidate": BASE_CANDIDATE_NAME,
        "validation_records": len(rows),
        "validation_dataset_sha256": manifest["datasets"]["validation"]["sha256"],
        "policy": policy,
        "validation_family_results": family_results,
        "passed_development_gate": passed,
        "rc3_holdout_report_predictions_or_cases_used": False,
        "rc3_verdict_status_read_only": True,
        "classifier_retrained": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "evidence_limit": "Development calibration evidence, not independent accuracy.",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("RELIGIOUSLY OFFENSIVE CONTENT V5 RC4 GUARDED DEVELOPMENT")
    print("=" * 60)
    print(f"Validation records: {len(rows)}")
    print(f"Accuracy: {policy['accuracy'] * 100:.2f}%")
    print(f"Religious precision: {policy['precision'] * 100:.2f}%")
    print(f"Religious recall: {policy['recall'] * 100:.2f}%")
    print(f"Religious F1: {policy['f1'] * 100:.2f}%")
    print(f"Nonreligious specificity: {policy['specificity'] * 100:.2f}%")
    print(f"Probability threshold: {policy['religious_probability_threshold']:.2f}")
    print(f"Minimum religious margin: {policy['minimum_religious_margin']:.2f}")
    print(f"Minimum family accuracy: {minimum_family_accuracy * 100:.2f}%")
    print(f"Neutral-religious safe routing: {neutral_safe_rate * 100:.2f}%")
    print(f"Category-mix failures: {category_mix_failures}")
    print("Follower-boundary output enabled: False")
    print("Follower-boundary owner: Hate Speech & Discrimination V7")
    print()
    print(f"Passed development gate: {passed}")
    print(f"Artifact: {MODEL_ARTIFACT}")
    print(f"Configuration: {MODEL_CONFIG}")
    print(f"Report: {REPORT_PATH}")
    print("RC3 holdout report, predictions, and cases used: False")
    print("Classifier retrained: False")
    print("Live moderation changed: False")
    print("This is development calibration evidence, not independent accuracy.")


if __name__ == "__main__":
    main()

