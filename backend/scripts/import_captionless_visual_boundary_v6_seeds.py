from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = ROOT / "datasets" / "development" / "captionless_visual_boundary_v6"
MANIFEST_PATH = OUTPUT_DIRECTORY / "seed_manifest.json"
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_boundary_v6_seed_import"
    / "report.json"
)
DOWNLOADS = Path.home() / "Downloads"

SEEDS: tuple[dict[str, Any], ...] = (
    {
        "filename": "my-work-original-painting-art-realism-watercolor-female-v0-9zwrn5fn70ic1.webp",
        "boundary": "verified_art_culture_or_education",
        "expected_category": "Normal/Ignore",
        "expected_action": "Allow",
        "human_review_required": False,
        "context_type": "recognized_artwork",
    },
    {
        "filename": "amedeo_modigliani_012.jpg",
        "boundary": "verified_art_culture_or_education",
        "expected_category": "Normal/Ignore",
        "expected_action": "Allow",
        "human_review_required": False,
        "context_type": "recognized_artwork",
    },
    {
        "filename": "images.jpg",
        "boundary": "verified_art_culture_or_education",
        "expected_category": "Normal/Ignore",
        "expected_action": "Allow",
        "human_review_required": False,
        "context_type": "recognized_monument",
    },
    {
        "filename": "image3_temp-130.jpg",
        "boundary": "non_explicit_intimacy",
        "expected_category": "Uncertain",
        "expected_action": "Allow with sensitive-content warning and refer to human review",
        "human_review_required": True,
        "context_type": "live_action_intimacy",
    },
    {
        "filename": "12.jpg",
        "boundary": "non_explicit_intimacy",
        "expected_category": "Uncertain",
        "expected_action": "Allow with sensitive-content warning and refer to human review",
        "human_review_required": True,
        "context_type": "live_action_intimacy",
    },
    {
        "filename": "image2_temp-130.jpg",
        "boundary": "non_explicit_intimacy",
        "expected_category": "Uncertain",
        "expected_action": "Allow with sensitive-content warning and refer to human review",
        "human_review_required": True,
        "context_type": "live_action_intimacy",
    },
    {
        "filename": "gif_-_alexis_knapp_naked_sex_scene_project_x_1285978955.gif",
        "boundary": "explicit_adult_sexual_content",
        "expected_category": "Graphic, Obscene & Sexual Content",
        "expected_action": "Age-restrict/block distribution",
        "human_review_required": False,
        "context_type": "live_action_explicit",
    },
    {
        "filename": "images (1).jpg",
        "boundary": "explicit_adult_sexual_content",
        "expected_category": "Graphic, Obscene & Sexual Content",
        "expected_action": "Age-restrict/block distribution",
        "human_review_required": False,
        "context_type": "live_action_explicit",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    records: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for index, seed in enumerate(SEEDS, start=1):
        path = DOWNLOADS / str(seed["filename"])
        if not path.is_file():
            raise FileNotFoundError(f"Required user-supplied seed is missing: {path}")
        digest = sha256_file(path)
        if digest in seen_hashes:
            raise RuntimeError(f"Duplicate seed content detected: {seed['filename']}")
        seen_hashes.add(digest)
        records.append(
            {
                "record_id": f"CAPTIONLESS-V6-SEED-{index:03d}",
                "filename": seed["filename"],
                "content_sha256": digest,
                "file_size_bytes": path.stat().st_size,
                "media_type": "video" if path.suffix.lower() == ".gif" else "image",
                "boundary": seed["boundary"],
                "context_type": seed["context_type"],
                "expected_category": seed["expected_category"],
                "expected_action": seed["expected_action"],
                "human_review_required": seed["human_review_required"],
                "label_source": "user_confirmed_policy_boundary",
                "raw_media_copied": False,
                "training_allowed": False,
                "evaluation_seed_only": True,
                "redistribution_allowed": False,
                "license_status": "unknown_user_supplied",
            }
        )

    boundary_counts = {
        boundary: sum(item["boundary"] == boundary for item in records)
        for boundary in sorted({str(item["boundary"]) for item in records})
    }
    manifest = {
        "dataset": "captionless_visual_boundary_v6_seeds",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "boundary_counts": boundary_counts,
        "content_hash_sha256": canonical_hash(records),
        "records": records,
        "raw_media_copied": False,
        "raw_media_stored_in_repository": False,
        "training_allowed": False,
        "evaluation_seed_only": True,
        "redistribution_allowed": False,
        "external_or_restricted_data_imported": False,
        "connected_to_live_moderation": False,
    }
    write_json(MANIFEST_PATH, manifest)
    write_json(REPORT_PATH, manifest)

    print("CAPTIONLESS VISUAL BOUNDARY V6 SEED IMPORT")
    print("=" * 60)
    print(f"Records: {len(records)}")
    print("\nBOUNDARY COUNTS")
    print("-" * 60)
    for boundary, count in boundary_counts.items():
        print(f"{boundary}: {count}")
    print(f"\nContent SHA-256: {manifest['content_hash_sha256']}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("Raw media copied or stored: False")
    print("Training allowed: False")
    print("Evaluation seed only: True")
    print("Redistribution allowed: False")
    print("Connected to live moderation: False")


if __name__ == "__main__":
    main()
