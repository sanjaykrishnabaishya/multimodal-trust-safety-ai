from __future__ import annotations

import csv
import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from torch.nn.utils import clip_grad_norm_
from torch.optim import AdamW
from torch.utils.data import DataLoader, TensorDataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)


ROOT = Path(__file__).resolve().parents[2]
CIVIL_DIRECTORY = ROOT / "datasets" / "public" / "civil_comments_hate_rc2"
HATEXPLAIN_DIRECTORY = ROOT / "datasets" / "public" / "hatexplain"
MODEL_DIRECTORY = ROOT / "backend" / "storage" / "models" / "hate_speech_v6"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v6_finetuned_development"
)
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"
CALIBRATION_PATH = MODEL_DIRECTORY / "calibration.json"
CONFIG_PATH = MODEL_DIRECTORY / "development_config.json"

BASE_MODEL_NAME = "microsoft/MiniLM-L12-H384-uncased"
BASE_MODEL_REVISION = "86186eff27cda7c5bc520e45de4800c575d9d8b3"
BASE_MODEL_LICENSE = "MIT"
SEED = 20260811
MAX_LENGTH = 128
BATCH_SIZE = 16
EPOCHS = 3
LEARNING_RATE = 2e-5
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.10
HATEXPLAIN_TRAIN_PER_CLASS = 1500

LABEL_TO_ID = {
    "safe_or_other": 0,
    "abusive_words": 1,
    "hate_speech": 2,
}
ID_TO_LABEL = {value: key for key, value in LABEL_TO_ID.items()}

HATEXPLAIN_CATEGORY_TO_LABEL = {
    "Normal/Ignore": "safe_or_other",
    "Abusive Words": "abusive_words",
    "Hate Speech & Discrimination": "hate_speech",
}

TARGET_OVERALL_PRECISION = 0.90
TARGET_SOURCE_PRECISION = 0.85
TARGET_OVERALL_SPECIFICITY = 0.95
TARGET_SOURCE_SPECIFICITY = 0.90
MINIMUM_OVERALL_RECALL = 0.15
MINIMUM_SOURCE_RECALL = 0.15
MINIMUM_ACCEPTED = 100
MINIMUM_RAW_ACCURACY = 0.75
MINIMUM_RAW_MACRO_F1 = 0.75


def set_seed() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))


def normalized_text_hash(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_civil(split: str) -> list[dict[str, Any]]:
    path = CIVIL_DIRECTORY / f"{split}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Required Civil Comments split was not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            label = str(row.get("label", "")).strip()
            if text and label in LABEL_TO_ID:
                rows.append(
                    {
                        "text": text,
                        "label": label,
                        "source": "Civil Comments",
                        "hash": normalized_text_hash(text),
                    }
                )
    return rows


def load_hatexplain(split: str) -> list[dict[str, Any]]:
    path = HATEXPLAIN_DIRECTORY / f"{split}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Required HateXplain split was not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            category = str(row.get("category", "")).strip()
            label = HATEXPLAIN_CATEGORY_TO_LABEL.get(category)
            if text and label:
                rows.append(
                    {
                        "text": text,
                        "label": label,
                        "source": "HateXplain",
                        "hash": normalized_text_hash(text),
                    }
                )
    return rows


def balanced_hatexplain_training(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["label"])].append(row)
    rng = random.Random(SEED)
    selected: list[dict[str, Any]] = []
    for label in LABEL_TO_ID:
        candidates = grouped[label]
        if len(candidates) < HATEXPLAIN_TRAIN_PER_CLASS:
            raise RuntimeError(
                f"HateXplain train has only {len(candidates)} {label} rows; "
                f"{HATEXPLAIN_TRAIN_PER_CLASS} are required."
            )
        selected.extend(rng.sample(candidates, HATEXPLAIN_TRAIN_PER_CLASS))
    rng.shuffle(selected)
    return selected


def load_development_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    civil_train = load_civil("train")
    civil_validation = load_civil("validation")
    hatexplain_train = balanced_hatexplain_training(load_hatexplain("train"))
    hatexplain_validation = load_hatexplain("validation")

    train = civil_train + hatexplain_train
    validation = civil_validation + hatexplain_validation
    train_hashes = {str(row["hash"]) for row in train}
    validation_hashes = {str(row["hash"]) for row in validation}
    overlap = train_hashes & validation_hashes
    if overlap:
        raise RuntimeError(
            f"Training/validation leakage detected: {len(overlap)} normalized hashes."
        )

    rng = random.Random(SEED)
    rng.shuffle(train)
    return train, validation


def encode_dataset(
    tokenizer: Any,
    rows: list[dict[str, Any]],
) -> TensorDataset:
    encoded = tokenizer(
        [str(row["text"]) for row in rows],
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    labels = torch.tensor(
        [LABEL_TO_ID[str(row["label"])] for row in rows],
        dtype=torch.long,
    )
    return TensorDataset(
        encoded["input_ids"],
        encoded["attention_mask"],
        labels,
    )


def move_batch(
    batch: tuple[torch.Tensor, ...],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    input_ids, attention_mask, labels = batch
    return (
        input_ids.to(device),
        attention_mask.to(device),
        labels.to(device),
    )


def validation_probabilities(
    model: Any,
    loader: DataLoader,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    probability_batches: list[np.ndarray] = []
    label_batches: list[np.ndarray] = []
    with torch.inference_mode():
        for batch in loader:
            input_ids, attention_mask, labels = move_batch(batch, device)
            logits = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            ).logits
            probability_batches.append(
                torch.softmax(logits, dim=-1).detach().cpu().numpy()
            )
            label_batches.append(labels.detach().cpu().numpy())
    return np.concatenate(probability_batches), np.concatenate(label_batches)


def multiclass_metrics(
    probabilities: np.ndarray,
    truth: np.ndarray,
) -> dict[str, Any]:
    predicted = probabilities.argmax(axis=1)
    precision, recall, f1, support = precision_recall_fscore_support(
        truth,
        predicted,
        labels=[0, 1, 2],
        zero_division=0,
    )
    return {
        "accuracy": round(float(accuracy_score(truth, predicted)), 4),
        "macro_f1": round(float(np.mean(f1)), 4),
        "class_results": {
            ID_TO_LABEL[index]: {
                "precision": round(float(precision[index]), 4),
                "recall": round(float(recall[index]), 4),
                "f1": round(float(f1[index]), 4),
                "support": int(support[index]),
            }
            for index in (0, 1, 2)
        },
    }


def hate_metrics(
    selected: np.ndarray,
    truth: np.ndarray,
    sources: np.ndarray,
) -> dict[str, Any]:
    hate_truth = truth == LABEL_TO_ID["hate_speech"]
    accepted = int(selected.sum())
    true_positives = int((selected & hate_truth).sum())
    false_positives = int((selected & ~hate_truth).sum())
    positives = int(hate_truth.sum())
    negatives = int((~hate_truth).sum())

    result: dict[str, Any] = {
        "accepted": accepted,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "precision": round(
            true_positives / accepted if accepted else 0.0,
            4,
        ),
        "recall": round(true_positives / positives if positives else 0.0, 4),
        "specificity": round(
            1.0 - (false_positives / negatives if negatives else 0.0),
            4,
        ),
        "source_metrics": {},
    }
    for source in ("Civil Comments", "HateXplain"):
        mask = sources == source
        source_selected = selected & mask
        source_hate = hate_truth & mask
        source_non_hate = ~hate_truth & mask
        source_accepted = int(source_selected.sum())
        source_tp = int((source_selected & source_hate).sum())
        source_fp = int((source_selected & source_non_hate).sum())
        source_positive = int(source_hate.sum())
        source_negative = int(source_non_hate.sum())
        result["source_metrics"][source] = {
            "records": int(mask.sum()),
            "accepted": source_accepted,
            "true_positives": source_tp,
            "false_positives": source_fp,
            "precision": round(
                source_tp / source_accepted if source_accepted else 0.0,
                4,
            ),
            "recall": round(
                source_tp / source_positive if source_positive else 0.0,
                4,
            ),
            "specificity": round(
                1.0 - (
                    source_fp / source_negative if source_negative else 0.0
                ),
                4,
            ),
        }
    return result


def passes_hate_gates(result: dict[str, Any]) -> bool:
    civil = result["source_metrics"]["Civil Comments"]
    hatexplain = result["source_metrics"]["HateXplain"]
    return bool(
        result["precision"] >= TARGET_OVERALL_PRECISION
        and result["specificity"] >= TARGET_OVERALL_SPECIFICITY
        and result["recall"] >= MINIMUM_OVERALL_RECALL
        and result["accepted"] >= MINIMUM_ACCEPTED
        and civil["precision"] >= TARGET_SOURCE_PRECISION
        and civil["specificity"] >= TARGET_SOURCE_SPECIFICITY
        and civil["recall"] >= MINIMUM_SOURCE_RECALL
        and hatexplain["precision"] >= TARGET_SOURCE_PRECISION
        and hatexplain["specificity"] >= TARGET_SOURCE_SPECIFICITY
        and hatexplain["recall"] >= MINIMUM_SOURCE_RECALL
    )


def calibrate_hate_output(
    probabilities: np.ndarray,
    truth: np.ndarray,
    sources: np.ndarray,
) -> dict[str, Any]:
    hate_probability = probabilities[:, LABEL_TO_ID["hate_speech"]]
    other_probability = probabilities[:, [0, 1]].max(axis=1)
    candidates: list[dict[str, Any]] = []
    for threshold in np.arange(0.30, 0.951, 0.02):
        for margin in np.arange(0.00, 0.401, 0.02):
            selected = (
                (hate_probability >= threshold)
                & ((hate_probability - other_probability) >= margin)
            )
            metrics = hate_metrics(selected, truth, sources)
            candidates.append(
                {
                    "probability_threshold": round(float(threshold), 2),
                    "minimum_margin": round(float(margin), 2),
                    **metrics,
                }
            )

    passing = [candidate for candidate in candidates if passes_hate_gates(candidate)]
    if passing:
        return {
            "enabled": True,
            **max(
                passing,
                key=lambda item: (
                    item["recall"],
                    item["accepted"],
                    item["precision"],
                    item["specificity"],
                ),
            ),
        }

    closest = max(
        candidates,
        key=lambda item: (
            int(item["precision"] >= TARGET_OVERALL_PRECISION)
            + int(item["specificity"] >= TARGET_OVERALL_SPECIFICITY)
            + int(item["recall"] >= MINIMUM_OVERALL_RECALL)
            + int(item["source_metrics"]["Civil Comments"]["precision"] >= TARGET_SOURCE_PRECISION)
            + int(item["source_metrics"]["Civil Comments"]["recall"] >= MINIMUM_SOURCE_RECALL)
            + int(item["source_metrics"]["HateXplain"]["precision"] >= TARGET_SOURCE_PRECISION)
            + int(item["source_metrics"]["HateXplain"]["recall"] >= MINIMUM_SOURCE_RECALL),
            item["precision"],
            item["recall"],
        ),
    )
    return {
        "enabled": False,
        "reason": "No calibrated hate output satisfied every development gate.",
        "closest_candidate": closest,
    }


def train_model(
    train_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
) -> tuple[Any, Any, np.ndarray, np.ndarray, list[dict[str, Any]], str]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training device: {device.type.upper()}")
    print("Loading the pinned MiniLM base model...")
    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL_NAME,
        revision=BASE_MODEL_REVISION,
        use_fast=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL_NAME,
        revision=BASE_MODEL_REVISION,
        num_labels=len(LABEL_TO_ID),
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID,
    )
    model.to(device)

    print("Encoding training and validation records...")
    train_dataset = encode_dataset(tokenizer, train_rows)
    validation_dataset = encode_dataset(tokenizer, validation_rows)
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        generator=generator,
        pin_memory=device.type == "cuda",
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=BATCH_SIZE * 2,
        shuffle=False,
        pin_memory=device.type == "cuda",
    )

    optimizer = AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * WARMUP_RATIO),
        num_training_steps=total_steps,
    )

    best_macro_f1 = -1.0
    best_state: dict[str, torch.Tensor] | None = None
    best_probabilities: np.ndarray | None = None
    best_truth: np.ndarray | None = None
    history: list[dict[str, Any]] = []

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for step, batch in enumerate(train_loader, start=1):
            input_ids, attention_mask, labels = move_batch(batch, device)
            optimizer.zero_grad(set_to_none=True)
            output = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            output.loss.backward()
            clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            total_loss += float(output.loss.detach().cpu())
            if step % 100 == 0 or step == len(train_loader):
                print(
                    f"Epoch {epoch}/{EPOCHS} | step {step}/{len(train_loader)} "
                    f"| mean loss {total_loss / step:.4f}"
                )

        probabilities, truth = validation_probabilities(
            model,
            validation_loader,
            device,
        )
        metrics = multiclass_metrics(probabilities, truth)
        history.append(
            {
                "epoch": epoch,
                "mean_training_loss": round(total_loss / len(train_loader), 6),
                **metrics,
            }
        )
        print(
            f"Epoch {epoch} validation: accuracy "
            f"{metrics['accuracy'] * 100:.2f}% | macro F1 "
            f"{metrics['macro_f1'] * 100:.2f}%"
        )
        if float(metrics["macro_f1"]) > best_macro_f1:
            best_macro_f1 = float(metrics["macro_f1"])
            best_state = {
                name: tensor.detach().cpu().clone()
                for name, tensor in model.state_dict().items()
            }
            best_probabilities = probabilities.copy()
            best_truth = truth.copy()

    if best_state is None or best_probabilities is None or best_truth is None:
        raise RuntimeError("Training did not produce a usable development checkpoint.")
    model.load_state_dict(best_state)
    model.to("cpu")
    return (
        model,
        tokenizer,
        best_probabilities,
        best_truth,
        history,
        device.type,
    )


def print_hate_policy(policy: dict[str, Any]) -> None:
    metrics = policy if policy["enabled"] else policy["closest_candidate"]
    print(f"Enabled: {policy['enabled']}")
    if not policy["enabled"]:
        print(f"Reason: {policy['reason']}")
        print("Closest rejected candidate:")
    print(f"Probability threshold: {metrics['probability_threshold']:.2f}")
    print(f"Minimum margin: {metrics['minimum_margin']:.2f}")
    print(f"Accepted: {metrics['accepted']:,}")
    print(f"Precision: {metrics['precision'] * 100:.2f}%")
    print(f"Recall: {metrics['recall'] * 100:.2f}%")
    print(f"Specificity: {metrics['specificity'] * 100:.2f}%")
    for source, source_metrics_result in metrics["source_metrics"].items():
        print(
            f"  {source}: precision "
            f"{source_metrics_result['precision'] * 100:.2f}% | recall "
            f"{source_metrics_result['recall'] * 100:.2f}% | specificity "
            f"{source_metrics_result['specificity'] * 100:.2f}% | accepted "
            f"{source_metrics_result['accepted']:,}"
        )


def main() -> None:
    set_seed()
    train_rows, validation_rows = load_development_data()
    print("HATE SPEECH V6 SUPERVISED DEVELOPMENT")
    print("=" * 60)
    print(f"Training records: {len(train_rows):,}")
    print(f"Validation records: {len(validation_rows):,}")
    print(f"Training label counts: {dict(Counter(row['label'] for row in train_rows))}")
    print("Reserved test splits opened: False")
    print()

    (
        model,
        tokenizer,
        probabilities,
        truth,
        history,
        device_type,
    ) = train_model(train_rows, validation_rows)
    raw_metrics = multiclass_metrics(probabilities, truth)
    sources = np.array([str(row["source"]) for row in validation_rows])
    hate_policy = calibrate_hate_output(probabilities, truth, sources)

    raw_gate = bool(
        raw_metrics["accuracy"] >= MINIMUM_RAW_ACCURACY
        and raw_metrics["macro_f1"] >= MINIMUM_RAW_MACRO_F1
    )
    passed = bool(raw_gate and hate_policy["enabled"])

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(MODEL_DIRECTORY, safe_serialization=True)
    tokenizer.save_pretrained(MODEL_DIRECTORY)

    report = {
        "candidate": "hate-speech-v6-finetuned-development",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_model": BASE_MODEL_NAME,
        "base_model_revision": BASE_MODEL_REVISION,
        "base_model_license": BASE_MODEL_LICENSE,
        "device": device_type,
        "training_records": len(train_rows),
        "validation_records": len(validation_rows),
        "training_label_counts": dict(Counter(row["label"] for row in train_rows)),
        "training_source_counts": dict(Counter(row["source"] for row in train_rows)),
        "training_parameters": {
            "seed": SEED,
            "max_length": MAX_LENGTH,
            "batch_size": BATCH_SIZE,
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "weight_decay": WEIGHT_DECAY,
            "warmup_ratio": WARMUP_RATIO,
        },
        "training_history": history,
        "raw_validation_metrics": raw_metrics,
        "hate_output_policy": hate_policy,
        "raw_development_gate_passed": raw_gate,
        "passed_development_gate": passed,
        "test_splits_opened": False,
        "raw_text_stored_in_report": False,
        "record_level_predictions_stored": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "active_output_category_if_validated": "Hate Speech & Discrimination",
        "abusive_words_live_behavior": "Remain handled by validated RC2",
        "safe_live_behavior": "No override",
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "candidate": report["candidate"],
                "base_model": BASE_MODEL_NAME,
                "base_model_revision": BASE_MODEL_REVISION,
                "base_model_license": BASE_MODEL_LICENSE,
                "label_to_id": LABEL_TO_ID,
                "hate_output_policy": hate_policy,
                "passed_development_gate": passed,
                "test_splits_opened": False,
                "automatic_enforcement_allowed": False,
                "connected_to_live_moderation": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    CALIBRATION_PATH.write_text(
        json.dumps(
            {
                "candidate": report["candidate"],
                "hate_output_policy": hate_policy,
                "passed_development_gate": passed,
                "test_splits_opened": False,
                "automatic_enforcement_allowed": False,
                "connected_to_live_moderation": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH V6 FINETUNED DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Raw accuracy: {raw_metrics['accuracy'] * 100:.2f}%")
    print(f"Raw macro F1: {raw_metrics['macro_f1'] * 100:.2f}%")
    print()
    print("RAW CLASS RESULTS")
    print("-" * 60)
    for label, metrics in raw_metrics["class_results"].items():
        print(
            f"{label}: precision {metrics['precision'] * 100:.2f}% | "
            f"recall {metrics['recall'] * 100:.2f}% | "
            f"F1 {metrics['f1'] * 100:.2f}%"
        )
    print()
    print("SELECTIVE HATE OUTPUT")
    print("-" * 60)
    print_hate_policy(hate_policy)
    print()
    print(f"Raw development gate passed: {raw_gate}")
    print(f"Passed complete development gate: {passed}")
    print(f"Model artifact: {MODEL_DIRECTORY}")
    print(f"Report: {REPORT_PATH}")
    print("Neither reserved test split was opened.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
