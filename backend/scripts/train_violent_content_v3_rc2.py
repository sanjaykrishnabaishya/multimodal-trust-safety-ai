from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, precision_recall_fscore_support


CANDIDATE = "violent-content-v3-rc2-development"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
POSITIVE_CLASSES = ("graphic_violence", "allowed_context", "targeted_threat")
ALL_CLASSES = (*POSITIVE_CLASSES, "safe_or_other")
ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "datasets" / "development" / "violent_content_v3" / "development.csv"
MODEL_DIR = ROOT / "backend" / "storage" / "models" / "violent_content_v3_rc2"
REPORT_DIR = ROOT / "reports" / "evaluation" / "violent_content" / "v3_rc2_development"


HARD_NEGATIVES = (
    "The chef crushed pepper before adding it to the soup.",
    "The audience exploded into applause after the final song.",
    "The editor killed the weak opening paragraph.",
    "The new product destroyed last month's sales record.",
    "The goalkeeper blocked a dangerous attack during the match.",
    "The photographer shot the ceremony from the balcony.",
    "The operating system killed an unresponsive process.",
    "The storm knocked out power but nobody was injured.",
    "The doctor showed the class a model of a human skull.",
    "The textbook contains a labelled drawing of internal organs.",
    "The museum exhibits an ancient skeleton behind glass.",
    "The athlete recovered from a simple leg fracture.",
    "A stunt coordinator rehearsed a fake fight with the actors.",
    "The cartoon character fell over and immediately stood up.",
    "Police prevented the confrontation before anyone was harmed.",
    "She reported an intimidating message to the school counselor.",
    "The workshop teaches people never to threaten others.",
    "The safety poster says to leave an area when conflict begins.",
    "Send your password to unlock the cash reward.",
    "This fake support agent demands a bank transfer.",
    "The post reveals a private address without permission.",
    "The file contains code intended to steal account credentials.",
    "The comment attacks a person because of their religion.",
    "The seller copied a copyrighted film and offered downloads.",
    "The appointment begins at ten o'clock on Monday.",
    "Our family visited a science museum during the holiday.",
    "The article explains how batteries store energy.",
    "A train arrived at the central platform this morning.",
    "The teacher discussed the structure of bones in biology class.",
    "The drama uses sound effects while all physical contact happens off camera.",
    "A journalist quoted the threatening words solely as evidence in a court report.",
    "The moderator removed a threat and directed the recipient to support services.",
)


EXTRA_GRAPHIC = (
    "An uncensored photograph reveals a deep wound with tissue visible.",
    "The clip focuses on a dead body missing both hands.",
    "A close view shows a shattered bone protruding through skin.",
    "The footage depicts prolonged torture with severe visible injuries.",
    "The picture clearly displays blood-covered human remains.",
    "A frame shows a corpse burned beyond recognition.",
    "The recording visibly captures a limb being removed from a victim.",
    "The image presents a body torn apart by the blast.",
    "A close-up reveals an open skull and exposed tissue.",
    "The uncensored scene displays several detached body parts.",
    "The video shows a captive with graphic wounds after repeated beating.",
    "The photograph visibly depicts a decapitated corpse.",
)


EXTRA_CONTEXT = (
    "The news anchor reports deaths in the conflict without displaying victims.",
    "A podcast discusses assault prevention and lists emergency resources.",
    "The history lecture covers wartime casualties using only maps.",
    "A censored documentary describes torture while the screen remains blurred.",
    "The newspaper mentions a fatal stabbing without graphic detail.",
    "An educational program explains how to respond to armed violence.",
    "The court summary discusses a murder case in restrained factual language.",
    "A radio bulletin reports an explosion and provides no visual material.",
    "The museum panel describes a historical execution without an image.",
    "The article analyzes violent-crime statistics using charts.",
    "A fictional story implies a battle occurred but does not describe injuries.",
    "A public-service announcement addresses domestic violence prevention.",
)


EXTRA_THREATS = (
    "I know your route home and I am coming to hurt you.",
    "Keep speaking and I will break your teeth.",
    "If you complain, I will attack your brother.",
    "We are waiting outside to beat you after work.",
    "I am bringing a weapon when I meet you tonight.",
    "Delete the message or your family will be harmed.",
    "You will end up in hospital when I find you.",
    "I intend to set your room on fire while you sleep.",
    "Someone should physically punish her for that opinion.",
    "There is no place to hide because I will come after you.",
    "Meet me behind the station and I will crush your jaw.",
    "I will send people to attack him unless he pays.",
)


def load_development() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(f"Development dataset not found: {DATASET_PATH}")
    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    train = [row for row in rows if row["split"] == "train"]
    validation = [row for row in rows if row["split"] == "validation"]
    if not train or not validation:
        raise RuntimeError("Train and validation splits are required.")
    return train, validation


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def choose_binary_threshold(y_true: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    best: tuple[tuple[float, float, float, float], dict[str, float]] | None = None
    for threshold in np.arange(0.30, 0.91, 0.01):
        predicted = probability >= threshold
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true,
            predicted,
            average="binary",
            zero_division=0,
        )
        qualifies = precision >= 0.85 and recall >= 0.85
        rank = (float(qualifies), float(f1), float(precision), float(recall))
        result = {
            "threshold": round(float(threshold), 2),
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1": round(float(f1), 4),
            "passed_85_percent": bool(qualifies),
        }
        if best is None or rank > best[0]:
            best = (rank, result)
    if best is None:
        raise RuntimeError("Unable to select a binary threshold.")
    return best[1]


def predict_runtime(
    score_matrix: np.ndarray,
    thresholds: dict[str, dict[str, float]],
    margin: float,
) -> np.ndarray:
    results: list[str] = []
    for scores in score_matrix:
        order = np.argsort(scores)[::-1]
        top_index = int(order[0])
        second_index = int(order[1])
        label = POSITIVE_CLASSES[top_index]
        top_score = float(scores[top_index])
        score_margin = top_score - float(scores[second_index])
        if top_score >= thresholds[label]["threshold"] and score_margin >= margin:
            results.append(label)
        else:
            results.append("safe_or_other")
    return np.array(results)


def main() -> None:
    train, validation = load_development()
    validation_text = {normalize(row["text"]) for row in validation}
    additions = [
        *(('safe_or_other', text) for text in HARD_NEGATIVES),
        *(('graphic_violence', text) for text in EXTRA_GRAPHIC),
        *(('allowed_context', text) for text in EXTRA_CONTEXT),
        *(('targeted_threat', text) for text in EXTRA_THREATS),
    ]
    overlap = sorted(normalize(text) for _, text in additions if normalize(text) in validation_text)
    if overlap:
        raise RuntimeError(f"RC2 augmentation overlaps validation: {overlap}")

    train_texts = [row["text"] for row in train] + [text for _, text in additions]
    train_labels = np.array(
        [row["semantic_class"] for row in train] + [label for label, _ in additions]
    )
    validation_texts = [row["text"] for row in validation]
    validation_labels = np.array([row["semantic_class"] for row in validation])

    print(f"Loading semantic embedding model: {MODEL_NAME}")
    encoder = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")
    train_embeddings = encoder.encode(
        train_texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True
    )
    validation_embeddings = encoder.encode(
        validation_texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True
    )

    classifiers: dict[str, LogisticRegression] = {}
    thresholds: dict[str, dict[str, float]] = {}
    validation_scores: list[np.ndarray] = []
    for label in POSITIVE_CLASSES:
        y_train = (train_labels == label).astype(int)
        y_validation = (validation_labels == label).astype(int)
        classifier = LogisticRegression(
            C=1.0,
            class_weight="balanced",
            max_iter=3000,
            random_state=42,
        )
        classifier.fit(train_embeddings, y_train)
        probability = classifier.predict_proba(validation_embeddings)[:, 1]
        classifiers[label] = classifier
        thresholds[label] = choose_binary_threshold(y_validation, probability)
        validation_scores.append(probability)

    score_matrix = np.column_stack(validation_scores)
    best_margin: float | None = None
    best_predictions: np.ndarray | None = None
    best_report: dict[str, object] | None = None
    best_rank: tuple[float, float, float] | None = None
    for margin in np.arange(0.00, 0.31, 0.01):
        predictions = predict_runtime(score_matrix, thresholds, float(margin))
        report = classification_report(
            validation_labels,
            predictions,
            labels=list(ALL_CLASSES),
            output_dict=True,
            zero_division=0,
        )
        every_class_passes = all(
            float(report[label]["precision"]) >= 0.85
            and float(report[label]["recall"]) >= 0.85
            and float(report[label]["f1-score"]) >= 0.85
            for label in ALL_CLASSES
        )
        rank = (
            float(every_class_passes),
            float(report["macro avg"]["f1-score"]),
            float(margin),
        )
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_margin = round(float(margin), 2)
            best_predictions = predictions
            best_report = report

    if best_margin is None or best_predictions is None or best_report is None:
        raise RuntimeError("Unable to select the RC2 decision margin.")

    exact_accuracy = float(np.mean(best_predictions == validation_labels))
    every_class_passes = all(
        float(best_report[label]["precision"]) >= 0.85
        and float(best_report[label]["recall"]) >= 0.85
        and float(best_report[label]["f1-score"]) >= 0.85
        for label in ALL_CLASSES
    )
    passed = exact_accuracy >= 0.85 and every_class_passes

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = MODEL_DIR / "classifier_bundle.joblib"
    config_path = MODEL_DIR / "config.json"
    report_path = REPORT_DIR / "validation_report.json"
    joblib.dump(classifiers, artifact_path)
    config = {
        "candidate": CANDIDATE,
        "embedding_model": MODEL_NAME,
        "embedding_model_revision": MODEL_REVISION,
        "positive_classes": list(POSITIVE_CLASSES),
        "default_result": "safe_or_other",
        "default_behavior": "No specialist override",
        "thresholds": thresholds,
        "minimum_score_margin": best_margin,
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    report_payload = {
        "candidate": CANDIDATE,
        "training_records": len(train_texts),
        "base_training_records": len(train),
        "hard_negative_records": len(HARD_NEGATIVES),
        "additional_positive_records": len(EXTRA_GRAPHIC) + len(EXTRA_CONTEXT) + len(EXTRA_THREATS),
        "validation_records": len(validation),
        "validation_overlap": overlap,
        "accuracy": round(exact_accuracy, 4),
        "macro_f1": round(float(best_report["macro avg"]["f1-score"]), 4),
        "minimum_score_margin": best_margin,
        "thresholds": thresholds,
        "classification_report": best_report,
        "passed_development_gate": passed,
        "notice": "Development evidence only. RC1 holdout data was not read or reused.",
    }
    report_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")

    print("\nVIOLENT CONTENT V3 RC2 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Training records: {len(train_texts)}")
    print(f"Validation records: {len(validation)}")
    print(f"Validation overlap: {len(overlap)}")
    print(f"Accuracy: {exact_accuracy * 100:.2f}%")
    print(f"Macro F1: {best_report['macro avg']['f1-score'] * 100:.2f}%")
    print(f"Minimum score margin: {best_margin:.2f}")
    print("\nCLASS RESULTS")
    print("-" * 60)
    for label in ALL_CLASSES:
        values = best_report[label]
        print(
            f"{label}: precision {values['precision'] * 100:.2f}% | "
            f"recall {values['recall'] * 100:.2f}% | "
            f"F1 {values['f1-score'] * 100:.2f}%"
        )
    print(f"\nPassed development gate: {passed}")
    print(f"Artifact: {artifact_path}")
    print(f"Report: {report_path}")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
