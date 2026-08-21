from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = ROOT / "datasets" / "public" / "wikidata_screen_works_v1"
RECORDS_PATH = OUTPUT_DIRECTORY / "records.json"
MANIFEST_PATH = OUTPUT_DIRECTORY / "manifest.json"
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "wikidata_screen_works_v1_import"
    / "import_report.json"
)
API_ENDPOINT = "https://www.wikidata.org/w/api.php"
USER_AGENT = "TrustScopeAI-screen-media-catalog/1.0 (CC0 structured-data import)"
LICENSE = "CC0-1.0"
DEFAULT_TITLES = ("Titanic", "Outlander")
WORK_TYPE_QIDS = {
    "Q11424": "film",
    "Q5398426": "television_series",
}
QID_PATTERN = re.compile(r"^Q[1-9][0-9]*$")
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a CC0 Wikidata cache for exact film/series title candidates."
    )
    parser.add_argument(
        "--title",
        action="append",
        default=[],
        help="Additional title to retrieve; may be repeated.",
    )
    return parser.parse_args()


def clean(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split())


def key(value: object) -> str:
    return clean(value).casefold()


def fetch_json(parameters: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    url = API_ENDPOINT + "?" + urlencode({**parameters, "format": "json", "origin": "*"})
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("Wikidata response exceeded the safety limit.")
                document = json.loads(payload.decode("utf-8"))
                if not isinstance(document, dict):
                    raise RuntimeError("Wikidata returned a non-object JSON response.")
                return document, {
                    "http_status": response.status,
                    "response_bytes": len(payload),
                    "response_sha256": hashlib.sha256(payload).hexdigest(),
                    "attempts": attempt + 1,
                }
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 503} or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After", "3")
            try:
                delay = max(1, min(30, int(retry_after)))
            except ValueError:
                delay = 3
            time.sleep(delay)
        except (URLError, TimeoutError, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Wikidata entity retrieval failed: {last_error}")


def search_qids(title: str) -> tuple[list[str], dict[str, Any]]:
    document, audit = fetch_json(
        {
            "action": "wbsearchentities",
            "search": title,
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": "20",
        }
    )
    qids = [
        str(item.get("id", ""))
        for item in document.get("search", [])
        if isinstance(item, dict) and QID_PATTERN.fullmatch(str(item.get("id", "")))
    ]
    return list(dict.fromkeys(qids)), audit


def entity_documents(qids: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not qids:
        return {}, {"http_status": None, "response_bytes": 0, "attempts": 0}
    document, audit = fetch_json(
        {
            "action": "wbgetentities",
            "ids": "|".join(qids[:50]),
            "props": "labels|aliases|claims",
            "languages": "en",
            "languagefallback": "1",
        }
    )
    entities = document.get("entities", {})
    return (entities if isinstance(entities, dict) else {}), audit


def claim_entity_ids(entity: dict[str, Any], property_id: str) -> list[str]:
    claims = entity.get("claims", {})
    statements = claims.get(property_id, []) if isinstance(claims, dict) else []
    result: list[str] = []
    for statement in statements:
        try:
            value = statement["mainsnak"]["datavalue"]["value"]["id"]
        except (KeyError, TypeError):
            continue
        if QID_PATTERN.fullmatch(str(value)):
            result.append(str(value))
    return result


def release_year(entity: dict[str, Any]) -> int | None:
    claims = entity.get("claims", {})
    statements = claims.get("P577", []) if isinstance(claims, dict) else []
    years: list[int] = []
    for statement in statements:
        try:
            timestamp = str(statement["mainsnak"]["datavalue"]["value"]["time"])
        except (KeyError, TypeError):
            continue
        match = re.match(r"^[+-](\d{4,})-", timestamp)
        if match:
            years.append(int(match.group(1)))
    return min(years) if years else None


def entity_record(qid: str, entity: dict[str, Any], searched_title: str) -> dict[str, Any] | None:
    labels = entity.get("labels", {})
    label_value = labels.get("en", {}) if isinstance(labels, dict) else {}
    title = clean(label_value.get("value", "") if isinstance(label_value, dict) else "")
    aliases_value = entity.get("aliases", {})
    english_aliases = aliases_value.get("en", []) if isinstance(aliases_value, dict) else []
    aliases = sorted(
        {
            clean(item.get("value", ""))
            for item in english_aliases
            if isinstance(item, dict) and clean(item.get("value", ""))
        },
        key=str.casefold,
    )
    exact_names = {key(title), *(key(alias) for alias in aliases)}
    if not title or key(searched_title) not in exact_names:
        return None
    type_qids = claim_entity_ids(entity, "P31")
    matched_types = [WORK_TYPE_QIDS[item] for item in type_qids if item in WORK_TYPE_QIDS]
    if len(set(matched_types)) != 1:
        return None
    return {
        "qid": qid,
        "title": title,
        "aliases": aliases,
        "work_type": matched_types[0],
        "release_year": release_year(entity),
        "source": "wikidata",
        "license": LICENSE,
        "source_url": f"https://www.wikidata.org/wiki/{qid}",
        "retrieved_for_exact_title": searched_title,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    args = parse_args()
    searched_titles = list(
        dict.fromkeys(
            clean(title)
            for title in (*DEFAULT_TITLES, *args.title)
            if clean(title)
        )
    )
    if len(searched_titles) > 100:
        raise ValueError("At most 100 titles may be requested in one import.")

    print("Retrieving exact CC0 screen-work candidates from Wikidata...")
    print("No images, prose, plots, scripts, or subtitles are requested.\n")
    records_by_qid: dict[str, dict[str, Any]] = {}
    source_audit: list[dict[str, Any]] = []
    title_results: dict[str, int] = {}
    for title in searched_titles:
        qids, search_audit = search_qids(title)
        entities, entity_audit = entity_documents(qids)
        accepted = 0
        for qid, entity in entities.items():
            if not QID_PATTERN.fullmatch(str(qid)) or not isinstance(entity, dict):
                continue
            record = entity_record(str(qid), entity, title)
            if record is None:
                continue
            records_by_qid[str(qid)] = record
            accepted += 1
        title_results[title] = accepted
        source_audit.append(
            {
                "title": title,
                "search_candidates": len(qids),
                "accepted_exact_typed_records": accepted,
                "search_request": search_audit,
                "entity_request": entity_audit,
            }
        )

    records = sorted(
        records_by_qid.values(),
        key=lambda item: (item["title"].casefold(), item["release_year"] or 0, item["qid"]),
    )
    if not records:
        raise RuntimeError("No exact film or television-series entities were found.")
    retrieved_at = datetime.now(timezone.utc).isoformat()
    content_hash = canonical_hash(records)
    manifest = {
        "dataset": "wikidata_screen_works_v1",
        "retrieved_at_utc": retrieved_at,
        "record_count": len(records),
        "work_type_counts": {
            work_type: sum(item["work_type"] == work_type for item in records)
            for work_type in sorted(set(WORK_TYPE_QIDS.values()))
        },
        "searched_titles": searched_titles,
        "title_results": title_results,
        "source": "Wikidata structured entity data",
        "source_endpoint": API_ENDPOINT,
        "source_audit": source_audit,
        "license": LICENSE,
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "content_hash_sha256": content_hash,
        "exact_title_or_alias_match_required": True,
        "direct_film_or_television_series_type_required": True,
        "candidate_generation_only": True,
        "confirmed_visual_provenance": 0,
        "creative_media_downloaded": False,
        "wikipedia_prose_downloaded": False,
        "posters_or_stills_downloaded": False,
        "plots_scripts_or_subtitles_downloaded": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    report = {
        **manifest,
        "output_records": str(RECORDS_PATH),
        "output_manifest": str(MANIFEST_PATH),
    }
    write_json(RECORDS_PATH, records)
    write_json(MANIFEST_PATH, manifest)
    write_json(REPORT_PATH, report)

    print("WIKIDATA SCREEN-WORK RAG CATALOG V1 IMPORT")
    print("=" * 60)
    print(f"Titles searched: {len(searched_titles)}")
    print(f"Exact typed records: {len(records)}")
    for title, count in title_results.items():
        print(f"  {title}: {count}")
    print("\nWORK TYPE COUNTS")
    print("-" * 60)
    for work_type, count in manifest["work_type_counts"].items():
        print(f"{work_type}: {count}")
    print(f"\nContent SHA-256: {content_hash}")
    print(f"Records: {RECORDS_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("Licence: CC0-1.0")
    print("Creative media or Wikipedia prose downloaded: False")
    print("Confirmed visual provenance: 0")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("Every result is a retrieval candidate, not proof of uploaded-media provenance.")


if __name__ == "__main__":
    main()
