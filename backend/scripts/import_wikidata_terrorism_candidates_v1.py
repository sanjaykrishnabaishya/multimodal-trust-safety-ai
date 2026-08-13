from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = (
    ROOT
    / "datasets"
    / "public"
    / "wikidata_terrorism_candidates_v1"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "wikidata_candidate_import_v1"
)
CANDIDATE_PATH = OUTPUT_DIRECTORY / "candidates.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "manifest.json"
REPORT_PATH = REPORT_DIRECTORY / "import_report.json"

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_ENTITY_BASE = "https://www.wikidata.org/wiki/"
WIKIDATA_LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
WIKIDATA_LICENSE_PAGE = "https://www.wikidata.org/wiki/Wikidata:Licensing"
USER_AGENT = (
    "TrustScopeAI-Wikidata-DiscoveryBot/1.0 "
    "(https://trustscopeai.sanjaykb.workers.dev/)"
)
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
REVALIDATION_DAYS = 30

CLASS_LABELS = {
    "Q17127659": "terrorist organization",
    "Q4456236": "terrorist group",
}

# Wikidata is community edited. A small number of events, plots, people, and
# unrelated music groups are incorrectly assigned one of the target classes.
# Reject contradictory entity types in SPARQL, then apply a conservative label
# check as a second independent guard. Excluded rows remain counted in the audit.
CONTRADICTORY_CLASS_LABELS = {
    "Q5": "human",
    "Q1656682": "event",
    "Q215380": "musical group",
}
NON_ORGANIZATION_LABEL_PATTERN = re.compile(
    r"\b(?:"
    r"attack|attacks|bombing|bombings|explosion|explosions|"
    r"hijacker|hijackers|hijacking|hijackings|incident|incidents|"
    r"massacre|massacres|plot|plots|shooting|shootings|siege|sieges|"
    r"strike|strikes"
    r")\b",
    flags=re.IGNORECASE,
)

QUERY = """
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX schema: <http://schema.org/>

SELECT
  ?item
  ?itemLabel
  ?modified
  ?revision
  (GROUP_CONCAT(DISTINCT ?classId; separator="|") AS ?classIds)
  (GROUP_CONCAT(DISTINCT ?alias; separator="||") AS ?aliases)
WHERE {
  VALUES ?class { wd:Q17127659 wd:Q4456236 }
  ?item wdt:P31 ?class .
  FILTER NOT EXISTS {
    VALUES ?contradictoryRoot { wd:Q5 wd:Q1656682 wd:Q215380 }
    ?item wdt:P31/wdt:P279* ?contradictoryRoot .
  }
  ?item rdfs:label ?itemLabel .
  FILTER(LANG(?itemLabel) = "en")
  BIND(REPLACE(STR(?class), "^.*/", "") AS ?classId)
  OPTIONAL {
    ?item skos:altLabel ?alias .
    FILTER(LANG(?alias) = "en")
  }
  OPTIONAL { ?item schema:dateModified ?modified }
  OPTIONAL { ?item schema:version ?revision }
}
GROUP BY ?item ?itemLabel ?modified ?revision
ORDER BY LCASE(?itemLabel)
LIMIT 5000
""".strip()


def utc_text(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).strip()
    value = value.replace("’", "'").replace("‘", "'")
    value = re.sub(r"\s+", " ", value)
    return value


def comparison_key(value: str) -> str:
    value = normalized_name(value).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def is_matchable_name(value: str) -> bool:
    value = normalized_name(value)
    key = comparison_key(value)
    if len(key) < 5:
        return False
    tokens = key.split()
    if len(tokens) == 1 and value.isupper() and len(key) <= 8:
        return False
    if key.isdigit():
        return False
    return True


def unique_names(values: list[str], primary_name: str) -> list[str]:
    seen = {comparison_key(primary_name)}
    result: list[str] = []
    for raw_value in values:
        value = normalized_name(raw_value)
        key = comparison_key(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return sorted(result, key=str.casefold)


def quality_exclusion_reason(primary_name: str) -> str:
    if NON_ORGANIZATION_LABEL_PATTERN.search(normalized_name(primary_name)):
        return "event_plot_or_participant_like_label"
    return ""


def fetch_query() -> tuple[bytes, dict[str, object]]:
    encoded = urlencode({"query": QUERY, "format": "json"})
    url = f"{SPARQL_ENDPOINT}?{encoded}"
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json, application/json",
        },
        method="GET",
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=90) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("Wikidata response exceeded the safety limit.")
                if not payload:
                    raise RuntimeError("Wikidata returned an empty response.")
                return payload, {
                    "endpoint": SPARQL_ENDPOINT,
                    "http_status": response.status,
                    "content_type": response.headers.get("Content-Type", ""),
                    "response_bytes": len(payload),
                    "response_sha256": hashlib.sha256(payload).hexdigest(),
                    "request_count": attempt + 1,
                    "concurrent_requests": 1,
                    "access_control_bypassed": False,
                }
        except HTTPError as error:
            last_error = error
            if error.code not in {429, 503} or attempt == 2:
                raise
            retry_after = error.headers.get("Retry-After", "5")
            try:
                delay = max(1, min(60, int(retry_after)))
            except ValueError:
                delay = 5
            time.sleep(delay)
        except URLError as error:
            last_error = error
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Wikidata retrieval failed: {last_error}")


def binding_value(binding: dict[str, object], name: str) -> str:
    value = binding.get(name, {})
    if not isinstance(value, dict):
        return ""
    return normalized_name(str(value.get("value", "")))


def parse_candidates(
    payload: bytes,
    retrieved_utc: str,
) -> tuple[list[dict[str, object]], Counter[str]]:
    document = json.loads(payload.decode("utf-8"))
    bindings = document.get("results", {}).get("bindings", [])
    if not isinstance(bindings, list):
        raise RuntimeError("Wikidata returned an unexpected result structure.")

    candidates: list[dict[str, object]] = []
    quality_exclusions: Counter[str] = Counter()
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        entity_url = binding_value(binding, "item")
        qid_match = re.search(r"/(Q\d+)$", entity_url)
        if not qid_match:
            continue
        qid = qid_match.group(1)
        primary_name = binding_value(binding, "itemLabel")
        if not primary_name or primary_name == qid:
            continue
        exclusion_reason = quality_exclusion_reason(primary_name)
        if exclusion_reason:
            quality_exclusions[exclusion_reason] += 1
            continue

        aliases = unique_names(
            [
                part
                for part in binding_value(binding, "aliases").split("||")
                if part.strip()
            ],
            primary_name,
        )
        matchable_aliases = [alias for alias in aliases if is_matchable_name(alias)]
        class_qids = sorted(
            {
                part
                for part in binding_value(binding, "classIds").split("|")
                if part in CLASS_LABELS
            }
        )
        if not class_qids:
            continue

        candidates.append(
            {
                "qid": qid,
                "primary_name": primary_name,
                "aliases_json": json.dumps(
                    aliases, ensure_ascii=False, separators=(",", ":")
                ),
                "matchable_aliases_json": json.dumps(
                    matchable_aliases,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "primary_name_match_allowed": is_matchable_name(primary_name),
                "wikidata_class_qids_json": json.dumps(class_qids),
                "wikidata_class_labels_json": json.dumps(
                    [CLASS_LABELS[qid] for qid in class_qids]
                ),
                "community_status": "UNVERIFIED_COMMUNITY_CANDIDATE",
                "confirmed_legal_designation": False,
                "eligible_for_review_routing": True,
                "eligible_for_automatic_category": False,
                "automatic_enforcement_allowed": False,
                "neutral_mention_is_violation": False,
                "exact_match_only": True,
                "behavior_context_required": True,
                "source_url": f"{WIKIDATA_ENTITY_BASE}{qid}",
                "source_modified_utc": binding_value(binding, "modified"),
                "source_revision": binding_value(binding, "revision"),
                "retrieved_utc": retrieved_utc,
                "license": "CC0-1.0",
                "license_url": WIKIDATA_LICENSE_URL,
            }
        )

    deduplicated = {str(row["qid"]): row for row in candidates}
    return (
        sorted(
            deduplicated.values(),
            key=lambda row: str(row["primary_name"]).casefold(),
        ),
        quality_exclusions,
    )


def validate_candidates(
    candidates: list[dict[str, object]],
    quality_exclusions: Counter[str],
) -> dict[str, object]:
    failures: list[str] = []
    qids = [str(row["qid"]) for row in candidates]
    if len(candidates) < 20:
        failures.append(
            f"Expected at least 20 community candidates; received {len(candidates)}."
        )
    if len(qids) != len(set(qids)):
        failures.append("Duplicate Wikidata QIDs were produced.")
    if any(row["confirmed_legal_designation"] is not False for row in candidates):
        failures.append("A community candidate was incorrectly marked as confirmed.")
    if any(row["automatic_enforcement_allowed"] is not False for row in candidates):
        failures.append("Automatic enforcement must remain disabled.")
    if any(row["neutral_mention_is_violation"] is not False for row in candidates):
        failures.append("Neutral mentions must not be violations.")
    if any(row["license"] != "CC0-1.0" for row in candidates):
        failures.append("Every record must carry the CC0 licence identifier.")

    class_counts = Counter()
    matchable_primary_count = 0
    excluded_alias_count = 0
    for row in candidates:
        class_counts.update(json.loads(str(row["wikidata_class_qids_json"])))
        matchable_primary_count += int(bool(row["primary_name_match_allowed"]))
        aliases = json.loads(str(row["aliases_json"]))
        matchable_aliases = json.loads(str(row["matchable_aliases_json"]))
        excluded_alias_count += len(aliases) - len(matchable_aliases)

    return {
        "passed": not failures,
        "failures": failures,
        "records": len(candidates),
        "class_counts": dict(sorted(class_counts.items())),
        "matchable_primary_names": matchable_primary_count,
        "ambiguous_aliases_excluded_from_matching": excluded_alias_count,
        "quality_exclusions_after_retrieval": dict(
            sorted(quality_exclusions.items())
        ),
    }


def write_csv(rows: list[dict[str, object]], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".new")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(destination)


def write_json(value: object, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".new")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)


def main() -> None:
    retrieved = datetime.now(timezone.utc)
    retrieved_utc = utc_text(retrieved)
    print("Retrieving CC0 structured data from the Wikidata Query Service...")
    print("One identified API request is used; Wikipedia prose is not retrieved.\n")

    payload, source_audit = fetch_query()
    candidates, quality_exclusions = parse_candidates(payload, retrieved_utc)
    validation = validate_candidates(candidates, quality_exclusions)
    source_audit["retrieved_utc"] = retrieved_utc

    manifest = {
        "dataset_version": "2026.08-wikidata-candidates-v1",
        "created_utc": retrieved_utc,
        "revalidate_after_utc": utc_text(
            retrieved + timedelta(days=REVALIDATION_DAYS)
        ),
        "source": "Wikidata structured data",
        "source_classes": CLASS_LABELS,
        "source_endpoint": SPARQL_ENDPOINT,
        "source_license": "CC0-1.0",
        "source_license_url": WIKIDATA_LICENSE_URL,
        "source_license_policy": WIKIDATA_LICENSE_PAGE,
        "query_sha256": hashlib.sha256(QUERY.encode("utf-8")).hexdigest(),
        "validation": validation,
        "source_audit": source_audit,
        "policy_contract": {
            "community_edited": True,
            "confirmed_legal_designation": False,
            "eligible_for_review_routing": True,
            "eligible_for_automatic_category": False,
            "automatic_enforcement_allowed": False,
            "neutral_mention_is_violation": False,
            "exact_match_only": True,
            "behavior_context_required": True,
            "short_ambiguous_aliases_matchable": False,
            "wikipedia_prose_downloaded": False,
            "images_or_logos_downloaded": False,
            "individual_people_collected": False,
            "contradictory_entity_types_excluded": CONTRADICTORY_CLASS_LABELS,
            "event_plot_or_participant_like_labels_excluded": True,
            "extremism_inferred_from_ideology": False,
            "connected_to_live_moderation": False,
        },
    }

    write_json(manifest, REPORT_PATH)
    if not validation["passed"]:
        print("WIKIDATA CANDIDATE IMPORT VALIDATION FAILED")
        for failure in validation["failures"]:
            print(f"  - {failure}")
        print("The previous candidate registry, if any, was not replaced.")
        raise SystemExit(1)

    write_csv(candidates, CANDIDATE_PATH)
    write_json(manifest, MANIFEST_PATH)

    print("WIKIDATA TERRORISM COMMUNITY-CANDIDATE IMPORT")
    print("=" * 60)
    print(f"Records: {validation['records']:,}")
    print("\nDIRECT WIKIDATA CLASS COUNTS")
    print("-" * 60)
    for qid, count in validation["class_counts"].items():
        print(f"{qid} ({CLASS_LABELS[qid]}): {count:,}")
    print(
        "Ambiguous aliases excluded from matching: "
        f"{validation['ambiguous_aliases_excluded_from_matching']:,}"
    )
    print("\nQUALITY EXCLUSIONS AFTER RETRIEVAL")
    print("-" * 60)
    quality_counts = validation["quality_exclusions_after_retrieval"]
    if quality_counts:
        for reason, count in quality_counts.items():
            print(f"{reason}: {count:,}")
    else:
        print("None")
    print(f"\nCandidates: {CANDIDATE_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Audit report: {REPORT_PATH}")
    print("Licence: CC0-1.0")
    print("Wikipedia prose downloaded: False")
    print("Extremism inferred from ideology: False")
    print("Confirmed legal designations: 0")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("Every record is an unverified community candidate for review routing only.")


if __name__ == "__main__":
    main()
