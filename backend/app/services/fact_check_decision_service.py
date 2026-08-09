from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import torch
import requests
from lxml import html as lxml_html
from lxml.etree import ParserError as LxmlParserError
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.services.fact_check_retrieval_service import retrieve_fact_check_evidence
from app.services.stable_knowledge_v3_service import (
    retrieve_stable_knowledge_v3,
)


MODEL_NAME = "cross-encoder/nli-deberta-v3-small"

MISINFORMATION_CATEGORY = "Misinformation & Fake News"
NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"

MAX_EVIDENCE_TO_ANALYZE = 12

SUPPORT_THRESHOLD = 0.82
REFUTE_THRESHOLD = 0.85
MINIMUM_SCORE_MARGIN = 0.12

MINIMUM_OFFICIAL_RELEVANCE = 0.03
MINIMUM_GENERAL_RELEVANCE = 0.06
MINIMUM_CONTENT_OVERLAP = 0.08
MINIMUM_PIB_CACHE_MATCH_SCORE = 0.12
PIB_CACHE_VERDICT_CONFIDENCE = 0.75

PIB_COPYRIGHT_POLICY_URL = (
    "https://factcheck.pib.gov.in/Documents/CopyrightPolicy.pdf"
)

ALLOWED_PIB_CACHE_HOSTS = {
    "pib.gov.in",
    "www.pib.gov.in",
    "factcheck.pib.gov.in",
}

ECI_LIVE_HOST = "www.eci.gov.in"
ECI_LIVE_REQUEST_TIMEOUT = 20
ECI_LIVE_USER_AGENT = (
    "TrustSafetyAI/1.0 "
    "(educational fact-checking project; live official evidence; no caching)"
)

ECI_LIVE_SOURCES: tuple[dict[str, str], ...] = (
    {
        "source_id": "eci_live_evm_faqs",
        "source_name": "Election Commission of India — EVM FAQs",
        "title": "FAQs on Electronic Voting Machines",
        "source_url": "https://www.eci.gov.in/evm-faqs/",
    },
    {
        "source_id": "eci_live_evm_vvpat",
        "source_name": "Election Commission of India — EVM/VVPAT",
        "title": "EVM/VVPAT",
        "source_url": "https://www.eci.gov.in/evm-vvpat",
    },
)


STOP_WORDS = {
    "a",
    "about",
    "after",
    "all",
    "also",
    "an",
    "and",
    "any",
    "are",
    "around",
    "as",
    "at",
    "be",
    "been",
    "before",
    "being",
    "between",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "during",
    "every",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "hers",
    "him",
    "his",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "more",
    "most",
    "must",
    "not",
    "of",
    "on",
    "only",
    "or",
    "our",
    "ours",
    "she",
    "should",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "under",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "would",
    "you",
    "your",
    "yours",
}


SUBJECT_PREDICATE_PATTERN = re.compile(
    r"\b(?:"
    r"is|are|was|were|be|been|being|"
    r"has|have|had|"
    r"does|do|did|"
    r"will|would|can|could|should|must|may|might|"
    r"travels?|orbits?|revolves?|contains?|"
    r"created|creates|developed|develops|"
    r"founded|established|entered|issued|issues|"
    r"administers?|operates?|located|reached|banned|"
    r"supports?|refutes?|announced|reported|said"
    r")\b",
    flags=re.IGNORECASE,
)


def is_india_evm_claim(claim: str) -> bool:
    claim_text = normalized_lower(claim)

    evm_signal = bool(
        re.search(
            r"\b(?:evm|evms|electronic voting machines?)\b",
            claim_text,
        )
    )

    india_or_court_signal = any(
        phrase in claim_text
        for phrase in (
            "india",
            "indian",
            "election commission of india",
            "eci",
            "supreme court",
            "ballot paper",
            "ballot papers",
        )
    )

    explicitly_foreign = any(
        phrase in claim_text
        for phrase in (
            "united states",
            "u.s. supreme court",
            "us supreme court",
            "united kingdom",
            "uk supreme court",
            "pakistan supreme court",
            "bangladesh supreme court",
            "nepal supreme court",
        )
    )

    return bool(evm_signal and india_or_court_signal and not explicitly_foreign)


def is_evm_ban_claim(claim: str) -> bool:
    claim_text = normalized_lower(claim)

    return bool(
        re.search(
            r"\b(?:ban|banned|banning|abolished|discontinued|stopped|"
            r"prohibited|outlawed)\b",
            claim_text,
        )
        and re.search(
            r"\b(?:evm|evms|electronic voting machines?)\b",
            claim_text,
        )
    )


def drop_non_text_elements(document: Any) -> None:
    for element in document.xpath(
        "//script|//style|//noscript|//svg|//img|//video|//audio|"
        "//form|//button|//nav|//header|//footer"
    ):
        try:
            element.drop_tree()
        except AttributeError:
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)


def extract_eci_text_blocks(page_content: bytes) -> list[str]:
    document = lxml_html.fromstring(page_content)
    drop_non_text_elements(document)

    blocks: list[str] = []
    seen: set[str] = set()

    for element in document.xpath("//main//*[self::p or self::li or self::h2 or self::h3] | //article//*[self::p or self::li or self::h2 or self::h3] | //p | //li"):
        text = normalize_text(" ".join(element.itertext()))

        if len(text) < 45 or len(text) > 1800:
            continue

        key = text.casefold()

        if key in seen:
            continue

        seen.add(key)
        blocks.append(text)

    return blocks


def eci_block_is_relevant(block: str) -> bool:
    block_text = normalized_lower(block)

    has_evm = bool(
        re.search(
            r"\b(?:evm|evms|electronic voting machines?)\b",
            block_text,
        )
    )

    has_decision_context = any(
        phrase in block_text
        for phrase in (
            "supreme court",
            "return to the paper ballot",
            "return to paper ballot",
            "manual ballot",
            "dismissed the petition",
            "dismissed the petitions",
            "used in indian elections",
            "used for elections",
            "record and count votes",
            "record votes",
            "statutory mandate",
            "backing of judiciary",
        )
    )

    return bool(has_evm and has_decision_context)


def eci_block_refutes_ban_claim(claim: str, block: str) -> bool:
    if not is_evm_ban_claim(claim):
        return False

    block_text = normalized_lower(block)

    current_use_signal = any(
        phrase in block_text
        for phrase in (
            "evms are used in indian elections",
            "evm is an electronic device used to electronically record",
            "electronic voting machine is an electronic device for recording votes",
            "evms are used in elections",
        )
    )

    court_rejection_signal = bool(
        "supreme court" in block_text
        and any(
            phrase in block_text
            for phrase in (
                "dismissed the petition",
                "dismissed the petitions",
                "return to the manual ballot",
                "return to manual ballot",
                "discarding the use of evms",
                "backing of judiciary",
            )
        )
    )

    return bool(current_use_signal or court_rejection_signal)


def live_relevance_score(claim: str, block: str) -> float:
    claim_tokens = content_tokens(claim)
    block_tokens = content_tokens(block)

    if not claim_tokens or not block_tokens:
        return 0.0

    overlap = len(claim_tokens & block_tokens) / len(claim_tokens)

    if eci_block_refutes_ban_claim(claim, block):
        overlap = max(overlap, 0.35)

    return round(min(overlap, 1.0), 4)


def retrieve_live_eci_evidence(
    claim: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not is_india_evm_claim(claim):
        return [], []

    warnings: list[str] = []
    candidates: list[dict[str, Any]] = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    for source in ECI_LIVE_SOURCES:
        url = source["source_url"]

        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": ECI_LIVE_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=ECI_LIVE_REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            response.raise_for_status()

            final_url = str(response.url)
            final_host = (urlparse(final_url).hostname or "").casefold()

            if final_host != ECI_LIVE_HOST:
                warnings.append(
                    f"{source['source_name']} redirected outside the approved "
                    "ECI host and was not used."
                )
                continue

            content_type = str(response.headers.get("Content-Type", "")).casefold()

            if "html" not in content_type:
                warnings.append(
                    f"{source['source_name']} did not return an HTML page and "
                    "was not used."
                )
                continue

            relevant_blocks = [
                block
                for block in extract_eci_text_blocks(response.content)
                if eci_block_is_relevant(block)
            ]

            relevant_blocks.sort(
                key=lambda block: live_relevance_score(claim, block),
                reverse=True,
            )

            for block_index, block in enumerate(relevant_blocks[:3], start=1):
                relation_refutes = eci_block_refutes_ban_claim(claim, block)

                candidates.append(
                    {
                        "source_id": f"{source['source_id']}:{block_index}",
                        "source_name": source["source_name"],
                        "source_type": "live_eci_official_evidence",
                        "trust_tier": 1,
                        "official_source": True,
                        "official_snapshot": False,
                        "retrieved_live": True,
                        "cache_allowed": False,
                        "live_evidence_retrieved_at": retrieved_at,
                        "title": source["title"],
                        "source_url": final_url,
                        "relevance_score": live_relevance_score(claim, block),
                        "excerpt": block[:700],
                        "official_relation_verdict": (
                            "REFUTES" if relation_refutes else "NOT_DETERMINED"
                        ),
                        "verified_relation": (
                            "current_evm_use_or_court_rejection"
                            if relation_refutes
                            else "none"
                        ),
                        "attribution": (
                            f"Source: {source['source_name']}. Original: "
                            f"{final_url}. Accessed live at {retrieved_at}."
                        ),
                    }
                )

        except requests.RequestException as error:
            warnings.append(
                f"{source['source_name']} live retrieval failed without "
                f"bypassing the source: {type(error).__name__}: {error}"
            )
        except (ValueError, TypeError, LxmlParserError) as error:
            warnings.append(
                f"{source['source_name']} returned unusable HTML: "
                f"{type(error).__name__}: {error}"
            )

    candidates.sort(
        key=lambda item: (
            item.get("official_relation_verdict") == "REFUTES",
            float(item.get("relevance_score", 0.0)),
        ),
        reverse=True,
    )

    return candidates[:4], list(dict.fromkeys(warnings))


@lru_cache(maxsize=1)
def load_fact_check_model():
    print("Loading the English fact-check NLI model...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()

    return tokenizer, model


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def normalized_lower(text: str) -> str:
    return normalize_text(text).casefold()


def token_forms(token: str) -> set[str]:
    cleaned = token.casefold().strip("'-_")

    if not cleaned:
        return set()

    forms = {cleaned}

    if len(cleaned) > 4 and cleaned.endswith("ies"):
        forms.add(cleaned[:-3] + "y")

    if len(cleaned) > 4 and cleaned.endswith("es"):
        forms.add(cleaned[:-2])

    if len(cleaned) > 3 and cleaned.endswith("s"):
        forms.add(cleaned[:-1])

    if len(cleaned) > 5 and cleaned.endswith("ing"):
        forms.add(cleaned[:-3])

    if len(cleaned) > 4 and cleaned.endswith("ed"):
        forms.add(cleaned[:-2])

    return forms


def content_tokens(text: str) -> set[str]:
    tokens: set[str] = set()

    for raw_token in re.findall(r"[A-Za-z0-9]+", normalized_lower(text)):
        if raw_token in STOP_WORDS:
            continue

        if len(raw_token) < 3 and not raw_token.isdigit():
            continue

        tokens.update(token_forms(raw_token))

    return tokens


def extract_subject_text(claim: str) -> str:
    cleaned_claim = normalize_text(claim).strip(" .?!,;:")
    match = SUBJECT_PREDICATE_PATTERN.search(cleaned_claim)

    if match:
        subject = cleaned_claim[: match.start()]
    else:
        subject = cleaned_claim

    subject = re.sub(
        r"^(?:the|a|an|this|that|these|those)\s+",
        "",
        subject,
        flags=re.IGNORECASE,
    )

    return subject.strip(" .?!,;:")


def overlap_ratio(first: set[str], second: set[str]) -> float:
    if not first or not second:
        return 0.0

    return len(first & second) / len(first)


def required_subject_matches(subject_tokens: set[str]) -> int:
    if not subject_tokens:
        return 0

    return min(2, max(1, math.ceil(len(subject_tokens) * 0.34)))


def is_persistent_snapshot(evidence: dict[str, Any]) -> bool:
    source_id = str(evidence.get("source_id", "")).casefold()
    source_type = str(evidence.get("source_type", "")).casefold()

    return bool(evidence.get("official_snapshot", False)) or source_id.startswith(
        "official_cache:"
    ) or source_type in {
        "official_reference_snapshot",
        "official_cached_fact_check",
    }


def safe_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def validate_pib_legal_cache(
    claim: str,
    evidence: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if not is_persistent_snapshot(evidence):
        return True, ["live_evidence"]

    source_id = str(evidence.get("source_id", "")).casefold()
    source_type = str(evidence.get("source_type", "")).casefold()
    source_url = str(evidence.get("source_url", ""))
    source_host = (urlparse(source_url).hostname or "").casefold()
    policy_url = str(evidence.get("copyright_policy_url", ""))

    if not evidence.get("legal_cache_approved", False):
        reasons.append("legal_cache_not_approved")

    if str(evidence.get("cache_policy_status", "")).casefold() != "approved":
        reasons.append("cache_policy_status_not_approved")

    if not source_id.startswith("pib_legal_cache:"):
        reasons.append("cache_source_id_not_pib_allowlist")

    if source_type != "approved_pib_fact_check_cache":
        reasons.append("cache_source_type_not_approved_pib")

    if source_host not in ALLOWED_PIB_CACHE_HOSTS:
        reasons.append("cache_source_domain_not_pib")

    if policy_url != PIB_COPYRIGHT_POLICY_URL:
        reasons.append("pib_copyright_policy_missing_or_changed")

    if not evidence.get("third_party_content_excluded", False):
        reasons.append("third_party_content_not_excluded")

    expiry_date = safe_date(evidence.get("fresh_until"))

    if expiry_date is None or expiry_date < date.today():
        reasons.append("legal_cache_record_expired")

    if evidence.get("historical_only", False):
        allowed_years = {
            str(year)
            for year in evidence.get("allowed_claim_years", [])
        }
        claim_years = set(re.findall(r"\b(?:19|20)\d{2}\b", claim))

        if not claim_years.intersection(allowed_years):
            reasons.append("historical_claim_year_not_matched")

    return not reasons, reasons


def evidence_is_usable(
    claim: str,
    evidence: dict[str, Any],
) -> bool:
    valid, _ = validate_pib_legal_cache(claim, evidence)
    return valid


def evaluate_alignment(
    claim: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    title = normalize_text(evidence.get("title", ""))
    excerpt = normalize_text(evidence.get("excerpt", ""))
    evidence_text = normalize_text(f"{title}. {excerpt}")

    claim_tokens = content_tokens(claim)
    evidence_tokens = content_tokens(evidence_text)

    subject_text = extract_subject_text(claim)
    subject_tokens = content_tokens(subject_text)

    subject_matches = len(subject_tokens & evidence_tokens)
    required_matches = required_subject_matches(subject_tokens)

    subject_phrase_match = bool(
        len(subject_text) >= 3
        and normalized_lower(subject_text) in normalized_lower(evidence_text)
    )

    subject_passed = bool(
        not subject_tokens
        or subject_phrase_match
        or subject_matches >= required_matches
    )

    claim_overlap = overlap_ratio(claim_tokens, evidence_tokens)
    subject_overlap = overlap_ratio(subject_tokens, evidence_tokens)
    title_overlap = overlap_ratio(claim_tokens, content_tokens(title))

    raw_relevance = float(evidence.get("relevance_score", 0.0) or 0.0)
    official_source = bool(evidence.get("official_source", False))

    minimum_relevance = (
        MINIMUM_OFFICIAL_RELEVANCE
        if official_source
        else MINIMUM_GENERAL_RELEVANCE
    )

    relevant_passed = bool(
        raw_relevance >= minimum_relevance
        or claim_overlap >= MINIMUM_CONTENT_OVERLAP
        or title_overlap >= 0.20
    )

    claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", claim))
    evidence_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", evidence_text))

    if is_persistent_snapshot(evidence):
        evidence_numbers.update(
            re.findall(
                r"\b\d+(?:\.\d+)?\b",
                " ".join(
                    [
                        str(evidence.get("source_published_date", "")),
                        *[
                            str(year)
                            for year in evidence.get("allowed_claim_years", [])
                        ],
                    ]
                ),
            )
        )

    number_context_available = bool(not claim_numbers or evidence_numbers)

    alignment_score = (
        0.50 * subject_overlap
        + 0.25 * claim_overlap
        + 0.15 * title_overlap
        + 0.10 * min(raw_relevance / 0.25, 1.0)
    )

    legal_cache_valid, legal_cache_reasons = validate_pib_legal_cache(
        claim,
        evidence,
    )

    verified_structured_relationship = bool(
        evidence.get("retrieved_live", False)
        and not evidence.get("cache_allowed", True)
        and str(
            evidence.get(
                "structured_relation_verdict",
                evidence.get("stable_relation_verdict", ""),
            )
        ).upper()
        in {"SUPPORTS", "REFUTES"}
        and str(evidence.get("verified_relation", "none")) != "none"
        and evidence.get("anchor_entity")
    )

    # A live structured relationship is already aligned by exact entity
    # resolution, property routing, and typed value comparison. Sending its
    # generated explanation back through lexical alignment can incorrectly
    # reject it or manufacture an NLI conflict. This bypass applies only to
    # live, non-cached, verified structured records.
    if verified_structured_relationship:
        subject_passed = True
        relevant_passed = True
        number_context_available = True
        alignment_score = max(alignment_score, 0.95)

    alignment_passed = bool(
        subject_passed
        and relevant_passed
        and number_context_available
        and legal_cache_valid
    )

    reasons: list[str] = []

    if is_persistent_snapshot(evidence):
        if legal_cache_valid:
            reasons.append("approved_pib_legal_cache")
        else:
            reasons.extend(legal_cache_reasons)

    if not subject_passed:
        reasons.append("claim_subject_not_found")

    if not relevant_passed:
        reasons.append("insufficient_claim_overlap")

    if not number_context_available:
        reasons.append("claim_number_missing_from_evidence_context")

    if alignment_passed:
        reasons.append("alignment_passed")
    if verified_structured_relationship:
        reasons.append("verified_live_structured_relationship")

    return {
        "alignment_passed": alignment_passed,
        "alignment_score": round(alignment_score, 4),
        "alignment_reasons": reasons,
        "claim_subject": subject_text,
        "subject_overlap": round(subject_overlap, 4),
        "claim_overlap": round(claim_overlap, 4),
        "title_overlap": round(title_overlap, 4),
        "number_context_available": number_context_available,
        "legal_cache_validation_passed": legal_cache_valid,
        "legal_cache_validation_reasons": legal_cache_reasons,
    }


def analyze_evidence_batch(
    claim: str,
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not evidence_items:
        return []

    tokenizer, model = load_fact_check_model()

    evidence_texts = [
        normalize_text(item.get("excerpt", ""))
        for item in evidence_items
    ]

    encoded = tokenizer(
        evidence_texts,
        [claim for _ in evidence_texts],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )

    with torch.no_grad():
        output = model(**encoded)

    probabilities = torch.softmax(output.logits, dim=-1)
    analyzed_items: list[dict[str, Any]] = []

    for item, probability_row in zip(evidence_items, probabilities):
        scores = {
            "entailment": 0.0,
            "neutral": 0.0,
            "contradiction": 0.0,
        }

        for index, probability in enumerate(probability_row):
            label = str(
                model.config.id2label.get(index, f"LABEL_{index}")
            ).strip().casefold()

            if label in scores:
                scores[label] = float(probability)

        analyzed_item = dict(item)
        analyzed_item.update(evaluate_alignment(claim, analyzed_item))
        analyzed_item["nli_scores"] = {
            label: round(score, 4)
            for label, score in scores.items()
        }
        analyzed_item["support_margin"] = round(
            scores["entailment"]
            - max(scores["contradiction"], scores["neutral"]),
            4,
        )
        analyzed_item["refute_margin"] = round(
            scores["contradiction"]
            - max(scores["entailment"], scores["neutral"]),
            4,
        )

        analyzed_items.append(analyzed_item)

    return analyzed_items


def is_high_quality_source(evidence: dict[str, Any]) -> bool:
    if (
        is_persistent_snapshot(evidence)
        and not evidence.get("legal_cache_validation_passed", False)
    ):
        return False

    return bool(evidence.get("official_source", False)) or int(
        evidence.get("trust_tier", 99) or 99
    ) <= 2


def is_strong_support(evidence: dict[str, Any]) -> bool:
    if not evidence.get("alignment_passed", False):
        return False

    verified_stable_support = bool(
        evidence.get("retrieved_live", False)
        and not evidence.get("cache_allowed", True)
        and str(evidence.get("stable_relation_verdict", "")).upper()
        == "SUPPORTS"
        and str(evidence.get("verified_relation", "")) != "none"
    )

    if verified_stable_support:
        return True

    scores = evidence.get("nli_scores", {})
    entailment = float(scores.get("entailment", 0.0))
    contradiction = float(scores.get("contradiction", 0.0))
    neutral = float(scores.get("neutral", 0.0))

    return bool(
        entailment >= SUPPORT_THRESHOLD
        and entailment - max(contradiction, neutral) >= MINIMUM_SCORE_MARGIN
    )


def is_strong_refutation(evidence: dict[str, Any]) -> bool:
    if not evidence.get("alignment_passed", False):
        return False

    verified_stable_refutation = bool(
        evidence.get("retrieved_live", False)
        and not evidence.get("cache_allowed", True)
        and str(evidence.get("stable_relation_verdict", "")).upper()
        == "REFUTES"
        and str(evidence.get("verified_relation", "")) != "none"
    )

    if verified_stable_refutation:
        return True

    approved_pib_refutation = bool(
        evidence.get("legal_cache_validation_passed", False)
        and str(evidence.get("record_verdict", "")).casefold() == "refutes"
        and float(evidence.get("cache_match_score", 0.0) or 0.0)
        >= MINIMUM_PIB_CACHE_MATCH_SCORE
    )

    if approved_pib_refutation:
        return True

    scores = evidence.get("nli_scores", {})
    entailment = float(scores.get("entailment", 0.0))
    contradiction = float(scores.get("contradiction", 0.0))
    neutral = float(scores.get("neutral", 0.0))

    return bool(
        contradiction >= REFUTE_THRESHOLD
        and contradiction - max(entailment, neutral) >= MINIMUM_SCORE_MARGIN
    )


def unique_source_ids(evidence_items: list[dict[str, Any]]) -> set[str]:
    source_ids: set[str] = set()

    for item in evidence_items:
        source_id = str(item.get("source_id", "")).strip()
        source_url = str(item.get("source_url", "")).strip()

        if source_id:
            source_ids.add(source_id)
        elif source_url:
            source_ids.add(source_url)

    return source_ids


def best_score(evidence_items: list[dict[str, Any]], score_name: str) -> float:
    if not evidence_items:
        return 0.0

    return max(
        max(
            float(item.get("nli_scores", {}).get(score_name, 0.0)),
            (
                PIB_CACHE_VERDICT_CONFIDENCE
                if score_name == "contradiction"
                and item.get("legal_cache_validation_passed", False)
                and str(item.get("record_verdict", "")).casefold()
                == "refutes"
                and float(item.get("cache_match_score", 0.0) or 0.0)
                >= MINIMUM_PIB_CACHE_MATCH_SCORE
                else 0.0
            ),
            (
                0.80
                if score_name == "entailment"
                and str(item.get("stable_relation_verdict", "")).upper()
                == "SUPPORTS"
                and item.get("retrieved_live", False)
                and not item.get("cache_allowed", True)
                else 0.0
            ),
            (
                0.80
                if score_name == "contradiction"
                and str(item.get("stable_relation_verdict", "")).upper()
                == "REFUTES"
                and item.get("retrieved_live", False)
                and not item.get("cache_allowed", True)
                else 0.0
            ),
        )
        for item in evidence_items
    )


def make_public_evidence(
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    public_items: list[dict[str, Any]] = []

    for item in evidence_items:
        public_items.append(
            {
                "source_id": item.get("source_id"),
                "source_name": item.get("source_name"),
                "source_type": item.get("source_type"),
                "official_source": item.get("official_source", False),
                "trust_tier": item.get("trust_tier"),
                "title": item.get("title"),
                "source_url": item.get("source_url"),
                "relevance_score": item.get("relevance_score"),
                "alignment_passed": item.get("alignment_passed", False),
                "alignment_score": item.get("alignment_score", 0.0),
                "alignment_reasons": item.get("alignment_reasons", []),
                "legal_cache_approved": item.get(
                    "legal_cache_approved",
                    False,
                ),
                "legal_cache_validation_passed": item.get(
                    "legal_cache_validation_passed",
                    False,
                ),
                "legal_cache_validation_reasons": item.get(
                    "legal_cache_validation_reasons",
                    [],
                ),
                "cache_policy_version": item.get("cache_policy_version"),
                "record_verdict": item.get("record_verdict"),
                "cache_match_score": item.get("cache_match_score"),
                "copyright_policy_url": item.get("copyright_policy_url"),
                "historical_only": item.get("historical_only", False),
                "allowed_claim_years": item.get("allowed_claim_years", []),
                "attribution": item.get("attribution"),
                "retrieved_live": item.get("retrieved_live", False),
                "cache_allowed": item.get("cache_allowed", False),
                "stable_relation_verdict": item.get(
                    "stable_relation_verdict"
                ),
                "verified_relation": item.get("verified_relation"),
                "claim_subject": item.get("claim_subject", ""),
                "subject_overlap": item.get("subject_overlap", 0.0),
                "claim_overlap": item.get("claim_overlap", 0.0),
                "nli_scores": item.get("nli_scores", {}),
                "excerpt": item.get("excerpt"),
            }
        )

    return public_items


def source_confirmation(
    evidence_items: list[dict[str, Any]],
    high_impact_claim: bool,
) -> bool:
    if not evidence_items:
        return False

    verified_live_stable_items = [
        item
        for item in evidence_items
        if item.get("alignment_passed", False)
        and item.get("retrieved_live", False)
        and not item.get("cache_allowed", True)
        and int(item.get("trust_tier", 99) or 99) <= 2
        and str(item.get("stable_relation_verdict", "")).upper()
        in {"SUPPORTS", "REFUTES"}
        and str(item.get("verified_relation", "")) != "none"
    ]

    if verified_live_stable_items and not high_impact_claim:
        return True

    official_items = [
        item
        for item in evidence_items
        if item.get("official_source", False)
        and (
            not is_persistent_snapshot(item)
            or item.get("legal_cache_validation_passed", False)
        )
    ]

    if high_impact_claim:
        return bool(official_items)

    if official_items:
        return True

    high_quality_items = [
        item for item in evidence_items if is_high_quality_source(item)
    ]

    return bool(
        high_quality_items
        and len(unique_source_ids(evidence_items)) >= 2
    )


def analyze_fact_check(text: str) -> dict[str, Any]:
    claim = normalize_text(text)

    if not claim:
        return {
            "available": True,
            "category": NORMAL_CATEGORY,
            "evidence_status": "NOT_EVALUATED",
            "confidence": 0.50,
            "action": "Allow",
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "policy_violation": False,
            "reason": "No readable factual claim was supplied.",
            "evidence": [],
            "warnings": [],
            "stable_knowledge_eligible": False,
            "stable_knowledge_topic": None,
            "stable_knowledge_sources": [],
            "stable_knowledge_retrieval_mode": "not_used",
            "stable_knowledge_cache_allowed": False,
            "stable_knowledge_persistent_cache_used": False,
            "stable_knowledge_v3_structured_retrieval_used": False,
            "stable_knowledge_v3_legacy_fallback_used": False,
            "stable_knowledge_v3_structured_verdict": None,
            "stable_knowledge_v3_parser_relation": "unknown",
            "stable_knowledge_v3_parser_subject": "",
            "stable_knowledge_v3_parser_object": "",
            "engine_version": "india-world-english-v3.4-rc2-development",
        }

    stable_knowledge_result = retrieve_stable_knowledge_v3(claim)

    if stable_knowledge_result.get("eligible", False):
        retrieval_result = {
            "evidence": [],
            "warnings": [],
            "high_impact_claim": False,
            "confidence_cap": float(
                stable_knowledge_result.get("confidence_cap", 0.80) or 0.80
            ),
            "india_context_detected": False,
            "topics": [stable_knowledge_result.get("topic")],
        }
    else:
        retrieval_result = retrieve_fact_check_evidence(claim)

    all_retrieved_evidence = [
        *list(retrieval_result.get("evidence", [])),
        *list(stable_knowledge_result.get("evidence", [])),
    ]

    approved_pib_cache_items = [
        item
        for item in all_retrieved_evidence
        if is_persistent_snapshot(item)
        and evidence_is_usable(claim, item)
    ]

    rejected_persistent_items = [
        item
        for item in all_retrieved_evidence
        if is_persistent_snapshot(item)
        and not evidence_is_usable(claim, item)
    ]

    usable_evidence = [
        item
        for item in all_retrieved_evidence
        if not is_persistent_snapshot(item)
        or evidence_is_usable(claim, item)
    ][:MAX_EVIDENCE_TO_ANALYZE]

    analyzed_evidence = analyze_evidence_batch(claim, usable_evidence)

    support_evidence = [
        item for item in analyzed_evidence if is_strong_support(item)
    ]
    refute_evidence = [
        item for item in analyzed_evidence if is_strong_refutation(item)
    ]

    verified_stable_support = [
        item
        for item in analyzed_evidence
        if item.get("alignment_passed", False)
        and item.get("retrieved_live", False)
        and not item.get("cache_allowed", True)
        and int(item.get("trust_tier", 99) or 99) <= 2
        and str(item.get("stable_relation_verdict", "")).upper()
        == "SUPPORTS"
        and str(item.get("verified_relation", "")) != "none"
    ]
    verified_stable_refutations = [
        item
        for item in analyzed_evidence
        if item.get("alignment_passed", False)
        and item.get("retrieved_live", False)
        and not item.get("cache_allowed", True)
        and int(item.get("trust_tier", 99) or 99) <= 2
        and str(item.get("stable_relation_verdict", "")).upper()
        == "REFUTES"
        and str(item.get("verified_relation", "")) != "none"
    ]

    if verified_stable_support and not verified_stable_refutations:
        support_evidence = list(
            {
                str(item.get("source_id", index)): item
                for index, item in enumerate(
                    [*support_evidence, *verified_stable_support]
                )
            }.values()
        )
        refute_evidence = []
    elif verified_stable_refutations and not verified_stable_support:
        refute_evidence = list(
            {
                str(item.get("source_id", index)): item
                for index, item in enumerate(
                    [*refute_evidence, *verified_stable_refutations]
                )
            }.values()
        )
        support_evidence = []

    support_sources = unique_source_ids(support_evidence)
    refute_sources = unique_source_ids(refute_evidence)

    support_score = best_score(support_evidence, "entailment")
    refute_score = best_score(refute_evidence, "contradiction")

    if verified_stable_support:
        support_score = max(
            support_score,
            float(stable_knowledge_result.get("confidence", 0.0) or 0.0),
        )

    if verified_stable_refutations:
        refute_score = max(
            refute_score,
            float(stable_knowledge_result.get("confidence", 0.0) or 0.0),
        )

    high_impact_claim = bool(retrieval_result.get("high_impact_claim", False))
    confidence_cap = float(retrieval_result.get("confidence_cap", 0.80) or 0.80)

    support_confirmed = source_confirmation(
        support_evidence,
        high_impact_claim,
    )
    refutation_confirmed = source_confirmation(
        refute_evidence,
        high_impact_claim,
    )

    evidence_conflict_detected = bool(support_evidence and refute_evidence)

    if evidence_conflict_detected:
        evidence_status = "CONFLICTING_EVIDENCE"
        category = UNCERTAIN_CATEGORY
        confidence = 0.50
        action = "Refer to human review"
        human_review_required = True
        reason = (
            "Aligned evidence produced both strong support and strong "
            "refutation. The system will not select one side automatically."
        )

    elif refutation_confirmed:
        evidence_status = "REFUTES"
        category = MISINFORMATION_CATEGORY
        confidence = min(refute_score, confidence_cap)
        action = "Refer to human review"
        human_review_required = True
        reason = (
            "Relevant evidence from an acceptable live source appears to "
            "contradict the claim. No automatic enforcement is permitted."
        )

    elif support_confirmed:
        evidence_status = "SUPPORTS"
        category = NORMAL_CATEGORY
        confidence = min(support_score, confidence_cap)
        action = "Allow"
        human_review_required = False
        reason = (
            "Relevant evidence from sufficient live sources appears to "
            "support the claim."
        )

    else:
        evidence_status = "NOT_ENOUGH_INFO"
        category = UNCERTAIN_CATEGORY
        confidence = 0.55 if analyzed_evidence else 0.50
        action = "Refer to human review"
        human_review_required = True

        if high_impact_claim:
            reason = (
                "This is a high-impact claim, but relevant live official "
                "evidence was unavailable or insufficient."
            )
        else:
            reason = (
                "The available live evidence was missing, mismatched, weak, "
                "or did not meet the independent-source requirement."
            )

    warnings = [
        *list(retrieval_result.get("warnings", [])),
        *list(stable_knowledge_result.get("warnings", [])),
    ]

    if approved_pib_cache_items:
        warnings = [
            warning
            for warning in warnings
            if not str(warning).startswith(
                "A non-Indian election claim requires"
            )
        ]

    if rejected_persistent_items:
        warnings.append(
            f"Excluded {len(rejected_persistent_items)} unapproved, expired, "
            "mismatched or non-PIB cached evidence item(s) from the decision."
        )

    if approved_pib_cache_items:
        warnings.append(
            f"Used {len(approved_pib_cache_items)} approved PIB Fact Check "
            "historical cache item(s), subject to date and attribution rules."
        )
        warnings.append(
            "An approved PIB record verdict may confirm a refutation only "
            "after record-level allowlisting, subject matching and historical "
            "year matching. It never permits automatic enforcement."
        )

    aligned_evidence = [
        item for item in analyzed_evidence if item.get("alignment_passed", False)
    ]
    rejected_evidence = [
        item for item in analyzed_evidence if not item.get("alignment_passed", False)
    ]

    accepted_official_evidence = [
        item
        for item in aligned_evidence
        if item.get("official_source", False)
        and (
            not is_persistent_snapshot(item)
            or item.get("legal_cache_validation_passed", False)
        )
    ]

    accepted_official_names = sorted(
        {
            str(item.get("source_name", "")).strip()
            for item in accepted_official_evidence
            if str(item.get("source_name", "")).strip()
        }
    )

    if high_impact_claim and not accepted_official_evidence:
        warnings.append(
            "No sufficiently aligned live official source or approved PIB "
            "Fact Check record was available for this high-impact claim."
        )

    warnings = list(dict.fromkeys(warnings))

    return {
        "available": True,
        "category": category,
        "evidence_status": evidence_status,
        "confidence": round(float(confidence), 2),
        "action": action,
        "human_review_required": human_review_required,
        "automatic_enforcement_allowed": False,
        "policy_violation": False,
        "reason": reason,
        "claim": claim,
        "india_context_detected": bool(
            retrieval_result.get("india_context_detected", False)
            or approved_pib_cache_items
        ),
        "high_impact_claim": high_impact_claim,
        "topics": retrieval_result.get("topics", []),
        "confidence_cap": confidence_cap,
        "official_sources_consulted": bool(accepted_official_evidence),
        "official_source_names": accepted_official_names,
        "relevant_official_sources_found": bool(accepted_official_evidence),
        "relevant_official_source_names": accepted_official_names,
        "support_score": round(support_score, 4),
        "refute_score": round(refute_score, 4),
        "support_source_count": len(support_sources),
        "refute_source_count": len(refute_sources),
        "evidence_conflict_detected": evidence_conflict_detected,
        "evidence_retrieved": len(all_retrieved_evidence),
        "evidence_analyzed": len(analyzed_evidence),
        "evidence_aligned": len(aligned_evidence),
        "evidence_rejected_as_mismatched": len(rejected_evidence),
        "approved_pib_cache_count": len(approved_pib_cache_items),
        "approved_pib_cache_used": bool(approved_pib_cache_items),
        "stable_knowledge_eligible": bool(
            stable_knowledge_result.get("eligible", False)
        ),
        "stable_knowledge_topic": stable_knowledge_result.get("topic"),
        "stable_knowledge_sources": stable_knowledge_result.get(
            "source_names",
            [],
        ),
        "stable_knowledge_retrieval_mode": stable_knowledge_result.get(
            "retrieval_mode",
            "not_used",
        ),
        "stable_knowledge_cache_allowed": False,
        "stable_knowledge_persistent_cache_used": False,
        "stable_knowledge_v3_structured_retrieval_used": bool(
            stable_knowledge_result.get("structured_retrieval_used", False)
        ),
        "stable_knowledge_v3_legacy_fallback_used": bool(
            stable_knowledge_result.get("legacy_live_retrieval_used", False)
        ),
        "stable_knowledge_v3_structured_verdict": (
            stable_knowledge_result.get("structured_verdict")
        ),
        "stable_knowledge_v3_parser_relation": (
            stable_knowledge_result.get("parsed_claim", {}).get("relation")
        ),
        "stable_knowledge_v3_parser_subject": (
            stable_knowledge_result.get("parsed_claim", {}).get("subject")
        ),
        "stable_knowledge_v3_parser_object": (
            stable_knowledge_result.get("parsed_claim", {}).get("object")
        ),
        "persistent_snapshot_count_excluded": len(rejected_persistent_items),
        "evidence": make_public_evidence(analyzed_evidence),
        "warnings": warnings,
        "model_name": MODEL_NAME,
        "engine_version": "india-world-english-v3.4-rc2-development",
    }
