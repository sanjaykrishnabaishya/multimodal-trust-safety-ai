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
OUTPUT_DIRECTORY = ROOT / "datasets" / "public" / "civil_comments_hate_rc2"
CYBER_DIRECTORY = ROOT / "datasets" / "public" / "civil_comments_cyber"
HATEXPLAIN_DIRECTORY = ROOT / "datasets" / "public" / "hatexplain"
LABELS = ("hate_speech", "abusive_words", "safe_or_other")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-per-label", type=int, default=1_000)
    parser.add_argument("--validation-hate", type=int, default=60)
    parser.add_argument("--validation-comparison", type=int, default=200)
    parser.add_argument("--test-hate", type=int, default=50)
    parser.add_argument("--test-comparison", type=int, default=100)
    parser.add_argument("--max-scan", type=int, default=2_000_000)
    return parser.parse_args()


def score(record: dict[str, Any], key: str) -> float:
    try:
        return float(record.get(key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def normalized_text_hash(text: str) -> str:
    normalized = " ".join(str(text or "").casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_excluded_hashes() -> tuple[set[str], dict[str, int]]:
    excluded: set[str] = set()
    counts: Counter[str] = Counter()

    for split in ("train", "validation", "test"):
        path = CYBER_DIRECTORY / f"{split}.csv"
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                digest = str(row.get("source_text_sha256", "")).strip()
                if not digest:
                    digest = normalized_text_hash(row.get("text", ""))
                excluded.add(digest)
                counts[f"civil_comments_cyber_{split}"] += 1

    for split in ("train", "validation", "test"):
        path = HATEXPLAIN_DIRECTORY / f"{split}.csv"
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                excluded.add(normalized_text_hash(row.get("text", "")))
                counts[f"hatexplain_{split}"] += 1

    return excluded, dict(sorted(counts.items()))


def map_label(record: dict[str, Any]) -> str | None:
    identity_attack = score(record, "identity_attack")
    insult = score(record, "insult")
    threat = score(record, "threat")
    toxicity = score(record, "toxicity")
    severe_toxicity = score(record, "severe_toxicity")
    obscene = score(record, "obscene")
    sexual_explicit = score(record, "sexual_explicit")

    # The Hugging Face default configuration exposes the aggregate
    # identity_attack annotation, but not individual protected-class columns.
    # A strict identity-attack threshold therefore defines this source label.
    if (
        identity_attack >= 0.70
        and sexual_explicit < 0.50
    ):
        return "hate_speech"

    # Personal or general insults are Abusive Words only when identity signals,
    # sexual content, and physical threats are absent.
    if (
        insult >= 0.60
        and identity_attack <= 0.10
        and threat <= 0.10
        and sexual_explicit <= 0.10
    ):
        return "abusive_words"

    if (
        toxicity <= 0.08
        and severe_toxicity <= 0.08
        and obscene <= 0.08
        and threat <= 0.08
        and insult <= 0.08
        and identity_attack <= 0.08
        and sexual_explicit <= 0.08
    ):
        return "safe_or_other"

    return None


def collect_split(
    *,
    split: str,
    quotas: dict[str, int],
    max_scan: int,
    excluded_hashes: set[str],
    selected_hashes: set[str],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    stream = load_dataset(
        DATASET_NAME,
        split=split,
        streaming=True,
        revision=DATASET_REVISION,
    ).shuffle(seed=20260811, buffer_size=20_000)

    selected: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    statistics: Counter[str] = Counter()
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
            statistics["ambiguous_or_out_of_scope"] += 1
            continue
        if counts[label] >= quotas[label]:
            continue

        digest = normalized_text_hash(text)
        if digest in excluded_hashes:
            statistics["previously_used_hash_excluded"] += 1
            continue
        if digest in selected_hashes:
            statistics["duplicate_hash_excluded"] += 1
            continue

        selected_hashes.add(digest)
        counts[label] += 1
        selected.append(
            {
                "record_id": f"civil-hate-{split}-{digest[:16]}",
                "split": split,
                "label": label,
                "text": text,
                "source_text_sha256": digest,
            }
        )

        if scanned % 25_000 == 0:
            print(f"  scanned {scanned:,}: {dict(counts)}")
        if all(counts[label_name] >= quotas[label_name] for label_name in LABELS):
            break

    missing = {
        label: quotas[label] - counts[label]
        for label in LABELS
        if counts[label] < quotas[label]
    }
    if missing:
        raise RuntimeError(
            f"The {split} split did not provide the requested quota. "
            f"Missing: {missing}. Scanned: {statistics['scanned']:,}."
        )
    return selected, dict(statistics)


def main() -> None:
    args = parse_args()
    split_quotas = {
        "train": {
            label: args.train_per_label
            for label in LABELS
        },
        "validation": {
            "hate_speech": args.validation_hate,
            "abusive_words": args.validation_comparison,
            "safe_or_other": args.validation_comparison,
        },
        "test": {
            "hate_speech": args.test_hate,
            "abusive_words": args.test_comparison,
            "safe_or_other": args.test_comparison,
        },
    }
    if any(
        value <= 0
        for quotas in split_quotas.values()
        for value in quotas.values()
    ):
        raise ValueError("Every class-specific quota must be positive.")

    excluded_hashes, exclusion_sources = load_excluded_hashes()
    selected_hashes: set[str] = set()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    split_reports: dict[str, Any] = {}
    file_hashes: dict[str, str] = {}
    for split in ("train", "validation", "test"):
        rows, statistics = collect_split(
            split=split,
            quotas=split_quotas[split],
            max_scan=args.max_scan,
            excluded_hashes=excluded_hashes,
            selected_hashes=selected_hashes,
        )
        path = OUTPUT_DIRECTORY / f"{split}.csv"
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
                "training"
                if split == "train"
                else "threshold_selection_only"
                if split == "validation"
                else "independent_evaluation_only"
            ),
        }
        file_hashes[path.name] = file_sha256(path)

    manifest = {
        "dataset_name": "Civil Comments Hate Speech RC2",
        "source_dataset": DATASET_NAME,
        "source_revision": DATASET_REVISION,
        "source_url": "https://huggingface.co/datasets/google/civil_comments",
        "license": "CC0-1.0",
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "language": "English",
        "labels": list(LABELS),
        "mapping": {
            "hate_speech": (
                "identity_attack >= 0.70 using the source dataset's aggregate "
                "identity-attack annotation"
            ),
            "abusive_words": (
                "insult >= 0.60 with identity, protected-attribute, threat, and "
                "sexual exclusions"
            ),
            "safe_or_other": "all relevant policy scores <= 0.08",
        },
        "source_schema_note": (
            "The Hugging Face default Civil Comments configuration exposes "
            "identity_attack but does not expose protected-class subtype columns."
        ),
        "excluded_previous_hash_count": len(excluded_hashes),
        "exclusion_sources": exclusion_sources,
        "splits": split_reports,
        "requested_split_quotas": split_quotas,
        "file_sha256": file_hashes,
        "data_governance": {
            "test_split_must_not_be_used_for_training": True,
            "test_split_must_not_be_used_for_threshold_selection": True,
            "test_split_must_not_be_added_to_rag": True,
            "test_split_must_not_be_inspected_before_freeze": True,
            "public_dataset_files_should_not_be_committed_to_github": True,
            "raw_text_is_stored_locally_under_the_source_license": True,
        },
        "policy_boundary": {
            "protected_group_attack": "Hate Speech & Discrimination",
            "personal_insult_without_protected_target": "Abusive Words",
            "repeated_or_coordinated_personal_attack": (
                "Cyberbullying & Harassment, handled by a separate specialist"
            ),
            "uncertain": "Refer to human review",
        },
        "limitations": [
            "Civil Comments identity annotations do not cover every protected class or jurisdiction.",
            "Protected-class subtype performance requires a separate boundary dataset.",
            "This message-level dataset cannot establish repeated or coordinated harassment.",
            "Passing this component test will not establish overall application accuracy.",
        ],
    }
    manifest_path = OUTPUT_DIRECTORY / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("CIVIL COMMENTS HATE SPEECH RC2 IMPORT")
    print("=" * 60)
    for split in ("train", "validation", "test"):
        values = split_reports[split]
        print(f"{split.title()}: {values['records']:,} records")
        for label, count in values["label_counts"].items():
            print(f"  {label}: {count:,}")
    print(f"Previously used hashes excluded: {len(excluded_hashes):,}")
    print(f"Output: {OUTPUT_DIRECTORY}")
    print(f"Manifest: {manifest_path}")
    print("Licence: CC0-1.0")
    print("The new test split is reserved for one independent evaluation.")
    print("Do not inspect it, train on it, calibrate on it, or add it to RAG.")


if __name__ == "__main__":
    main()
