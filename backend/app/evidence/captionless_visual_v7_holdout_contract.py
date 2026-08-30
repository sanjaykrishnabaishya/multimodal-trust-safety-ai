from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


BOUNDARIES = (
    "verified_art_culture_or_education",
    "non_explicit_intimacy",
    "explicit_adult_sexual_content",
)
APPROVED_SOURCE_STATUSES = {"cc0", "public_domain", "user_owned"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
LABEL_COLUMNS = (
    "record_id",
    "relative_path",
    "boundary",
    "source_status",
    "art_context_verified",
    "adult_status_confirmed",
    "visible_explicit_detail",
)
MINIMUM_RECORDS = 60
MINIMUM_PER_BOUNDARY = 20


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
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_bool(value: Any, *, field: str, record_id: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"{record_id}: {field} must be true or false.")


def require_external_holdout_root(holdout_root: Path, repository_root: Path) -> Path:
    root = holdout_root.expanduser().resolve()
    repository = repository_root.resolve()
    if root == repository or root.is_relative_to(repository):
        raise RuntimeError(
            "Raw independent media must remain outside the repository."
        )
    return root


def write_template(holdout_root: Path, repository_root: Path) -> tuple[Path, Path]:
    root = require_external_holdout_root(holdout_root, repository_root)
    media = root / "media"
    labels = root / "labels.csv"
    root.mkdir(parents=True, exist_ok=True)
    media.mkdir(parents=True, exist_ok=True)
    if labels.exists():
        raise FileExistsError(f"The private label template already exists: {labels}")

    rows: list[dict[str, str]] = []
    prefixes = {
        "verified_art_culture_or_education": "ART",
        "non_explicit_intimacy": "INTIMACY",
        "explicit_adult_sexual_content": "EXPLICIT",
    }
    for boundary in BOUNDARIES:
        for index in range(1, MINIMUM_PER_BOUNDARY + 1):
            rows.append(
                {
                    "record_id": f"{prefixes[boundary]}-HOLDOUT-{index:03d}",
                    "relative_path": "",
                    "boundary": boundary,
                    "source_status": "",
                    "art_context_verified": str(
                        boundary == "verified_art_culture_or_education"
                    ).lower(),
                    "adult_status_confirmed": str(
                        boundary == "explicit_adult_sexual_content"
                    ).lower(),
                    "visible_explicit_detail": str(
                        boundary == "explicit_adult_sexual_content"
                    ).lower(),
                }
            )
    with labels.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return labels, media


def _safe_relative_path(value: str, record_id: str) -> Path:
    raw = value.strip().replace("\\", "/")
    path = Path(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{record_id}: relative_path is missing or unsafe.")
    return path


def load_holdout(
    holdout_root: Path,
    repository_root: Path,
    *,
    development_content_hashes: Iterable[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = require_external_holdout_root(holdout_root, repository_root)
    labels_path = root / "labels.csv"
    media_root = root / "media"
    if not labels_path.is_file():
        raise FileNotFoundError(f"Private labels file is missing: {labels_path}")
    if not media_root.is_dir():
        raise FileNotFoundError(f"Private media directory is missing: {media_root}")

    development_hashes = {str(value).lower() for value in development_content_hashes}
    runtime_records: list[dict[str, Any]] = []
    sanitized_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_content: set[str] = set()
    with labels_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != LABEL_COLUMNS:
            raise RuntimeError(
                "labels.csv columns must exactly match the generated template."
            )
        for line_number, row in enumerate(reader, start=2):
            record_id = " ".join(str(row.get("record_id", "")).split())
            if not record_id or record_id in seen_ids:
                raise ValueError(
                    f"labels.csv line {line_number}: missing or duplicate record_id."
                )
            seen_ids.add(record_id)
            relative = _safe_relative_path(str(row["relative_path"]), record_id)
            media_path = (media_root / relative).resolve()
            if not media_path.is_relative_to(media_root.resolve()):
                raise ValueError(f"{record_id}: media path escapes the private root.")
            if media_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                raise ValueError(f"{record_id}: unsupported media extension.")
            if not media_path.is_file():
                raise FileNotFoundError(f"{record_id}: private media file is missing.")

            boundary = str(row["boundary"]).strip()
            if boundary not in BOUNDARIES:
                raise ValueError(f"{record_id}: unknown boundary label.")
            source_status = str(row["source_status"]).strip().lower()
            if source_status not in APPROVED_SOURCE_STATUSES:
                raise ValueError(
                    f"{record_id}: source_status must be cc0, public_domain, "
                    "or user_owned."
                )
            art_verified = parse_bool(
                row["art_context_verified"],
                field="art_context_verified",
                record_id=record_id,
            )
            adult_confirmed = parse_bool(
                row["adult_status_confirmed"],
                field="adult_status_confirmed",
                record_id=record_id,
            )
            explicit_detail = parse_bool(
                row["visible_explicit_detail"],
                field="visible_explicit_detail",
                record_id=record_id,
            )
            if boundary == "verified_art_culture_or_education" and not art_verified:
                raise ValueError(f"{record_id}: art context must be independently verified.")
            if boundary == "non_explicit_intimacy" and explicit_detail:
                raise ValueError(
                    f"{record_id}: non-explicit intimacy cannot contain visible "
                    "explicit detail."
                )
            if boundary == "explicit_adult_sexual_content" and not (
                adult_confirmed and explicit_detail
            ):
                raise ValueError(
                    f"{record_id}: explicit records require confirmed adult status "
                    "and visible explicit detail."
                )

            content_hash = sha256_file(media_path)
            if content_hash in development_hashes:
                raise RuntimeError(f"{record_id}: exact development overlap detected.")
            if content_hash in seen_content:
                raise RuntimeError(f"{record_id}: duplicate holdout content detected.")
            seen_content.add(content_hash)
            relative_text = relative.as_posix()
            sanitized = {
                "record_id": record_id,
                "path_token_sha256": hashlib.sha256(
                    relative_text.encode("utf-8")
                ).hexdigest(),
                "content_sha256": content_hash,
                "file_size_bytes": media_path.stat().st_size,
                "boundary": boundary,
                "source_status": source_status,
                "art_context_verified": art_verified,
                "adult_status_confirmed": adult_confirmed,
                "visible_explicit_detail": explicit_detail,
            }
            sanitized_records.append(sanitized)
            runtime_records.append({**sanitized, "media_path": media_path})

    if len(sanitized_records) < MINIMUM_RECORDS:
        raise RuntimeError(f"At least {MINIMUM_RECORDS} holdout records are required.")
    group_counts = {
        boundary: sum(row["boundary"] == boundary for row in sanitized_records)
        for boundary in BOUNDARIES
    }
    insufficient = {
        key: value for key, value in group_counts.items() if value < MINIMUM_PER_BOUNDARY
    }
    if insufficient:
        raise RuntimeError(
            f"Every boundary requires at least {MINIMUM_PER_BOUNDARY} records: "
            f"{insufficient}"
        )
    sanitized_records.sort(key=lambda item: item["record_id"])
    runtime_records.sort(key=lambda item: item["record_id"])
    challenge = {
        "challenge": "captionless-visual-evidence-v7-rc1-independent",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(sanitized_records),
        "group_counts": group_counts,
        "challenge_sha256": canonical_hash(sanitized_records),
        "labels_file_sha256": sha256_file(labels_path),
        "records_manifest": sanitized_records,
        "raw_media_copied": False,
        "raw_media_stored_in_repository": False,
        "raw_filenames_stored_in_manifest": False,
        "development_overlap": 0,
        "source_statuses_allowed": sorted(APPROVED_SOURCE_STATUSES),
        "user_media_used_for_training": False,
        "evaluation_only": True,
    }
    return challenge, runtime_records
