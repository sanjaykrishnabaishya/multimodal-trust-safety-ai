from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datasets import load_dataset


DATASET_NAME = "google/civil_comments"
DATASET_REVISION = "main"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "datasets" / "public" / "civil_comments_cyber"
LABELS = ("targeted_threat", "abusive_words", "safe_or_other")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-per-label", type=int, default=500)
    parser.add_argument("--validation-per-label", type=int, default=100)
    parser.add_argument("--test-per-label", type=int, default=100)
    parser.add_argument("--max-scan", type=int, default=2_000_000)
    return parser.parse_args()


def score(record: dict[str, Any], key: str) -> float:
    try:
        return float(record.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def map_label(record: dict[str, Any]) -> str | None:
    threat = score(record, "threat")
    insult = score(record, "insult")
    toxicity = score(record, "toxicity")
    severe = score(record, "severe_toxicity")
    obscene = score(record, "obscene")
    identity = score(record, "identity_attack")
    sexual = score(record, "sexual_explicit")

    # Other TrustScope categories retain priority and are excluded here.
    if identity >= 0.50 or sexual >= 0.50:
        return None
    if threat >= 0.50:
        return "targeted_threat"
    if insult >= 0.50 and threat < 0.20:
        return "abusive_words"
    if (
        toxicity <= 0.10
        and severe <= 0.10
        and obscene <= 0.10
        and threat <= 0.10
        and insult <= 0.10
        and identity <= 0.10
        and sexual <= 0.10
    ):
        return "safe_or_other"
    return None


def text_hash(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def collect_split(
    split: str,
    quota: int,
    max_scan: int,
    global_hashes: set[str],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    stream = load_dataset(
        DATASET_NAME,
        split=split,
        streaming=True,
        revision=DATASET_REVISION,
    ).shuffle(seed=42, buffer_size=20_000)
    selected: list[dict[str, str]] = []
    counts = Counter[str]()
    statistics = Counter[str]()
    print(f"Streaming Civil Comments {split} split...")

    for scanned, record in enumerate(stream, 1):
        statistics["scanned"] = scanned
        if scanned > max_scan:
            break
        text = str(record.get("text", "")).strip()
        if len(text) < 3 or len(text) > 5_000:
            statistics["invalid_text"] += 1
            continue
        label = map_label(record)
        if label is None:
            statistics["ambiguous_or_excluded"] += 1
            continue
        if counts[label] >= quota:
            continue
        digest = text_hash(text)
        if digest in global_hashes:
            statistics["duplicates"] += 1
            continue
        global_hashes.add(digest)
        counts[label] += 1
        selected.append(
            {
                "record_id": f"civil-{split}-{digest[:16]}",
                "split": split,
                "label": label,
                "text": text,
                "source_text_sha256": digest,
            }
        )
        if scanned % 25_000 == 0:
            print(f"  scanned {scanned:,}: {dict(counts)}")
        if all(counts[label_name] >= quota for label_name in LABELS):
            break

    missing = {label: quota - counts[label] for label in LABELS if counts[label] < quota}
    if missing:
        raise RuntimeError(
            f"The {split} split did not provide the requested balanced quota. "
            f"Missing: {missing}. Scanned: {statistics['scanned']:,}."
        )
    return selected, dict(statistics)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    quotas = {
        "train": args.train_per_label,
        "validation": args.validation_per_label,
        "test": args.test_per_label,
    }
    if any(value <= 0 for value in quotas.values()):
        raise ValueError("Every per-label quota must be positive.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    global_hashes: set[str] = set()
    split_reports: dict[str, Any] = {}
    file_hashes: dict[str, str] = {}

    for split in ("train", "validation", "test"):
        rows, statistics = collect_split(
            split,
            quotas[split],
            args.max_scan,
            global_hashes,
        )
        path = OUTPUT_DIR / f"{split}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        counts = Counter(row["label"] for row in rows)
        split_reports[split] = {
            "records": len(rows),
            "label_counts": dict(sorted(counts.items())),
            "stream_statistics": statistics,
            "usage": (
                "training" if split == "train" else
                "threshold_selection_only" if split == "validation" else
                "independent_evaluation_only"
            ),
        }
        file_hashes[path.name] = file_sha256(path)

    manifest = {
        "source_dataset": DATASET_NAME,
        "source_revision": DATASET_REVISION,
        "source_url": "https://huggingface.co/datasets/google/civil_comments",
        "license": "CC0-1.0",
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "language": "English",
        "labels": list(LABELS),
        "mapping": {
            "targeted_threat": "threat >= 0.50 with identity/sexual exclusions",
            "abusive_words": "insult >= 0.50 and threat < 0.20 with identity/sexual exclusions",
            "safe_or_other": "all relevant annotation scores <= 0.10",
        },
        "excluded_policy_boundaries": [
            "identity_attack >= 0.50",
            "sexual_explicit >= 0.50",
            "ambiguous annotation scores",
        ],
        "splits": split_reports,
        "file_sha256": file_hashes,
        "data_governance": {
            "test_split_must_not_be_used_for_training": True,
            "test_split_must_not_be_added_to_rag": True,
            "public_dataset_files_should_not_be_committed_to_github": True,
            "raw_text_is_stored_locally_under_the_source_license": True,
        },
        "limitations": (
            "Individual comments do not validate repeated harassment, coordinated "
            "campaigns, or continued unwanted contact."
        ),
    }
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\nCIVIL COMMENTS CYBER/ABUSIVE IMPORT")
    print("=" * 60)
    for split in ("train", "validation", "test"):
        values = split_reports[split]
        print(f"{split.title()}: {values['records']} records")
        for label, count in values["label_counts"].items():
            print(f"  {label}: {count}")
    print(f"\nOutput: {OUTPUT_DIR}")
    print(f"Manifest: {manifest_path}")
    print("Licence: CC0-1.0")
    print("The test split is evaluation-only and must never enter training or RAG.")


if __name__ == "__main__":
    main()
