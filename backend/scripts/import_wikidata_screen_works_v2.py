from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = ROOT / "datasets" / "public" / "wikidata_screen_works_v2"
RECORDS_PATH = OUTPUT_DIRECTORY / "records.json"
MANIFEST_PATH = OUTPUT_DIRECTORY / "manifest.json"
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "wikidata_screen_works_v2_import"
    / "import_report.json"
)
WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
ENTITY_API_ENDPOINT = "https://www.wikidata.org/w/api.php"
USER_AGENT = "TrustScopeAI-screen-media-catalog/2.0 (CC0 structured-data import)"
LICENSE = "CC0-1.0"
DEFAULT_EXACT_TITLES = ("Titanic", "Outlander")
WORK_TYPE_QIDS = {
    "Q11424": "film",
    "Q5398426": "television_series",
}
QID_PATTERN = re.compile(r"^Q[1-9][0-9]*$")
ENTITY_URI_PATTERN = re.compile(r"^https?://www\.wikidata\.org/entity/(Q[1-9][0-9]*)$")
MAX_API_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_SPARQL_RESPONSE_BYTES = 24 * 1024 * 1024
MAX_ALIASES_PER_RECORD = 64
MAX_NAME_LENGTH = 200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a bounded CC0 Wikidata RAG catalog for films and television "
            "series. Catalog matches remain unverified provenance candidates."
        )
    )
    parser.add_argument(
        "--limit-per-type",
        type=int,
        default=1000,
        help="Maximum bulk entities requested for each work type (default: 1000).",
    )
    parser.add_argument(
        "--title",
        action="append",
        default=[],
        help="Exact title supplement; may be repeated.",
    )
    parser.add_argument(
        "--title-file",
        action="append",
        default=[],
        help="UTF-8 text file containing one exact title per line; may be repeated.",
    )
    parser.add_argument(
        "--skip-default-examples",
        action="store_true",
        help="Do not add the Titanic and Outlander exact-title supplements.",
    )
    return parser.parse_args()


def clean(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split())


def key(value: object) -> str:
    return clean(value).casefold()


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


def _read_response(response: Any, maximum_bytes: int) -> tuple[dict[str, Any], bytes]:
    payload = response.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise RuntimeError("Wikidata response exceeded the configured safety limit.")
    document = json.loads(payload.decode("utf-8"))
    if not isinstance(document, dict):
        raise RuntimeError("Wikidata returned a non-object JSON response.")
    return document, payload


def fetch_json(
    endpoint: str,
    parameters: dict[str, str],
    *,
    maximum_bytes: int,
    attempts: int = 5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    url = endpoint + "?" + urlencode(parameters)
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=90) as response:
                document, payload = _read_response(response, maximum_bytes)
                return document, {
                    "http_status": response.status,
                    "response_bytes": len(payload),
                    "response_sha256": hashlib.sha256(payload).hexdigest(),
                    "attempts": attempt + 1,
                }
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 502, 503, 504} or attempt == attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After", "65" if exc.code == 429 else "5")
            try:
                delay = max(2, min(75, int(retry_after)))
            except ValueError:
                delay = 65 if exc.code == 429 else 5
            print(f"Wikidata returned HTTP {exc.code}; retrying in {delay} seconds...")
            time.sleep(delay)
        except (URLError, TimeoutError, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
            delay = min(20, 2 ** attempt)
            print(f"Wikidata request failed; retrying in {delay} seconds...")
            time.sleep(delay)
    raise RuntimeError(f"Wikidata retrieval failed: {last_error}")


def bulk_query(limit_per_type: int) -> str:
    return f"""
SELECT ?item ?workType WHERE {{
  {{
    {{ SELECT DISTINCT ?item WHERE {{ ?item wdt:P31 wd:Q11424 . }} LIMIT {limit_per_type} }}
    BIND(\"film\" AS ?workType)
  }}
  UNION
  {{
    {{ SELECT DISTINCT ?item WHERE {{ ?item wdt:P31 wd:Q5398426 . }} LIMIT {limit_per_type} }}
    BIND(\"television_series\" AS ?workType)
  }}
}}
""".strip()


def retrieve_bulk_qids(limit_per_type: int) -> tuple[dict[str, set[str]], dict[str, Any]]:
    query = bulk_query(limit_per_type)
    document, audit = fetch_json(
        WDQS_ENDPOINT,
        {"format": "json", "query": query},
        maximum_bytes=MAX_SPARQL_RESPONSE_BYTES,
    )
    bindings = document.get("results", {}).get("bindings", [])
    if not isinstance(bindings, list):
        raise RuntimeError("Wikidata Query Service returned invalid bindings.")
    result: dict[str, set[str]] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        item_uri = str(binding.get("item", {}).get("value", ""))
        match = ENTITY_URI_PATTERN.fullmatch(item_uri)
        work_type = str(binding.get("workType", {}).get("value", ""))
        if match and work_type in set(WORK_TYPE_QIDS.values()):
            result.setdefault(match.group(1), set()).add(work_type)
    if not result:
        raise RuntimeError("The bulk Wikidata query returned no valid screen works.")
    audit.update(
        {
            "endpoint": WDQS_ENDPOINT,
            "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
            "binding_count": len(bindings),
            "unique_qid_count": len(result),
        }
    )
    return result, audit


def entity_documents(
    qids: list[str], *, include_claims: bool
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not qids:
        return {}, {"http_status": None, "response_bytes": 0, "attempts": 0}
    props = "labels|aliases|claims" if include_claims else "labels|aliases"
    document, audit = fetch_json(
        ENTITY_API_ENDPOINT,
        {
            "action": "wbgetentities",
            "ids": "|".join(qids[:50]),
            "props": props,
            "languages": "en",
            "languagefallback": "1",
            "format": "json",
            "origin": "*",
        },
        maximum_bytes=MAX_API_RESPONSE_BYTES,
    )
    entities = document.get("entities", {})
    return (entities if isinstance(entities, dict) else {}), audit


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def english_names(entity: dict[str, Any]) -> tuple[str, list[str]]:
    labels = entity.get("labels", {})
    label_value = labels.get("en", {}) if isinstance(labels, dict) else {}
    title = clean(label_value.get("value", "") if isinstance(label_value, dict) else "")
    aliases_value = entity.get("aliases", {})
    english_aliases = aliases_value.get("en", []) if isinstance(aliases_value, dict) else []
    aliases = sorted(
        {
            clean(item.get("value", ""))
            for item in english_aliases
            if isinstance(item, dict)
            and clean(item.get("value", ""))
            and len(clean(item.get("value", ""))) <= MAX_NAME_LENGTH
        },
        key=str.casefold,
    )[:MAX_ALIASES_PER_RECORD]
    return title[:MAX_NAME_LENGTH], aliases


def bulk_record(
    qid: str, entity: dict[str, Any], work_types: set[str]
) -> dict[str, Any] | None:
    if len(work_types) != 1:
        return None
    title, aliases = english_names(entity)
    if not title:
        return None
    return {
        "qid": qid,
        "title": title,
        "aliases": aliases,
        "work_type": next(iter(work_types)),
        "release_year": None,
        "source": "wikidata",
        "license": LICENSE,
        "source_url": f"https://www.wikidata.org/wiki/{qid}",
        "retrieval_methods": ["bounded_direct_instance_bulk_query"],
        "retrieved_for_exact_titles": [],
    }


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


def exact_record(
    qid: str, entity: dict[str, Any], searched_title: str
) -> dict[str, Any] | None:
    title, aliases = english_names(entity)
    if not title or key(searched_title) not in {key(title), *(key(item) for item in aliases)}:
        return None
    matched_types = {
        WORK_TYPE_QIDS[item]
        for item in claim_entity_ids(entity, "P31")
        if item in WORK_TYPE_QIDS
    }
    if len(matched_types) != 1:
        return None
    return {
        "qid": qid,
        "title": title,
        "aliases": aliases,
        "work_type": next(iter(matched_types)),
        "release_year": release_year(entity),
        "source": "wikidata",
        "license": LICENSE,
        "source_url": f"https://www.wikidata.org/wiki/{qid}",
        "retrieval_methods": ["exact_title_entity_search"],
        "retrieved_for_exact_titles": [searched_title],
    }


def search_qids(title: str) -> tuple[list[str], dict[str, Any]]:
    document, audit = fetch_json(
        ENTITY_API_ENDPOINT,
        {
            "action": "wbsearchentities",
            "search": title,
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": "20",
            "format": "json",
            "origin": "*",
        },
        maximum_bytes=MAX_API_RESPONSE_BYTES,
    )
    qids = [
        str(item.get("id", ""))
        for item in document.get("search", [])
        if isinstance(item, dict) and QID_PATTERN.fullmatch(str(item.get("id", "")))
    ]
    return list(dict.fromkeys(qids)), audit


def merge_record(
    records_by_qid: dict[str, dict[str, Any]], record: dict[str, Any]
) -> None:
    existing = records_by_qid.get(record["qid"])
    if existing is None:
        records_by_qid[record["qid"]] = record
        return
    existing["aliases"] = sorted(
        set(existing.get("aliases", [])) | set(record.get("aliases", [])),
        key=str.casefold,
    )[:MAX_ALIASES_PER_RECORD]
    existing["retrieval_methods"] = sorted(
        set(existing.get("retrieval_methods", []))
        | set(record.get("retrieval_methods", []))
    )
    existing["retrieved_for_exact_titles"] = sorted(
        set(existing.get("retrieved_for_exact_titles", []))
        | set(record.get("retrieved_for_exact_titles", [])),
        key=str.casefold,
    )
    if existing.get("release_year") is None and record.get("release_year") is not None:
        existing["release_year"] = record["release_year"]


def titles_from_args(args: argparse.Namespace) -> list[str]:
    values = [] if args.skip_default_examples else list(DEFAULT_EXACT_TITLES)
    values.extend(args.title)
    for raw_path in args.title_file:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Title file does not exist: {path}")
        values.extend(path.read_text(encoding="utf-8").splitlines())
    titles = [clean(value) for value in values if clean(value)]
    titles = list(dict.fromkeys(titles))
    if len(titles) > 500:
        raise ValueError("At most 500 exact-title supplements may be imported per run.")
    return titles


def main() -> None:
    args = parse_args()
    if not 100 <= args.limit_per_type <= 10000:
        raise ValueError("--limit-per-type must be between 100 and 10000.")
    exact_titles = titles_from_args(args)

    print("Retrieving a bounded CC0 film/series catalog from Wikidata...")
    print("No images, prose, plots, scripts, or subtitles are requested.")
    print("Catalog matches remain candidates and cannot verify uploaded media.\n")

    bulk_qids, bulk_audit = retrieve_bulk_qids(args.limit_per_type)
    records_by_qid: dict[str, dict[str, Any]] = {}
    entity_audit = {
        "batch_count": 0,
        "response_bytes": 0,
        "failed_entity_records": 0,
    }
    qids = sorted(bulk_qids, key=lambda value: int(value[1:]))
    for batch_number, batch in enumerate(chunks(qids, 50), start=1):
        entities, audit = entity_documents(batch, include_claims=False)
        entity_audit["batch_count"] += 1
        entity_audit["response_bytes"] += int(audit.get("response_bytes", 0))
        for qid in batch:
            entity = entities.get(qid)
            record = (
                bulk_record(qid, entity, bulk_qids[qid])
                if isinstance(entity, dict)
                else None
            )
            if record is None:
                entity_audit["failed_entity_records"] += 1
                continue
            merge_record(records_by_qid, record)
        if batch_number % 20 == 0:
            print(f"Loaded labels and aliases for {min(batch_number * 50, len(qids)):,} entities...")
        time.sleep(0.05)

    exact_title_audit: list[dict[str, Any]] = []
    for title in exact_titles:
        found_qids, search_audit = search_qids(title)
        entities, get_audit = entity_documents(found_qids, include_claims=True)
        accepted = 0
        for qid, entity in entities.items():
            if not QID_PATTERN.fullmatch(str(qid)) or not isinstance(entity, dict):
                continue
            record = exact_record(str(qid), entity, title)
            if record is None:
                continue
            merge_record(records_by_qid, record)
            accepted += 1
        exact_title_audit.append(
            {
                "title": title,
                "search_candidates": len(found_qids),
                "accepted_exact_typed_records": accepted,
                "search_request": search_audit,
                "entity_request": get_audit,
            }
        )

    records = sorted(
        records_by_qid.values(),
        key=lambda item: (item["title"].casefold(), item["work_type"], item["qid"]),
    )
    if not records:
        raise RuntimeError("No valid film or television-series records were imported.")
    retrieved_at = datetime.now(timezone.utc).isoformat()
    content_hash = canonical_hash(records)
    work_type_counts = {
        work_type: sum(item["work_type"] == work_type for item in records)
        for work_type in sorted(set(WORK_TYPE_QIDS.values()))
    }
    manifest = {
        "dataset": "wikidata_screen_works_v2",
        "retrieved_at_utc": retrieved_at,
        "record_count": len(records),
        "work_type_counts": work_type_counts,
        "requested_bulk_limit_per_type": args.limit_per_type,
        "exact_title_supplements": exact_titles,
        "source": "Wikidata structured entity data",
        "bulk_source_endpoint": WDQS_ENDPOINT,
        "entity_source_endpoint": ENTITY_API_ENDPOINT,
        "bulk_request_audit": bulk_audit,
        "entity_request_audit": entity_audit,
        "exact_title_request_audit": exact_title_audit,
        "license": LICENSE,
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "content_hash_sha256": content_hash,
        "bounded_catalog_not_exhaustive": True,
        "exact_title_expansion_supported": True,
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

    print("WIKIDATA SCREEN-WORK RAG CATALOG V2 IMPORT")
    print("=" * 60)
    print(f"Records: {len(records):,}")
    print(f"Requested bulk limit per type: {args.limit_per_type:,}")
    print(f"Exact-title supplements: {len(exact_titles):,}")
    print("\nWORK TYPE COUNTS")
    print("-" * 60)
    for work_type, count in work_type_counts.items():
        print(f"{work_type}: {count:,}")
    print(f"\nContent SHA-256: {content_hash}")
    print(f"Records: {RECORDS_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("Licence: CC0-1.0")
    print("Catalog exhaustive: False")
    print("Exact-title expansion supported: True")
    print("Creative media or Wikipedia prose downloaded: False")
    print("Confirmed visual provenance: 0")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("Every result is a retrieval candidate, not proof of uploaded-media provenance.")


if __name__ == "__main__":
    main()
