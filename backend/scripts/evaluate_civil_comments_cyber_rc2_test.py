from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sentence_transformers import SentenceTransformer
from sklearn.metrics import accuracy_score, classification_report


REPO_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    REPO_ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "cyberbullying-v2-rc2"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
ARTIFACT_PATH = CANDIDATE_DIRECTORY / "classifier_bundle.joblib"
CONFIG_PATH = CANDIDATE_DIRECTORY / "development_config.json"
TEST_PATH = (
    REPO_ROOT
    / "datasets"
    / "public"
    / "civil_comments_cyber"
    / "test.csv"
)
REPORT_DIRECTORY = (
    REPO_ROOT
    / "reports"
    / "evaluation"
    / "cyberbullying"
    / "v2_rc2_independent_test"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"

LABELS = ("targeted_threat", "abusive_words", "safe_or_other")
MINIMUM_SELECTIVE_PRECISION = 0.85
MINIMUM_SELECTIVE_ACCURACY = 0.85
MINIMUM_COVERAGE = 0.50


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def aligned(probabilities: np.ndarray, classes: np.ndarray) -> np.ndarray:
    indexes = [list(classes).index(label) for label in LABELS]
    return probabilities[:, indexes]


def load_and_verify_candidate() -> tuple[dict[str, object], dict[str, object]]:
    for path in (MANIFEST_PATH, ARTIFACT_PATH, CONFIG_PATH, TEST_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required frozen RC2 file was not found: {path}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if manifest.get("candidate") != "cyberbullying-v2-rc2":
        raise RuntimeError("Unexpected candidate manifest.")
    if manifest.get("independently_validated") is not False:
        raise RuntimeError("The manifest no longer represents an untested RC2 candidate.")
    if manifest.get("test_contract", {}).get("test_split_used_before_freeze") is not False:
        raise RuntimeError("The test split was used before freeze; evaluation is invalid.")

    expected_frozen = manifest.get("frozen_file_hashes", {})
    expected_dataset = manifest.get("dataset_hashes", {})
    actual_artifact_hash = sha256_file(ARTIFACT_PATH)
    actual_config_hash = sha256_file(CONFIG_PATH)
    actual_test_hash = sha256_file(TEST_PATH)
    if actual_artifact_hash != expected_frozen.get("classifier_bundle.joblib"):
        raise RuntimeError("Frozen classifier artifact hash mismatch.")
    if actual_config_hash != expected_frozen.get("development_config.json"):
        raise RuntimeError("Frozen development config hash mismatch.")
    if actual_test_hash != expected_dataset.get("test.csv"):
        raise RuntimeError("Reserved Civil Comments test split hash mismatch.")

    if tuple(config.get("labels", ())) != LABELS:
        raise RuntimeError("Frozen classifier label order is unexpected.")
    if config.get("test_split_read") is not False:
        raise RuntimeError("Frozen config indicates that test data was previously read.")
    return manifest, config


def print_existing_report() -> None:
    existing = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    print("The independent RC2 test was already completed.")
    print(f"Passed readiness gate: {existing['passed_independent_readiness_gate']}")
    print(f"Report: {REPORT_PATH}")


def main() -> None:
    if REPORT_PATH.exists():
        print_existing_report()
        return

    manifest, config = load_and_verify_candidate()
    with TEST_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("The reserved Civil Comments test split is empty.")

    required_columns = {"record_id", "text", "label", "source_text_sha256"}
    if not required_columns.issubset(rows[0]):
        raise RuntimeError("The reserved test split has an unexpected schema.")

    truth = np.array([row["label"] for row in rows])
    if set(truth) != set(LABELS):
        raise RuntimeError("The reserved test split does not contain all expected labels.")
    text = [row["text"] for row in rows]

    print("Loading the frozen Civil Comments RC2 classifier...")
    bundle = joblib.load(ARTIFACT_PATH)
    word_features = bundle["word_vectorizer"].transform(text)
    character_features = bundle["char_vectorizer"].transform(text)
    lexical_features = hstack(
        (word_features, character_features),
        format="csr",
    )
    lexical_probabilities = aligned(
        bundle["lexical_classifier"].predict_proba(lexical_features),
        bundle["lexical_classifier"].classes_,
    )

    print("Loading the frozen semantic encoder revision...")
    encoder = SentenceTransformer(
        str(manifest["embedding_model"]),
        revision=str(manifest["embedding_model_revision"]),
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

    lexical_weight = float(manifest["lexical_weight"])
    semantic_weight = float(manifest["semantic_weight"])
    probabilities = (
        lexical_weight * lexical_probabilities
        + semantic_weight * semantic_probabilities
    )
    prediction_indexes = probabilities.argmax(axis=1)
    predictions = np.array([LABELS[index] for index in prediction_indexes])
    confidence = probabilities.max(axis=1)

    raw_accuracy = float(accuracy_score(truth, predictions))
    raw_report = classification_report(
        truth,
        predictions,
        labels=list(LABELS),
        output_dict=True,
        zero_division=0,
    )

    thresholds = manifest["selective_thresholds"]
    accepted = np.array(
        [
            bool(thresholds[label]["enabled"])
            and float(score) >= float(thresholds[label]["threshold"])
            for label, score in zip(predictions, confidence, strict=True)
        ]
    )
    accepted_count = int(accepted.sum())
    correct_accepted = int((truth[accepted] == predictions[accepted]).sum())
    selective_accuracy = (
        correct_accepted / accepted_count if accepted_count else 0.0
    )
    coverage = accepted_count / len(rows)

    per_label: dict[str, dict[str, float | int]] = {}
    every_label_precision_passed = True
    for label in LABELS:
        label_accepted = accepted & (predictions == label)
        accepted_for_label = int(label_accepted.sum())
        correct_for_label = int((truth[label_accepted] == label).sum())
        support = int((truth == label).sum())
        precision = (
            correct_for_label / accepted_for_label if accepted_for_label else 0.0
        )
        selective_recall = correct_for_label / support if support else 0.0
        every_label_precision_passed = bool(
            every_label_precision_passed
            and accepted_for_label > 0
            and precision >= MINIMUM_SELECTIVE_PRECISION
        )
        per_label[label] = {
            "support": support,
            "accepted": accepted_for_label,
            "correct_accepted": correct_for_label,
            "accepted_precision": round(precision, 4),
            "selective_recall": round(selective_recall, 4),
            "threshold": float(thresholds[label]["threshold"]),
        }

    passed = bool(
        selective_accuracy >= MINIMUM_SELECTIVE_ACCURACY
        and coverage >= MINIMUM_COVERAGE
        and every_label_precision_passed
    )
    category_mapping = {
        "targeted_threat": "Cyberbullying & Harassment",
        "abusive_words": "Abusive Words",
        "safe_or_other": "No boundary override",
        "uncertain": "Uncertain / Refer to human review",
    }
    report = {
        "candidate": manifest["candidate"],
        "candidate_frozen_at_utc": manifest["frozen_at_utc"],
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "external_dataset": manifest["external_dataset"],
        "external_dataset_license": manifest["external_dataset_license"],
        "test_split_sha256": sha256_file(TEST_PATH),
        "records": len(rows),
        "raw_accuracy": round(raw_accuracy, 4),
        "raw_macro_f1": round(float(raw_report["macro avg"]["f1-score"]), 4),
        "raw_classification_report": raw_report,
        "selective_accuracy": round(selective_accuracy, 4),
        "coverage": round(coverage, 4),
        "accepted_records": accepted_count,
        "uncertain_records": len(rows) - accepted_count,
        "per_label_selective_results": per_label,
        "category_mapping": category_mapping,
        "minimum_selective_precision": MINIMUM_SELECTIVE_PRECISION,
        "minimum_selective_accuracy": MINIMUM_SELECTIVE_ACCURACY,
        "minimum_coverage": MINIMUM_COVERAGE,
        "passed_independent_readiness_gate": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "raw_text_stored_in_report": False,
        "record_level_predictions_stored": False,
        "frozen_candidate_modified": False,
        "limitations": [
            "Targeted-threat evidence can support Cyberbullying & Harassment, but this message-level dataset cannot validate repetition, campaigns, or continued unwanted contact.",
            "Passing this component gate does not make the full application production ready.",
            "No automatic enforcement is permitted by this candidate evaluation.",
        ],
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("CIVIL COMMENTS CYBER/ABUSIVE RC2 INDEPENDENT TEST")
    print("=" * 60)
    print(f"Records: {len(rows)}")
    print(f"Raw accuracy: {raw_accuracy * 100:.2f}%")
    print(f"Raw macro F1: {float(raw_report['macro avg']['f1-score']) * 100:.2f}%")
    print(f"Selective accuracy: {selective_accuracy * 100:.2f}%")
    print(f"Coverage: {coverage * 100:.2f}%")
    print(f"Accepted records: {accepted_count}")
    print(f"Uncertain records: {len(rows) - accepted_count}")
    print()
    print("SELECTIVE LABEL RESULTS")
    print("-" * 60)
    for label in LABELS:
        values = per_label[label]
        print(label)
        print(f"  Support: {values['support']}")
        print(f"  Accepted: {values['accepted']}")
        print(f"  Accepted precision: {float(values['accepted_precision']) * 100:.2f}%")
        print(f"  Selective recall: {float(values['selective_recall']) * 100:.2f}%")
    print()
    print(f"Passed independent readiness gate: {passed}")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("Frozen RC2 modified: False")
    print(f"Report: {REPORT_PATH}")
    print("Individual predictions and raw test text were not stored.")
    print("This component result is not overall product accuracy.")


if __name__ == "__main__":
    main()
