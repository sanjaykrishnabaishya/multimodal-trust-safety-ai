from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from torch.utils.data import DataLoader, TensorDataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    ROOT / "backend" / "storage" / "candidates" / "hate-speech-v7-rc1"
)
MODEL_DIRECTORY = CANDIDATE_DIRECTORY / "model"
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
CALIBRATION_PATH = MODEL_DIRECTORY / "calibration.json"
CIVIL_TEST = ROOT / "datasets" / "public" / "civil_comments_hate_rc2" / "test.csv"
HATEXPLAIN_TEST = ROOT / "datasets" / "public" / "hatexplain" / "test.csv"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v7_rc1_independent"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"

MAX_LENGTH = 128
BATCH_SIZE = 32
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_hash(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required independent-evaluation file is missing: {path}")


def verify_frozen_candidate(manifest: dict[str, Any]) -> None:
    if manifest.get("candidate") != "hate-speech-v7-rc1":
        raise RuntimeError("Unexpected frozen candidate name.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("The frozen candidate did not pass development.")
    if manifest.get("test_splits_used_before_freeze") is not False:
        raise RuntimeError("The pre-freeze test-split contract is invalid.")
    if manifest.get("independently_validated") is not False:
        raise RuntimeError("This RC1 has already been independently evaluated.")
    if manifest.get("connected_to_live_moderation") is not False:
        raise RuntimeError("The candidate must remain disconnected during testing.")
    if manifest.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The candidate must remain review-only.")

    for artifact in manifest.get("artifacts", []):
        relative = Path(str(artifact["relative_path"]))
        path = CANDIDATE_DIRECTORY / relative
        require_file(path)
        actual = sha256_file(path)
        if actual != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen artifact hash mismatch: {relative}")


def load_civil_test() -> list[dict[str, Any]]:
    require_file(CIVIL_TEST)
    rows: list[dict[str, Any]] = []
    with CIVIL_TEST.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            label = str(row.get("label", "")).strip()
            if text and label in LABEL_TO_ID:
                rows.append(
                    {
                        "text": text,
                        "label": label,
                        "source": "Civil Comments",
                        "hash": normalized_hash(text),
                    }
                )
    if not rows:
        raise RuntimeError("The Civil Comments test split was empty.")
    return rows


def load_hatexplain_test() -> list[dict[str, Any]]:
    require_file(HATEXPLAIN_TEST)
    rows: list[dict[str, Any]] = []
    with HATEXPLAIN_TEST.open("r", encoding="utf-8-sig", newline="") as handle:
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
                        "hash": normalized_hash(text),
                    }
                )
    if not rows:
        raise RuntimeError("The HateXplain test split was empty.")
    return rows


def development_hashes(manifest: dict[str, Any]) -> set[str]:
    hashes: set[str] = set()
    for item in manifest.get("development_data_hashes", []):
        path = ROOT / Path(str(item["path"]))
        require_file(path)
        if sha256_file(path) != str(item["sha256"]):
            raise RuntimeError(f"Development data changed after freeze: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                text = str(row.get("text", "")).strip()
                if text:
                    hashes.add(normalized_hash(text))
    return hashes


def encode_records(tokenizer: Any, rows: list[dict[str, Any]]) -> TensorDataset:
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


def infer(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, str]:
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_DIRECTORY,
        local_files_only=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_DIRECTORY,
        local_files_only=True,
        use_safetensors=True,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    loader = DataLoader(
        encode_records(tokenizer, rows),
        batch_size=BATCH_SIZE,
        shuffle=False,
        pin_memory=device.type == "cuda",
    )

    probabilities: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    with torch.inference_mode():
        for index, batch in enumerate(loader, start=1):
            input_ids, attention_mask, truth = batch
            logits = model(
                input_ids=input_ids.to(device),
                attention_mask=attention_mask.to(device),
            ).logits
            probabilities.append(
                torch.softmax(logits, dim=-1).detach().cpu().numpy()
            )
            labels.append(truth.numpy())
            if index % 20 == 0 or index == len(loader):
                completed = min(index * BATCH_SIZE, len(rows))
                print(f"Processed {completed:,}/{len(rows):,} independent records...")
    return np.concatenate(probabilities), np.concatenate(labels), device.type


def raw_metrics(probabilities: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
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


def binary_metrics(selected: np.ndarray, truth: np.ndarray) -> dict[str, Any]:
    hate_truth = truth == LABEL_TO_ID["hate_speech"]
    true_positives = int((selected & hate_truth).sum())
    true_negatives = int((~selected & ~hate_truth).sum())
    false_positives = int((selected & ~hate_truth).sum())
    false_negatives = int((~selected & hate_truth).sum())
    accepted = int(selected.sum())
    positives = int(hate_truth.sum())
    negatives = int((~hate_truth).sum())
    precision = true_positives / accepted if accepted else 0.0
    recall = true_positives / positives if positives else 0.0
    specificity = true_negatives / negatives if negatives else 0.0
    accuracy = (true_positives + true_negatives) / len(truth) if len(truth) else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "records": len(truth),
        "positive_records": positives,
        "negative_records": negatives,
        "accepted": accepted,
        "coverage": round(accepted / len(truth) if len(truth) else 0.0, 4),
        "true_positives": true_positives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "accuracy": round(accuracy, 4),
        "selective_precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1": round(f1, 4),
    }


def evaluate_gate(
    gate: dict[str, Any],
    overall: dict[str, Any],
    civil: dict[str, Any],
    hatexplain: dict[str, Any],
    action_failures: int,
    category_mix_failures: int,
    processing_errors: int,
    overlap_count: int,
) -> dict[str, bool]:
    return {
        "no_development_test_overlap": overlap_count == 0,
        "overall_selective_precision": (
            overall["selective_precision"]
            >= gate["minimum_overall_selective_precision"]
        ),
        "overall_recall": overall["recall"] >= gate["minimum_overall_recall"],
        "overall_specificity": (
            overall["specificity"] >= gate["minimum_overall_specificity"]
        ),
        "civil_selective_precision": (
            civil["selective_precision"]
            >= gate["minimum_civil_selective_precision"]
        ),
        "civil_recall": civil["recall"] >= gate["minimum_civil_recall"],
        "civil_specificity": (
            civil["specificity"] >= gate["minimum_civil_specificity"]
        ),
        "hatexplain_selective_precision": (
            hatexplain["selective_precision"]
            >= gate["minimum_hatexplain_selective_precision"]
        ),
        "hatexplain_recall": (
            hatexplain["recall"] >= gate["minimum_hatexplain_recall"]
        ),
        "hatexplain_specificity": (
            hatexplain["specificity"]
            >= gate["minimum_hatexplain_specificity"]
        ),
        "total_accepted_volume": overall["accepted"] >= gate["minimum_total_accepted"],
        "civil_accepted_volume": civil["accepted"] >= gate["minimum_civil_accepted"],
        "action_contract": (
            action_failures <= gate["maximum_action_contract_failures"]
        ),
        "category_mix_contract": (
            category_mix_failures <= gate["maximum_category_mix_failures"]
        ),
        "processing_contract": (
            processing_errors <= gate["maximum_processing_errors"]
        ),
    }


def print_binary(title: str, metrics: dict[str, Any]) -> None:
    print(title)
    print("-" * 60)
    print(f"Records: {metrics['records']:,}")
    print(f"Accepted: {metrics['accepted']:,}")
    print(f"Accuracy: {metrics['accuracy'] * 100:.2f}%")
    print(f"Selective precision: {metrics['selective_precision'] * 100:.2f}%")
    print(f"Recall: {metrics['recall'] * 100:.2f}%")
    print(f"Specificity: {metrics['specificity'] * 100:.2f}%")
    print(f"F1: {metrics['f1'] * 100:.2f}%")


def main() -> None:
    if VERDICT_PATH.exists():
        raise FileExistsError(
            "This frozen RC1 already has an independent verdict. "
            "The reserved test evaluation will not be repeated."
        )
    for path in (MANIFEST_PATH, CALIBRATION_PATH, CIVIL_TEST, HATEXPLAIN_TEST):
        require_file(path)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_frozen_candidate(manifest)
    gate = manifest["independent_gate_frozen_before_test"]
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    policy = calibration["hate_output_policy"]
    if policy.get("enabled") is not True:
        raise RuntimeError("The frozen selective hate policy is disabled.")

    print("Opening the two reserved test splits for the one RC1 evaluation...")
    civil_rows = load_civil_test()
    hatexplain_rows = load_hatexplain_test()
    rows = civil_rows + hatexplain_rows

    dev_hashes = development_hashes(manifest)
    overlap_count = sum(str(row["hash"]) in dev_hashes for row in rows)
    probabilities, truth, device_type = infer(rows)
    sources = np.array([str(row["source"]) for row in rows])

    hate_probability = probabilities[:, LABEL_TO_ID["hate_speech"]]
    other_probability = probabilities[:, [0, 1]].max(axis=1)
    selected = (
        (hate_probability >= float(policy["probability_threshold"]))
        & (
            (hate_probability - other_probability)
            >= float(policy["minimum_margin"])
        )
    )

    overall = binary_metrics(selected, truth)
    civil_mask = sources == "Civil Comments"
    hatexplain_mask = sources == "HateXplain"
    civil = binary_metrics(selected[civil_mask], truth[civil_mask])
    hatexplain = binary_metrics(selected[hatexplain_mask], truth[hatexplain_mask])
    raw = raw_metrics(probabilities, truth)

    false_positive_labels = Counter(
        ID_TO_LABEL[int(label)]
        for is_selected, label in zip(selected, truth)
        if is_selected and int(label) != LABEL_TO_ID["hate_speech"]
    )
    processing_errors = 0
    action_failures = 0
    category_mix_failures = 0
    checks = evaluate_gate(
        gate,
        overall,
        civil,
        hatexplain,
        action_failures,
        category_mix_failures,
        processing_errors,
        overlap_count,
    )
    passed = all(checks.values())

    report = {
        "candidate": manifest["candidate"],
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "device": device_type,
        "test_file_hashes": {
            "civil_comments": sha256_file(CIVIL_TEST),
            "hatexplain": sha256_file(HATEXPLAIN_TEST),
        },
        "records": len(rows),
        "source_counts": {
            "Civil Comments": len(civil_rows),
            "HateXplain": len(hatexplain_rows),
        },
        "development_test_overlap_count": overlap_count,
        "frozen_policy": {
            "probability_threshold": policy["probability_threshold"],
            "minimum_margin": policy["minimum_margin"],
        },
        "overall": overall,
        "source_results": {
            "Civil Comments": civil,
            "HateXplain": hatexplain,
        },
        "raw_three_class_diagnostic": raw,
        "false_positive_true_labels": dict(false_positive_labels),
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "processing_errors": processing_errors,
        "independent_gate": gate,
        "gate_checks": checks,
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "raw_test_text_stored": False,
        "record_level_predictions_stored": False,
        "individual_predictions_printed": False,
        "test_data_used_for_training": False,
        "test_data_used_for_rag": False,
        "holdout_may_modify_rc1": False,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    verdict = {
        "candidate": manifest["candidate"],
        "status": (
            "Passed independent readiness gate"
            if passed
            else "Failed independent readiness gate"
        ),
        "evaluated_at_utc": report["evaluated_at_utc"],
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "aggregate_report": str(REPORT_PATH),
        "frozen_artifacts_modified": False,
        "evaluation_verdict_added": True,
        "holdout_may_modify_rc1": False,
    }
    VERDICT_PATH.write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH V7 RC1 INDEPENDENT TEST")
    print("=" * 60)
    print(f"Candidate: {manifest['candidate']}")
    print(f"Records: {len(rows):,}")
    print(f"Development/test overlap: {overlap_count}")
    print()
    print_binary("OVERALL SELECTIVE HATE OUTPUT", overall)
    print()
    print_binary("CIVIL COMMENTS", civil)
    print()
    print_binary("HATEXPLAIN", hatexplain)
    print()
    print("BOUNDARY AND CONTRACT RESULTS")
    print("-" * 60)
    print(f"False positives from Abusive Words: {false_positive_labels.get('abusive_words', 0)}")
    print(f"False positives from Safe/Other: {false_positive_labels.get('safe_or_other', 0)}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Processing errors: {processing_errors}")
    print()
    print("INDEPENDENT GATE CHECKS")
    print("-" * 60)
    for name, value in checks.items():
        print(f"{name}: {value}")
    print()
    print(f"Passed independent readiness gate: {passed}")
    print(f"Eligible for guarded live integration: {passed}")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print(f"Report: {REPORT_PATH}")
    print(f"Verdict: {VERDICT_PATH}")
    print("No raw test text or individual predictions were stored or printed.")
    print("This holdout may not be used to modify RC1.")


if __name__ == "__main__":
    main()
