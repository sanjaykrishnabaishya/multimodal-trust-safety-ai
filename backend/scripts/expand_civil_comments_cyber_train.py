from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone

from scripts.import_civil_comments_cyber import (
    OUTPUT_DIR,
    collect_split,
    file_sha256,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-label", type=int, default=1500)
    parser.add_argument("--max-scan", type=int, default=2_000_000)
    return parser.parse_args()


def load_protected_hashes() -> set[str]:
    hashes: set[str] = set()
    for split in ("validation", "test"):
        path = OUTPUT_DIR / f"{split}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Protected split not found: {path}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                digest = str(row.get("source_text_sha256", "")).strip()
                if digest:
                    hashes.add(digest)
    return hashes


def main() -> None:
    args = parse_args()
    if args.per_label <= 0:
        raise ValueError("--per-label must be positive.")
    manifest_path = OUTPUT_DIR / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Import manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    protected_hashes = load_protected_hashes()
    rows, statistics = collect_split(
        "train",
        args.per_label,
        args.max_scan,
        protected_hashes,
    )
    train_path = OUTPUT_DIR / "train.csv"
    with train_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(row["label"] for row in rows)
    manifest["splits"]["train"] = {
        "records": len(rows),
        "label_counts": dict(sorted(counts.items())),
        "stream_statistics": statistics,
        "usage": "training",
    }
    manifest["file_sha256"]["train.csv"] = file_sha256(train_path)
    manifest["training_expanded_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["training_expansion"] = {
        "per_label": args.per_label,
        "validation_text_used": False,
        "test_text_used": False,
        "validation_and_test_hashes_used_only_for_duplicate_prevention": True,
        "validation_file_modified": False,
        "test_file_modified": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("CIVIL COMMENTS TRAINING EXPANSION")
    print("=" * 60)
    print(f"Training records: {len(rows)}")
    for label, count in sorted(counts.items()):
        print(f"{label}: {count}")
    print(f"Protected validation/test hashes: {len(protected_hashes)}")
    print("Validation file modified: False")
    print("Test file modified: False")
    print(f"Training file: {train_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
