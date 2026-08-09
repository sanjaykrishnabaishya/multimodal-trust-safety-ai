from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


PROJECT_DIRECTORY = Path(__file__).resolve().parents[3]

DATASET_PATH = (
    PROJECT_DIRECTORY
    / "datasets"
    / "official_evidence"
    / "india_official_fact_checks.json"
)

PIB_COPYRIGHT_POLICY_URL = (
    "https://factcheck.pib.gov.in/Documents/CopyrightPolicy.pdf"
)

PIB_CACHE_VERSION = "pib-only-legal-cache-v1"

ALLOWED_HOSTS = {
    "pib.gov.in",
    "www.pib.gov.in",
    "factcheck.pib.gov.in",
}

ALLOWED_SOURCE_NAMES = {
    "press information bureau",
    "pib fact check",
    "press information bureau fact check unit",
}

MAXIMUM_RESULTS = 3
MINIMUM_MATCH_SCORE = 0.12
MAXIMUM_SUMMARY_LENGTH = 400
MAXIMUM_CORRECTION_LENGTH = 700
MAXIMUM_EXAMPLE_LENGTH = 300


# This is a record-level allowlist, not a domain-wide permission list.
#
# Each entry was checked against the exact PIB source URL shown below.
# The records are historical and may be used only when the analyzed claim
# explicitly contains one of the listed years. They must never be used to
# decide a current, undated claim.
APPROVED_PIB_RECORDS: dict[str, dict[str, Any]] = {
    "pib-covid-relief-fund-001": {
        "expected_source_url": (
            "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1724638"
        ),
        "expected_content_sha256": (
            "81e4a70485dc76b7ca81d1e653632bd7dffd6e57af1d927f335c0c5feb4f1411"
        ),
        "approved_on": "2026-08-07",
        "expires_on": "2027-02-03",
        "historical_only": True,
        "allowed_claim_years": {"2021"},
        "subject_anchor_groups": (
            ("phase 4", "fourth phase"),
            (
                "covid relief",
                "covid-19 relief",
                "coronavirus relief",
                "relief fund",
            ),
        ),
        "third_party_content_excluded": True,
        "verification_note": (
            "Only the locally stored paraphrased PIB fact-check statement is "
            "used. Images, screenshots, logos and social-media embeds are excluded."
        ),
    },
    "pib-evm-ballot-false-001": {
        "expected_source_url": (
            "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1884999"
        ),
        "expected_content_sha256": (
            "c1d4871ef690f166efd9868c6f98e63a236230672c7f2e419b5dc9441ee66860"
        ),
        "approved_on": "2026-08-07",
        "expires_on": "2027-02-03",
        "historical_only": True,
        "allowed_claim_years": {"2022"},
        "subject_anchor_groups": (
            (
                "evm",
                "evms",
                "electronic voting machine",
                "electronic voting machines",
                "ballot paper",
                "ballot papers",
            ),
            (
                "supreme court",
                "future election",
                "future elections",
                "banned",
                "ban on evm",
            ),
        ),
        "third_party_content_excluded": True,
        "verification_note": (
            "Only the locally stored paraphrased PIB fact-check statement is "
            "used. YouTube material, screenshots, channel logos and images are excluded."
        ),
    },
}


GENERIC_MATCH_WORDS = {
    "about",
    "according",
    "after",
    "before",
    "central",
    "claim",
    "current",
    "government",
    "india",
    "indian",
    "official",
    "public",
    "report",
    "says",
    "source",
    "today",
    "world",
}


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def normalized_lower(text: str) -> str:
    return normalize_text(text).casefold()


def contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = normalized_lower(text)
    normalized_phrase = normalized_lower(phrase)

    if not normalized_phrase:
        return False

    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_phrase)}(?![a-z0-9])",
            normalized_text,
        )
    )


def content_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized_lower(text))
        if (
            len(token) >= 4
            or token in {"evm", "evms", "pib", "covid"}
        )
        and token not in GENERIC_MATCH_WORDS
    }


def canonical_source_url(url: str) -> str:
    parsed = urlparse(normalize_text(url))

    scheme = parsed.scheme.casefold()
    hostname = (parsed.hostname or "").casefold()
    path = parsed.path.rstrip("/")
    query = parsed.query

    return f"{scheme}://{hostname}{path}" + (f"?{query}" if query else "")


def source_url_is_allowed(url: str) -> bool:
    parsed = urlparse(normalize_text(url))

    return bool(
        parsed.scheme.casefold() == "https"
        and (parsed.hostname or "").casefold() in ALLOWED_HOSTS
    )


def calculate_record_hash(record: dict[str, Any]) -> str:
    hash_payload = {
        key: value
        for key, value in record.items()
        if key not in {"content_sha256", "snapshot_sha256"}
    }

    canonical_json = json.dumps(
        hash_payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def safe_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def approval_is_active(approval: dict[str, Any]) -> bool:
    approved_on = safe_date(approval.get("approved_on"))
    expires_on = safe_date(approval.get("expires_on"))

    if approved_on is None or expires_on is None:
        return False

    return approved_on <= date.today() <= expires_on


def record_text_is_limited(record: dict[str, Any]) -> bool:
    claim_summary = normalize_text(record.get("claim_summary", ""))
    correction = normalize_text(record.get("correction", ""))
    claim_examples = [
        normalize_text(example)
        for example in record.get("claim_examples", [])
    ]

    if not claim_summary or not correction:
        return False

    if len(claim_summary) > MAXIMUM_SUMMARY_LENGTH:
        return False

    if len(correction) > MAXIMUM_CORRECTION_LENGTH:
        return False

    if any(len(example) > MAXIMUM_EXAMPLE_LENGTH for example in claim_examples):
        return False

    forbidden_fields = {
        "image",
        "images",
        "logo",
        "logos",
        "screenshot",
        "screenshots",
        "video",
        "raw_html",
        "full_page_text",
        "downloaded_file",
    }

    if forbidden_fields & {str(key).casefold() for key in record}:
        return False

    return True


def validate_approved_record(
    record: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    record_id = str(record.get("record_id", ""))
    approval = APPROVED_PIB_RECORDS.get(record_id)

    if approval is None:
        return False, ["record_id_not_allowlisted"]

    source_name = normalized_lower(record.get("source_name", ""))
    source_url = normalize_text(record.get("source_url", ""))

    if source_name not in ALLOWED_SOURCE_NAMES:
        reasons.append("source_name_not_pib_fact_check")

    if not source_url_is_allowed(source_url):
        reasons.append("source_domain_not_allowed")

    if canonical_source_url(source_url) != canonical_source_url(
        approval.get("expected_source_url", "")
    ):
        reasons.append("source_url_does_not_match_allowlist")

    stored_hash = str(record.get("content_sha256", ""))
    calculated_hash = calculate_record_hash(record)
    expected_hash = str(approval.get("expected_content_sha256", ""))

    if not stored_hash or stored_hash != calculated_hash:
        reasons.append("record_content_hash_invalid")

    if stored_hash != expected_hash:
        reasons.append("record_content_changed_after_approval")

    if not approval_is_active(approval):
        reasons.append("legal_cache_approval_expired")

    if not approval.get("third_party_content_excluded", False):
        reasons.append("third_party_content_not_excluded")

    if not record_text_is_limited(record):
        reasons.append("record_contains_missing_or_excessive_content")

    if normalized_lower(record.get("source_type", "")) != "official_fact_check":
        reasons.append("source_type_not_official_fact_check")

    return not reasons, reasons


def claim_matches_anchor_groups(
    claim: str,
    anchor_groups: tuple[tuple[str, ...], ...],
) -> bool:
    return all(
        any(contains_phrase(claim, anchor) for anchor in group)
        for group in anchor_groups
    )


def claim_matches_temporal_scope(
    claim: str,
    approval: dict[str, Any],
) -> bool:
    if not approval.get("historical_only", False):
        return True

    allowed_years = {
        str(year)
        for year in approval.get("allowed_claim_years", set())
    }

    claim_years = set(re.findall(r"\b(?:19|20)\d{2}\b", claim))

    return bool(claim_years & allowed_years)


def build_record_document(record: dict[str, Any]) -> str:
    return normalize_text(
        " ".join(
            [
                str(record.get("claim_summary", "")),
                *[
                    str(example)
                    for example in record.get("claim_examples", [])
                ],
                str(record.get("correction", "")),
                " ".join(
                    str(topic)
                    for topic in record.get("topics", [])
                ),
            ]
        )
    )


def calculate_match_scores(
    claim: str,
    records: list[dict[str, Any]],
) -> list[float]:
    if not records:
        return []

    documents = [
        claim,
        *[build_record_document(record) for record in records],
    ]

    try:
        word_vectors = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=8000,
        ).fit_transform(documents)

        character_vectors = TfidfVectorizer(
            lowercase=True,
            analyzer="char_wb",
            ngram_range=(3, 5),
            max_features=12000,
        ).fit_transform(documents)

        word_scores = cosine_similarity(
            word_vectors[0:1],
            word_vectors[1:],
        )[0]

        character_scores = cosine_similarity(
            character_vectors[0:1],
            character_vectors[1:],
        )[0]

    except ValueError:
        return [0.0 for _ in records]

    return [
        float(word_score * 0.70 + character_score * 0.30)
        for word_score, character_score in zip(
            word_scores,
            character_scores,
        )
    ]


@lru_cache(maxsize=1)
def load_pib_cache_records() -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    warnings: list[str] = []
    statistics = {
        "dataset_records": 0,
        "non_pib_records_rejected": 0,
        "pib_records_not_allowlisted": 0,
        "pib_records_invalid_or_expired": 0,
        "approved_active_records": 0,
    }

    if not DATASET_PATH.exists():
        return (
            [],
            ["The PIB fact-check dataset was not found."],
            statistics,
        )

    try:
        payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return (
            [],
            [
                "The PIB fact-check dataset could not be read: "
                f"{type(error).__name__}."
            ],
            statistics,
        )

    source_records = payload.get("records", [])

    if not isinstance(source_records, list):
        return (
            [],
            ["The fact-check dataset has an invalid records field."],
            statistics,
        )

    statistics["dataset_records"] = len(source_records)
    approved_records: list[dict[str, Any]] = []

    for source_record in source_records:
        if not isinstance(source_record, dict):
            continue

        record = dict(source_record)
        record_id = str(record.get("record_id", "unknown"))
        source_name = normalized_lower(record.get("source_name", ""))

        if source_name not in ALLOWED_SOURCE_NAMES:
            statistics["non_pib_records_rejected"] += 1
            continue

        if record_id not in APPROVED_PIB_RECORDS:
            statistics["pib_records_not_allowlisted"] += 1
            warnings.append(
                f"PIB cache record {record_id} was rejected because it is not "
                "on the record-level allowlist."
            )
            continue

        valid, reasons = validate_approved_record(record)

        if not valid:
            statistics["pib_records_invalid_or_expired"] += 1
            warnings.append(
                f"PIB cache record {record_id} was rejected: "
                + ", ".join(reasons)
                + "."
            )
            continue

        approval = APPROVED_PIB_RECORDS[record_id]
        record["legal_cache_approved"] = True
        record["cache_policy_status"] = "approved"
        record["cache_policy_version"] = PIB_CACHE_VERSION
        record["copyright_policy_url"] = PIB_COPYRIGHT_POLICY_URL
        record["licence_basis"] = "PIB Copyright Policy"
        record["third_party_content_excluded"] = True
        record["cache_approved_on"] = approval["approved_on"]
        record["cache_expires_on"] = approval["expires_on"]
        record["historical_only"] = approval.get("historical_only", False)
        record["allowed_claim_years"] = sorted(
            str(year)
            for year in approval.get("allowed_claim_years", set())
        )
        record["verification_note"] = approval.get(
            "verification_note",
            "",
        )

        approved_records.append(record)
        statistics["approved_active_records"] += 1

    return approved_records, list(dict.fromkeys(warnings)), statistics


def retrieve_official_cached_evidence(
    claim: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    cleaned_claim = normalize_text(claim)

    if not cleaned_claim:
        return [], []

    records, load_warnings, _ = load_pib_cache_records()
    warnings = list(load_warnings)
    eligible_records: list[dict[str, Any]] = []

    for record in records:
        record_id = str(record["record_id"])
        approval = APPROVED_PIB_RECORDS[record_id]

        if not claim_matches_anchor_groups(
            cleaned_claim,
            approval["subject_anchor_groups"],
        ):
            continue

        if not claim_matches_temporal_scope(cleaned_claim, approval):
            allowed_years = ", ".join(
                sorted(approval.get("allowed_claim_years", set()))
            )
            warnings.append(
                f"Historical PIB cache record {record_id} was not used because "
                f"the claim did not explicitly identify its allowed year: {allowed_years}."
            )
            continue

        eligible_records.append(record)

    scores = calculate_match_scores(cleaned_claim, eligible_records)
    matched_records: list[tuple[float, dict[str, Any]]] = []

    for record, score in zip(eligible_records, scores):
        if score >= MINIMUM_MATCH_SCORE:
            matched_records.append((float(score), record))

    matched_records.sort(key=lambda item: item[0], reverse=True)
    candidates: list[dict[str, Any]] = []

    for score, record in matched_records[:MAXIMUM_RESULTS]:
        record_id = str(record["record_id"])
        source_url = str(record["source_url"])

        attribution = (
            "Source: Press Information Bureau (PIB Fact Check), Government "
            f"of India. Original: {source_url}. Accessed and approved for the "
            f"local text-only cache on {record['cache_approved_on']}."
        )

        candidates.append(
            {
                "source_id": f"pib_legal_cache:{record_id}",
                "source_name": "Press Information Bureau — PIB Fact Check",
                "source_type": "approved_pib_fact_check_cache",
                "trust_tier": 1,
                "official_source": True,
                "official_snapshot": True,
                "legal_cache_approved": True,
                "cache_policy_status": "approved",
                "cache_policy_version": PIB_CACHE_VERSION,
                "copyright_policy_url": PIB_COPYRIGHT_POLICY_URL,
                "licence_basis": record["licence_basis"],
                "third_party_content_excluded": True,
                "historical_only": record["historical_only"],
                "allowed_claim_years": record["allowed_claim_years"],
                "record_id": record_id,
                "record_verdict": record.get("verdict", "REFUTES"),
                "source_published_date": record.get(
                    "source_published_date",
                    "undated",
                ),
                "last_verified_date": record["cache_approved_on"],
                "fresh_until": record["cache_expires_on"],
                "content_sha256": record["content_sha256"],
                "cache_match_score": round(score, 4),
                "title": f"PIB Fact Check: {record['claim_summary']}",
                "source_url": source_url,
                "evidence_text": normalize_text(record["correction"]),
                "attribution": attribution,
                "verification_note": record["verification_note"],
            }
        )

    return candidates, list(dict.fromkeys(warnings))


def get_official_evidence_cache_status() -> dict[str, Any]:
    records, warnings, statistics = load_pib_cache_records()

    return {
        "available": bool(records),
        "cache_scope": "PIB Fact Check only",
        "cache_policy_version": PIB_CACHE_VERSION,
        "dataset_path": str(DATASET_PATH),
        "copyright_policy_url": PIB_COPYRIGHT_POLICY_URL,
        "allowed_hosts": sorted(ALLOWED_HOSTS),
        "allowed_record_ids": sorted(APPROVED_PIB_RECORDS),
        "approved_active_records": len(records),
        "statistics": statistics,
        "rules": {
            "record_level_allowlist_required": True,
            "text_only": True,
            "third_party_content_excluded": True,
            "expired_records_allowed": False,
            "historical_claim_year_required": True,
            "automatic_enforcement_allowed": False,
            "training_or_rag_use_allowed": False,
        },
        "warnings": warnings,
    }
