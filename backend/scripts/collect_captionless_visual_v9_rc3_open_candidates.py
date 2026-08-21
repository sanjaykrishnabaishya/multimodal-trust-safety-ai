from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


USER_AGENT = (
    "TrustScopeAI-OpenAccessCandidateCollector/2026.08 "
    "(development candidates only; no automatic labels or training)"
)
MET_SEARCH_URL = "https://collectionapi.metmuseum.org/public/collection/v1/search"
MET_OBJECT_URL = "https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}"
AIC_SEARCH_URL = "https://api.artic.edu/api/v1/artworks/search"
AIC_IIIF_BASE = "https://www.artic.edu/iiif/2"

MET_QUERIES = (
    "nude figure",
    "nude sculpture",
    "kiss",
    "anatomy",
    "body horror",
)
AIC_QUERIES = MET_QUERIES
LOC_PUBLIC_DOMAIN_FILM_TITLES = (
    "St. Louis Blues",
    "Popeye the Sailor Meets Sindbad the Sailor",
    "The House I Live In",
    "The Middleton Family at the New York World's Fair",
    "Modesta",
    "Master Hands",
    "The Memphis Belle: A Story of a Flying Fortress",
    "All My Babies: A Midwife's Own Story",
    "Under Western Stars",
    "Duck and Cover",
    "The Hitch-Hiker",
    "Trance and Dance in Bali",
    "Within Our Gates",
    "San Francisco Earthquake and Fire, April 18, 1906",
    "President McKinley Taking the Oath",
    "The Great Train Robbery",
    "Panorama of Machine Co. Aisle, Westinghouse Co. Works",
    "May Irwin Kiss",
)
LOC_CURATED_PAGE = (
    "https://www.loc.gov/free-to-use/"
    "public-domain-films-from-the-national-film-registry"
)

MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
SAFE_IDENTIFIER = re.compile(r"[^A-Za-z0-9_.-]+")


def default_output_root() -> Path:
    return (
        Path.home()
        / "Documents"
        / "TrustScopeAI Private Datasets"
        / "captionless-visual-v9-rc3-open-candidates"
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _safe_name(value: str) -> str:
    cleaned = SAFE_IDENTIFIER.sub("-", value).strip("-.")
    return cleaned[:120] or "candidate"


def _https_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlparse(url)
    return url if parsed.scheme == "https" and parsed.netloc else ""


def request_bytes(
    url: str,
    *,
    timeout: int = 45,
    maximum_bytes: int = MAX_DOWNLOAD_BYTES,
    attempts: int = 4,
) -> tuple[bytes, str]:
    if not _https_url(url):
        raise ValueError(f"Only absolute HTTPS URLs are permitted: {url}")
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > maximum_bytes:
                    raise RuntimeError(f"Response exceeds size limit: {url}")
                payload = response.read(maximum_bytes + 1)
                if len(payload) > maximum_bytes:
                    raise RuntimeError(f"Response exceeds size limit: {url}")
                return payload, str(response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in {429, 500, 502, 503, 504}:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            delay = min(60.0, float(retry_after or (2 ** attempt)))
            print(f"HTTP {error.code}; retrying in {delay:.0f} seconds: {url}")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            time.sleep(min(15.0, float(2 ** attempt)))
    raise RuntimeError(f"Request failed after retries: {url}") from last_error


def request_json(url: str) -> dict[str, Any]:
    payload, _ = request_bytes(url, maximum_bytes=10 * 1024 * 1024)
    value = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return value


def validate_image(payload: bytes) -> tuple[str, int, int]:
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(payload)) as image:
        image.verify()
    with Image.open(BytesIO(payload)) as image:
        width, height = image.size
        image_format = str(image.format or "").upper()
    if width < 128 or height < 128:
        raise ValueError("Image is too small for a visual candidate.")
    allowed = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
    if image_format not in allowed:
        raise ValueError(f"Unsupported image format: {image_format}")
    return allowed[image_format], int(width), int(height)


def write_media(
    *,
    payload: bytes,
    media_directory: Path,
    source: str,
    source_id: str,
) -> tuple[str, str, int, int, int]:
    extension, width, height = validate_image(payload)
    digest = _sha256_bytes(payload)
    filename = f"{_safe_name(source)}-{_safe_name(source_id)}-{digest[:12]}{extension}"
    destination = media_directory / filename
    if not destination.exists():
        destination.write_bytes(payload)
    return filename, digest, len(payload), width, height


def existing_media_payload(
    *, media_directory: Path, source: str, source_id: str
) -> bytes | None:
    prefix = f"{_safe_name(source)}-{_safe_name(source_id)}-"
    candidates = sorted(
        path
        for path in media_directory.glob(f"{prefix}*")
        if path.is_file()
    )
    for candidate in candidates:
        try:
            payload = candidate.read_bytes()
            validate_image(payload)
            return payload
        except (OSError, ValueError):
            continue
    return None


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def base_record(
    *, source: str, source_id: str, search_bucket: str
) -> dict[str, Any]:
    return {
        "candidate_id": f"{source}:{source_id}",
        "source": source,
        "source_id": source_id,
        "search_bucket": search_bucket,
        "search_bucket_is_ground_truth": False,
        "review_status": "pending_human_rights_and_boundary_review",
        "approved_boundary": "",
        "rights_verified": False,
        "boundary_verified": False,
        "training_allowed": False,
        "calibration_allowed": False,
        "independent_holdout_allowed": False,
        "automatic_moderation_allowed": False,
        "adult_status_verified": False,
        "model_release_verified": False,
        "privacy_and_publicity_review_complete": False,
    }


def collect_met(
    *,
    output_root: Path,
    limit_per_query: int,
    metadata_only: bool,
    seen_ids: set[str],
    bucket_counts: Counter[tuple[str, str]],
    checkpoint_path: Path,
) -> list[dict[str, Any]]:
    media_directory = output_root / "media"
    records: list[dict[str, Any]] = []
    for query in MET_QUERIES:
        accepted_for_query = bucket_counts[("met", query)]
        if accepted_for_query >= limit_per_query:
            print(
                f"Met bucket already complete: {query} "
                f"({accepted_for_query}/{limit_per_query})"
            )
            continue
        parameters = urllib.parse.urlencode({"hasImages": "true", "q": query})
        try:
            search = request_json(f"{MET_SEARCH_URL}?{parameters}")
        except urllib.error.HTTPError as error:
            if error.code == 403:
                print(
                    "Met API is temporarily returning HTTP 403. "
                    "Met collection is paused; continuing with other sources."
                )
                return records
            print(f"Skipped unavailable Met search bucket {query}: HTTP {error.code}")
            continue
        except (RuntimeError, ValueError, json.JSONDecodeError) as error:
            print(f"Skipped unavailable Met search bucket {query}: {error}")
            continue
        object_ids = search.get("objectIDs") or []
        consecutive_forbidden = 0
        for object_id in object_ids:
            if accepted_for_query >= limit_per_query:
                break
            candidate_id = f"met:{object_id}"
            if candidate_id in seen_ids:
                continue
            time.sleep(0.08)
            item_url = MET_OBJECT_URL.format(object_id=int(object_id))
            try:
                item = request_json(item_url)
            except urllib.error.HTTPError as error:
                if error.code == 403:
                    consecutive_forbidden += 1
                    print(
                        f"Skipped inaccessible Met object {object_id} "
                        f"(HTTP {error.code})."
                    )
                    if consecutive_forbidden >= 3:
                        print(
                            "Met returned three consecutive HTTP 403 responses. "
                            "Met collection is paused; continuing with other sources."
                        )
                        return records
                    continue
                print(
                    f"Skipped inaccessible Met object {object_id} "
                    f"(HTTP {error.code})."
                )
                continue
            except (RuntimeError, ValueError, json.JSONDecodeError) as error:
                print(f"Skipped unreadable Met object {object_id}: {error}")
                continue
            consecutive_forbidden = 0
            if item.get("isPublicDomain") is not True:
                continue
            media_url = _https_url(item.get("primaryImageSmall"))
            if not media_url:
                continue
            record = base_record(
                source="met", source_id=str(object_id), search_bucket=query
            )
            record.update(
                {
                    "title": _clean_text(item.get("title")),
                    "object_type": _clean_text(item.get("objectName")),
                    "classification": _clean_text(item.get("classification")),
                    "source_record_url": _https_url(item.get("objectURL")),
                    "source_api_url": item_url,
                    "media_url": media_url,
                    "rights_status": "public_domain_open_access",
                    "rights_statement_url": "https://metmuseum.github.io/",
                    "permission_request_required": False,
                    "media_downloaded": False,
                    "relative_media_path": "",
                    "media_sha256": "",
                    "media_size_bytes": 0,
                    "width": 0,
                    "height": 0,
                }
            )
            if not metadata_only:
                try:
                    payload = existing_media_payload(
                        media_directory=media_directory,
                        source="met",
                        source_id=str(object_id),
                    )
                    if payload is None:
                        payload, _ = request_bytes(media_url)
                    filename, digest, size, width, height = write_media(
                        payload=payload,
                        media_directory=media_directory,
                        source="met",
                        source_id=str(object_id),
                    )
                except Exception as error:  # candidate collection must continue
                    print(f"Skipped inaccessible Met media {object_id}: {error}")
                    continue
                record.update(
                    {
                        "media_downloaded": True,
                        "relative_media_path": f"media/{filename}",
                        "media_sha256": digest,
                        "media_size_bytes": size,
                        "width": width,
                        "height": height,
                    }
                )
            records.append(record)
            seen_ids.add(candidate_id)
            append_jsonl(checkpoint_path, record)
            accepted_for_query += 1
            bucket_counts[("met", query)] += 1
            print(
                f"Collected Met candidate {accepted_for_query}/{limit_per_query} "
                f"for bucket: {query}"
            )
    return records


def collect_aic(
    *,
    output_root: Path,
    limit_per_query: int,
    metadata_only: bool,
    seen_ids: set[str],
    bucket_counts: Counter[tuple[str, str]],
    checkpoint_path: Path,
) -> list[dict[str, Any]]:
    media_directory = output_root / "media"
    records: list[dict[str, Any]] = []
    fields = ",".join(
        (
            "id",
            "title",
            "image_id",
            "is_public_domain",
            "classification_title",
            "artwork_type_title",
            "date_display",
            "artist_display",
            "api_link",
        )
    )
    for query in AIC_QUERIES:
        accepted_for_query = bucket_counts[("aic", query)]
        if accepted_for_query >= limit_per_query:
            print(
                f"AIC bucket already complete: {query} "
                f"({accepted_for_query}/{limit_per_query})"
            )
            continue
        parameters = urllib.parse.urlencode(
            {
                "q": query,
                "query[term][is_public_domain]": "true",
                "limit": min(100, max(limit_per_query * 3, 20)),
                "fields": fields,
            }
        )
        try:
            response = request_json(f"{AIC_SEARCH_URL}?{parameters}")
        except (urllib.error.HTTPError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            print(f"Skipped unavailable AIC search bucket {query}: {error}")
            continue
        for item in response.get("data") or []:
            if accepted_for_query >= limit_per_query:
                break
            if not isinstance(item, dict) or item.get("is_public_domain") is not True:
                continue
            object_id = str(item.get("id", "")).strip()
            image_id = str(item.get("image_id", "")).strip()
            candidate_id = f"aic:{object_id}"
            if not object_id or not image_id or candidate_id in seen_ids:
                continue
            media_url = f"{AIC_IIIF_BASE}/{urllib.parse.quote(image_id)}/full/843,/0/default.jpg"
            record = base_record(
                source="aic", source_id=object_id, search_bucket=query
            )
            record.update(
                {
                    "title": _clean_text(item.get("title")),
                    "object_type": _clean_text(item.get("artwork_type_title")),
                    "classification": _clean_text(item.get("classification_title")),
                    "source_record_url": f"https://www.artic.edu/artworks/{object_id}",
                    "source_api_url": _https_url(item.get("api_link")),
                    "media_url": media_url,
                    "rights_status": "cc0_public_domain_record",
                    "rights_statement_url": "https://www.artic.edu/open-access",
                    "permission_request_required": False,
                    "media_downloaded": False,
                    "relative_media_path": "",
                    "media_sha256": "",
                    "media_size_bytes": 0,
                    "width": 0,
                    "height": 0,
                }
            )
            if not metadata_only:
                time.sleep(1.0)
                try:
                    payload = existing_media_payload(
                        media_directory=media_directory,
                        source="aic",
                        source_id=object_id,
                    )
                    if payload is None:
                        payload, _ = request_bytes(media_url)
                    filename, digest, size, width, height = write_media(
                        payload=payload,
                        media_directory=media_directory,
                        source="aic",
                        source_id=object_id,
                    )
                except Exception as error:
                    print(f"Skipped inaccessible AIC media {object_id}: {error}")
                    continue
                record.update(
                    {
                        "media_downloaded": True,
                        "relative_media_path": f"media/{filename}",
                        "media_sha256": digest,
                        "media_size_bytes": size,
                        "width": width,
                        "height": height,
                    }
                )
            records.append(record)
            seen_ids.add(candidate_id)
            append_jsonl(checkpoint_path, record)
            accepted_for_query += 1
            bucket_counts[("aic", query)] += 1
            print(
                f"Collected AIC candidate {accepted_for_query}/{limit_per_query} "
                f"for bucket: {query}"
            )
    return records


def collect_loc_references(seen_ids: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, title in enumerate(LOC_PUBLIC_DOMAIN_FILM_TITLES, start=1):
        source_id = f"curated-film-{index:03d}"
        candidate_id = f"loc-film-reference:{source_id}"
        if candidate_id in seen_ids:
            continue
        record = base_record(
            source="loc-film-reference",
            source_id=source_id,
            search_bucket="official_public_domain_film_selection",
        )
        record.update(
            {
                "title": title,
                "object_type": "film_reference",
                "classification": "public_domain_film_candidate",
                "source_record_url": LOC_CURATED_PAGE,
                "source_api_url": "",
                "media_url": "",
                "rights_status": "pending_item_level_rights_verification",
                "rights_statement_url": LOC_CURATED_PAGE,
                "permission_request_required": False,
                "media_downloaded": False,
                "relative_media_path": "",
                "media_sha256": "",
                "media_size_bytes": 0,
                "width": 0,
                "height": 0,
                "manual_item_resolution_required": True,
            }
        )
        records.append(record)
        seen_ids.add(candidate_id)
    return records


def read_existing(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_review_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fields = (
        "candidate_id",
        "source",
        "source_id",
        "title",
        "search_bucket",
        "source_record_url",
        "rights_status",
        "relative_media_path",
        "media_sha256",
        "review_status",
        "rights_verified",
        "boundary_verified",
        "approved_boundary",
        "adult_status_verified",
        "model_release_verified",
        "privacy_and_publicity_review_complete",
        "training_allowed",
        "calibration_allowed",
        "independent_holdout_allowed",
        "review_notes",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({**record, "review_notes": ""})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect public-domain art candidates and public-domain film "
            "references for manual RC3 review."
        )
    )
    parser.add_argument("--output-root", type=Path, default=default_output_root())
    parser.add_argument("--limit-per-query", type=int, default=20)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=("met", "aic", "loc"),
        default=("met", "aic", "loc"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.limit_per_query <= 100:
        raise ValueError("--limit-per-query must be between 1 and 100.")
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "media").mkdir(parents=True, exist_ok=True)
    jsonl_path = output_root / "candidates.jsonl"
    review_path = output_root / "candidate_review.csv"
    report_path = output_root / "collection_report.json"

    existing = read_existing(jsonl_path)
    seen_ids = {str(item.get("candidate_id", "")) for item in existing}
    bucket_counts: Counter[tuple[str, str]] = Counter(
        (
            str(item.get("source", "")),
            str(item.get("search_bucket", "")),
        )
        for item in existing
    )
    additions: list[dict[str, Any]] = []
    if "met" in args.sources:
        additions.extend(
            collect_met(
                output_root=output_root,
                limit_per_query=args.limit_per_query,
                metadata_only=args.metadata_only,
                seen_ids=seen_ids,
                bucket_counts=bucket_counts,
                checkpoint_path=jsonl_path,
            )
        )
    if "aic" in args.sources:
        additions.extend(
            collect_aic(
                output_root=output_root,
                limit_per_query=args.limit_per_query,
                metadata_only=args.metadata_only,
                seen_ids=seen_ids,
                bucket_counts=bucket_counts,
                checkpoint_path=jsonl_path,
            )
        )
    if "loc" in args.sources:
        loc_additions = collect_loc_references(seen_ids)
        for record in loc_additions:
            append_jsonl(jsonl_path, record)
        additions.extend(loc_additions)

    all_records = existing + additions
    write_jsonl(jsonl_path, all_records)
    write_review_csv(review_path, all_records)
    source_counts = Counter(str(item.get("source", "")) for item in all_records)
    media_count = sum(item.get("media_downloaded") is True for item in all_records)
    report = {
        "candidate_package": "captionless-visual-v9-rc3-open-candidates",
        "records": len(all_records),
        "new_records": len(additions),
        "source_counts": dict(sorted(source_counts.items())),
        "media_downloaded_records": media_count,
        "metadata_only": bool(args.metadata_only),
        "output_root": str(output_root),
        "review_csv": str(review_path),
        "candidate_jsonl": str(jsonl_path),
        "approved_records": 0,
        "automatic_labels_created": False,
        "search_query_used_as_ground_truth": False,
        "training_allowed": False,
        "calibration_allowed": False,
        "independent_evaluation_allowed": False,
        "automatic_moderation_allowed": False,
        "explicit_real_person_media_collected": False,
        "modern_film_or_television_media_collected": False,
        "raw_user_examples_copied": False,
        "human_rights_and_boundary_review_required": True,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("CAPTIONLESS VISUAL V9 RC3 OPEN CANDIDATE COLLECTION")
    print("=" * 60)
    print(f"Records: {len(all_records)}")
    print(f"New records: {len(additions)}")
    for source, count in sorted(source_counts.items()):
        print(f"  {source}: {count}")
    print(f"Media downloaded: {media_count}")
    print(f"Candidates: {jsonl_path}")
    print(f"Private review CSV: {review_path}")
    print(f"Report: {report_path}")
    print("Approved records: 0")
    print("Search queries used as ground truth: False")
    print("Training or calibration allowed: False")
    print("Independent evaluation allowed: False")
    print("Explicit real-person media collected: False")
    print("Modern film or television media collected: False")
    print("Review every record before assigning a boundary or dataset role.")


if __name__ == "__main__":
    main()
