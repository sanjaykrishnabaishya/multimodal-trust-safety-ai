from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


CANDIDATE = "hate-speech-v3-dual-head-development"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
ROOT = Path(__file__).resolve().parents[2]
CIVIL_DIRECTORY = ROOT / "datasets" / "public" / "civil_comments_hate_rc2"
HATEXPLAIN_DIRECTORY = ROOT / "datasets" / "public" / "hatexplain"
MODEL_DIRECTORY = ROOT / "backend" / "storage" / "models" / "hate_speech_v3"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v3_dual_head_development"
)
ARTIFACT_PATH = MODEL_DIRECTORY / "dual_head_bundle.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "development_config.json"
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"

TARGET_NATIVE_PRECISION = 0.90
TARGET_CONSENSUS_PRECISION = 0.90
TARGET_SOURCE_PRECISION = 0.85
TARGET_SPECIFICITY = 0.95
MINIMUM_CONSENSUS_RECALL = 0.20

HATEXPLAIN_MAPPING = {
    "Hate Speech & Discrimination": "hate_speech",
    "Abusive Words": "no_hate",
    "Normal/Ignore": "no_hate",
}


def normalized_hash(text: str) -> str:
    value = " ".join(str(text or "").casefold().split())
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_civil(split: str) -> list[dict[str, str]]:
    path = CIVIL_DIRECTORY / f"{split}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Civil Comments {split} split not found: {path}")
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            source_label = str(row.get("label", ""))
            if not text or source_label not in {
                "hate_speech",
                "abusive_words",
                "safe_or_other",
            }:
                continue
            rows.append(
                {
                    "text": text,
                    "label": "hate_speech" if source_label == "hate_speech" else "no_hate",
                    "source": "Civil Comments",
                    "hash": str(row.get("source_text_sha256", "")) or normalized_hash(text),
                }
            )
    return rows


def load_hatexplain(split: str) -> list[dict[str, str]]:
    path = HATEXPLAIN_DIRECTORY / f"{split}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"HateXplain {split} split not found: {path}")
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            label = HATEXPLAIN_MAPPING.get(str(row.get("category", "")))
            if not text or not label:
                continue
            rows.append(
                {
                    "text": text,
                    "label": label,
                    "source": "HateXplain",
                    "hash": normalized_hash(text),
                }
            )
    return rows


def deduplicate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if row["hash"] in seen:
            continue
        seen.add(row["hash"])
        selected.append(row)
    return selected


def build_lexical_features(
    train_text: list[str],
    validation_text: list[str],
) -> tuple[TfidfVectorizer, TfidfVectorizer, Any, Any]:
    word = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        ngram_range=(1, 2),
        min_df=2,
        max_features=55_000,
    )
    character = TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        ngram_range=(3, 5),
        min_df=2,
        max_features=75_000,
    )
    train_features = hstack(
        (word.fit_transform(train_text), character.fit_transform(train_text)),
        format="csr",
    )
    validation_features = hstack(
        (word.transform(validation_text), character.transform(validation_text)),
        format="csr",
    )
    return word, character, train_features, validation_features


def positive_probability(classifier: LogisticRegression, features: Any) -> np.ndarray:
    classes = list(classifier.classes_)
    return classifier.predict_proba(features)[:, classes.index(1)]


def precision_recall(
    accepted: np.ndarray,
    truth: np.ndarray,
) -> tuple[float, float, int, int]:
    accepted_count = int(accepted.sum())
    correct = int((accepted & truth).sum())
    support = int(truth.sum())
    precision = correct / accepted_count if accepted_count else 0.0
    recall = correct / support if support else 0.0
    return precision, recall, accepted_count, correct


def select_native_policy(
    lexical_probability: np.ndarray,
    semantic_probability: np.ndarray,
    truth: np.ndarray,
    minimum_accepted: int,
) -> dict[str, Any]:
    best: tuple[tuple[float, float, int], dict[str, Any]] | None = None
    for lexical_weight in np.arange(0.0, 1.01, 0.05):
        probability = (
            lexical_weight * lexical_probability
            + (1.0 - lexical_weight) * semantic_probability
        )
        for threshold in np.arange(0.50, 0.991, 0.01):
            accepted = probability >= threshold
            precision, recall, count, correct = precision_recall(accepted, truth)
            if count < minimum_accepted or precision < TARGET_NATIVE_PRECISION:
                continue
            policy = {
                "enabled": True,
                "lexical_weight": round(float(lexical_weight), 2),
                "semantic_weight": round(float(1.0 - lexical_weight), 2),
                "threshold": round(float(threshold), 2),
                "accepted": count,
                "correct": correct,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
            }
            rank = (recall, precision, count)
            if best is None or rank > best[0]:
                best = (rank, policy)
    if best:
        return best[1]
    return {
        "enabled": False,
        "lexical_weight": 0.5,
        "semantic_weight": 0.5,
        "threshold": 1.01,
        "accepted": 0,
        "correct": 0,
        "precision": 0.0,
        "recall": 0.0,
    }


def train_head(
    *,
    name: str,
    train_rows: list[dict[str, str]],
    native_validation_rows: list[dict[str, str]],
    train_embeddings: np.ndarray,
    native_validation_embeddings: np.ndarray,
    minimum_accepted: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    train_text = [row["text"] for row in train_rows]
    validation_text = [row["text"] for row in native_validation_rows]
    y_train = np.array([1 if row["label"] == "hate_speech" else 0 for row in train_rows])
    y_validation = np.array(
        [row["label"] == "hate_speech" for row in native_validation_rows]
    )

    print(f"Training {name} lexical head...")
    word, character, train_features, validation_features = build_lexical_features(
        train_text,
        validation_text,
    )
    lexical_classifier = LogisticRegression(
        C=4.0,
        class_weight="balanced",
        max_iter=4_000,
        random_state=42,
    )
    lexical_classifier.fit(train_features, y_train)
    lexical_probability = positive_probability(
        lexical_classifier,
        validation_features,
    )

    print(f"Training {name} semantic head...")
    semantic_classifier = LogisticRegression(
        C=2.0,
        class_weight="balanced",
        max_iter=4_000,
        random_state=42,
    )
    semantic_classifier.fit(csr_matrix(train_embeddings), y_train)
    semantic_probability = positive_probability(
        semantic_classifier,
        csr_matrix(native_validation_embeddings),
    )
    policy = select_native_policy(
        lexical_probability,
        semantic_probability,
        y_validation,
        minimum_accepted,
    )
    bundle = {
        "word_vectorizer": word,
        "character_vectorizer": character,
        "lexical_classifier": lexical_classifier,
        "semantic_classifier": semantic_classifier,
    }
    return bundle, policy


def head_probability(
    *,
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


def main() -> None:
    # Only train and validation are loaded. Test files are deliberately untouched.
    civil_train = deduplicate(load_civil("train"))
    civil_validation = deduplicate(load_civil("validation"))
    hatexplain_train = deduplicate(load_hatexplain("train"))
    hatexplain_validation = deduplicate(load_hatexplain("validation"))

    train_hashes = {row["hash"] for row in civil_train + hatexplain_train}
    validation_hashes = {
        row["hash"] for row in civil_validation + hatexplain_validation
    }
    overlap = train_hashes & validation_hashes
    if overlap:
        raise RuntimeError(f"Train/validation leakage detected: {len(overlap)}")

    print("HATE SPEECH V3 DUAL-HEAD DEVELOPMENT")
    print("=" * 60)
    print(f"Civil train: {len(civil_train):,}")
    print(f"Civil validation: {len(civil_validation):,}")
    print(f"HateXplain train: {len(hatexplain_train):,}")
    print(f"HateXplain validation: {len(hatexplain_validation):,}")
    print(f"Train/validation overlap: {len(overlap)}")
    print("Neither test split was opened.")
    print()

    encoder = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")
    print("Encoding Civil Comments train and validation...")
    civil_train_embeddings = encoder.encode(
        [row["text"] for row in civil_train],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    civil_validation_embeddings = encoder.encode(
        [row["text"] for row in civil_validation],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    print("Encoding HateXplain train and validation...")
    hatexplain_train_embeddings = encoder.encode(
        [row["text"] for row in hatexplain_train],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    hatexplain_validation_embeddings = encoder.encode(
        [row["text"] for row in hatexplain_validation],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    civil_bundle, civil_policy = train_head(
        name="Civil Comments",
        train_rows=civil_train,
        native_validation_rows=civil_validation,
        train_embeddings=civil_train_embeddings,
        native_validation_embeddings=civil_validation_embeddings,
        minimum_accepted=15,
    )
    hatexplain_bundle, hatexplain_policy = train_head(
        name="HateXplain",
        train_rows=hatexplain_train,
        native_validation_rows=hatexplain_validation,
        train_embeddings=hatexplain_train_embeddings,
        native_validation_embeddings=hatexplain_validation_embeddings,
        minimum_accepted=50,
    )

    combined_validation = civil_validation + hatexplain_validation
    combined_text = [row["text"] for row in combined_validation]
    combined_embeddings = np.vstack(
        (civil_validation_embeddings, hatexplain_validation_embeddings)
    )
    truth = np.array(
        [row["label"] == "hate_speech" for row in combined_validation]
    )
    sources = np.array([row["source"] for row in combined_validation])

    civil_probability = head_probability(
        bundle=civil_bundle,
        policy=civil_policy,
        text=combined_text,
        embeddings=combined_embeddings,
    )
    hatexplain_probability = head_probability(
        bundle=hatexplain_bundle,
        policy=hatexplain_policy,
        text=combined_text,
        embeddings=combined_embeddings,
    )
    accepted = (
        bool(civil_policy["enabled"])
        & bool(hatexplain_policy["enabled"])
        & (civil_probability >= float(civil_policy["threshold"]))
        & (hatexplain_probability >= float(hatexplain_policy["threshold"]))
    )
    precision, recall, accepted_count, correct = precision_recall(accepted, truth)
    non_hate = ~truth
    false_positives = int((accepted & non_hate).sum())
    specificity = 1.0 - (
        false_positives / int(non_hate.sum()) if int(non_hate.sum()) else 0.0
    )

    source_metrics: dict[str, dict[str, float | int]] = {}
    source_gate = True
    for source in ("Civil Comments", "HateXplain"):
        source_accepted = accepted & (sources == source)
        source_count = int(source_accepted.sum())
        source_correct = int((source_accepted & truth).sum())
        source_precision = source_correct / source_count if source_count else 0.0
        source_metrics[source] = {
            "accepted": source_count,
            "correct": source_correct,
            "precision": round(source_precision, 4),
        }
        if source_count < 10 or source_precision < TARGET_SOURCE_PRECISION:
            source_gate = False

    passed = bool(
        civil_policy["enabled"]
        and hatexplain_policy["enabled"]
        and accepted_count >= 30
        and precision >= TARGET_CONSENSUS_PRECISION
        and recall >= MINIMUM_CONSENSUS_RECALL
        and specificity >= TARGET_SPECIFICITY
        and source_gate
    )

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "civil_head": civil_bundle,
            "hatexplain_head": hatexplain_bundle,
        },
        ARTIFACT_PATH,
        compress=3,
    )
    config = {
        "candidate": CANDIDATE,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "embedding_model": MODEL_NAME,
        "embedding_model_revision": MODEL_REVISION,
        "civil_policy": civil_policy,
        "hatexplain_policy": hatexplain_policy,
        "active_output_category": "Hate Speech & Discrimination",
        "other_output_behavior": "No hate override",
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "test_splits_opened": False,
    }
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        **config,
        "training_counts": {
            "Civil Comments": dict(Counter(row["label"] for row in civil_train)),
            "HateXplain": dict(Counter(row["label"] for row in hatexplain_train)),
        },
        "validation_counts": {
            "Civil Comments": dict(
                Counter(row["label"] for row in civil_validation)
            ),
            "HateXplain": dict(
                Counter(row["label"] for row in hatexplain_validation)
            ),
        },
        "train_validation_overlap": len(overlap),
        "consensus": {
            "accepted": accepted_count,
            "correct": correct,
            "false_positives": false_positives,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "specificity": round(specificity, 4),
            "source_metrics": source_metrics,
        },
        "passed_development_gate": passed,
        "limitations": [
            "This is development validation, not independent accuracy.",
            "The candidate emits only Hate Speech supporting evidence.",
            "Protected-target and counterspeech boundary tests are still required.",
        ],
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH V3 DUAL-HEAD DEVELOPMENT RESULTS")
    print("=" * 60)
    for name, policy in (
        ("Civil Comments head", civil_policy),
        ("HateXplain head", hatexplain_policy),
    ):
        print(name)
        print(f"  Enabled: {policy['enabled']}")
        print(f"  Threshold: {policy['threshold']}")
        print(f"  Precision: {float(policy['precision']) * 100:.2f}%")
        print(f"  Recall: {float(policy['recall']) * 100:.2f}%")
    print()
    print("CONSENSUS RESULTS")
    print("-" * 60)
    print(f"Accepted: {accepted_count}")
    print(f"Precision: {precision * 100:.2f}%")
    print(f"Recall: {recall * 100:.2f}%")
    print(f"Non-hate specificity: {specificity * 100:.2f}%")
    for source, metrics in source_metrics.items():
        print(
            f"{source}: accepted {metrics['accepted']} | "
            f"precision {float(metrics['precision']) * 100:.2f}%"
        )
    print()
    print(f"Passed development gate: {passed}")
    print(f"Artifact: {ARTIFACT_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("Neither test split was opened.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
