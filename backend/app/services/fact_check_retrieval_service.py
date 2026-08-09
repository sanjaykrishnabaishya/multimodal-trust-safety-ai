from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from lxml import html as lxml_html
from sklearn.feature_extraction.text import (
    TfidfVectorizer,
)
from sklearn.metrics.pairwise import (
    cosine_similarity,
)

from app.services.fact_check_source_registry import (
    SOURCE_REGISTRY,
    build_fact_check_source_plan,
)

from app.services.official_evidence_cache_service import (
    retrieve_official_cached_evidence,
)


USER_AGENT = (
    "TrustSafetyAI/1.0 "
    "(https://github.com/"
    "sanjaykrishnabaishya/"
    "multimodal-trust-safety-ai; "
    "educational fact-checking project)"
)

REQUEST_TIMEOUT = 30

MAX_EVIDENCE_ITEMS = 12
MAX_WIKIPEDIA_PAGES = 10
MAX_PAGE_CHARACTERS = 30000

MINIMUM_RELEVANCE_SCORE = 0.04
OFFICIAL_SOURCE_RELEVANCE_SCORE = 0.08

HTTP_CACHE_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "storage"
    / "fact_check"
    / "http_cache"
)

HTTP_CACHE_TTL_SECONDS = 86400
MINIMUM_REQUEST_INTERVAL_SECONDS = 0.8
MAXIMUM_REQUEST_ATTEMPTS = 3

_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_TIME = 0.0


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
}


WORLD_BANK_INDICATORS = {
    "population": {
        "indicator": "SP.POP.TOTL",
        "name": "Population, total",
    },

    "gdp": {
        "indicator": "NY.GDP.MKTP.CD",
        "name": "GDP, current US dollars",
    },

    "inflation": {
        "indicator": "FP.CPI.TOTL.ZG",
        "name": (
            "Inflation, consumer prices "
            "annual percent"
        ),
    },

    "unemployment": {
        "indicator": "SL.UEM.TOTL.ZS",
        "name": (
            "Unemployment, total percent "
            "of total labour force"
        ),
    },

    "life_expectancy": {
        "indicator": "SP.DYN.LE00.IN",
        "name": "Life expectancy at birth",
    },
}


def normalize_text(
    text: str,
) -> str:
    return " ".join(
        str(text or "").split()
    )


def tokenize(
    text: str,
) -> list[str]:
    return [
        token.casefold()
        for token in re.findall(
            r"[A-Za-z0-9][A-Za-z0-9'’-]*",
            text,
        )
        if token.casefold()
        not in STOP_WORDS
    ]


def build_search_queries(
    claim: str,
) -> list[str]:
    cleaned_claim = normalize_text(
        claim
    )

    if not cleaned_claim:
        return []

    queries = []

    predicate_pattern = re.compile(
        r"""
        \b
        (?:
            is
            |
            are
            |
            was
            |
            were
            |
            has
            |
            have
            |
            had
            |
            reached
            |
            reaches
            |
            located
            |
            banned
            |
            closed
            |
            became
            |
            contains
            |
            includes
            |
            founded
            |
            created
            |
            invented
            |
            discovered
            |
            announced
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    predicate_match = (
        predicate_pattern.search(
            cleaned_claim
        )
    )

    if predicate_match:
        subject = cleaned_claim[
            :predicate_match.start()
        ]

        subject = re.sub(
            r"^(?:The|A|An)\s+",
            "",
            subject,
            flags=re.IGNORECASE,
        ).strip(" ,.-")

        if len(subject) >= 3:
            queries.append(subject)

    capitalized_phrases = re.findall(
        r"""
        \b
        (?:
            [A-Z][A-Za-z0-9'’-]*
            (?:
                \s+
                [A-Z][A-Za-z0-9'’-]*
            ){0,5}
        )
        \b
        """,
        cleaned_claim,
        re.VERBOSE,
    )

    for phrase in capitalized_phrases:
        phrase = re.sub(
            r"^(?:The|A|An)\s+",
            "",
            phrase,
        ).strip()

        if (
            len(phrase) >= 3
            and phrase.casefold()
            not in {
                "the",
                "a",
                "an",
            }
        ):
            queries.append(phrase)

    important_tokens = tokenize(
        cleaned_claim
    )

    if important_tokens:
        queries.append(
            " ".join(
                important_tokens[:8]
            )
        )

    queries.append(cleaned_claim)

    unique_queries = []

    for query in queries:
        query = normalize_text(query)

        if (
            query
            and query.casefold()
            not in {
                existing.casefold()
                for existing
                in unique_queries
            }
        ):
            unique_queries.append(query)

    return unique_queries[:3]


def split_evidence_text(
    text: str,
) -> list[str]:
    cleaned_text = normalize_text(
        text
    )

    if not cleaned_text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        cleaned_text,
    )

    sentences = [
        normalize_text(sentence)
        for sentence in sentences
        if len(
            normalize_text(sentence)
        )
        >= 35
    ]

    chunks = []

    for index, sentence in enumerate(
        sentences
    ):
        combined = sentence

        if index + 1 < len(sentences):
            combined = (
                f"{sentence} "
                f"{sentences[index + 1]}"
            )

        chunks.append(
            combined[:1200]
        )

    return chunks


def _cache_path(
    url: str,
    params: dict[str, Any],
) -> Path:
    serialized_request = json.dumps(
        {
            "url": url,
            "params": params,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    cache_key = hashlib.sha256(
        serialized_request.encode(
            "utf-8"
        )
    ).hexdigest()

    return (
        HTTP_CACHE_DIRECTORY
        / f"{cache_key}.json"
    )


def _read_cached_payload(
    cache_path: Path,
    maximum_age: float | None,
) -> Any | None:
    if not cache_path.exists():
        return None

    try:
        cached_record = json.loads(
            cache_path.read_text(
                encoding="utf-8"
            )
        )

        cached_at = float(
            cached_record.get(
                "cached_at",
                0.0,
            )
        )

        if (
            maximum_age is not None
            and time.time() - cached_at
            > maximum_age
        ):
            return None

        return cached_record.get(
            "payload"
        )

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None


def _write_cached_payload(
    cache_path: Path,
    payload: Any,
) -> None:
    HTTP_CACHE_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        cache_path.with_suffix(
            ".tmp"
        )
    )

    temporary_path.write_text(
        json.dumps(
            {
                "cached_at": time.time(),
                "payload": payload,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        cache_path
    )


def _wait_for_request_slot() -> None:
    global _LAST_REQUEST_TIME

    with _REQUEST_LOCK:
        elapsed = (
            time.monotonic()
            - _LAST_REQUEST_TIME
        )

        remaining_wait = (
            MINIMUM_REQUEST_INTERVAL_SECONDS
            - elapsed
        )

        if remaining_wait > 0:
            time.sleep(
                remaining_wait
            )

        _LAST_REQUEST_TIME = (
            time.monotonic()
        )


def request_any_json(
    url: str,
    params: dict[str, Any],
) -> Any:
    cache_path = _cache_path(
        url,
        params,
    )

    fresh_payload = (
        _read_cached_payload(
            cache_path,
            HTTP_CACHE_TTL_SECONDS,
        )
    )

    if fresh_payload is not None:
        return fresh_payload

    last_error: Exception | None = None

    for attempt in range(
        MAXIMUM_REQUEST_ATTEMPTS
    ):
        try:
            _wait_for_request_slot()

            response = requests.get(
                url,
                params=params,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "application/json"
                    ),
                },
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code in {
                429,
                500,
                502,
                503,
                504,
            }:
                retry_after = (
                    response.headers.get(
                        "Retry-After"
                    )
                )

                try:
                    retry_delay = float(
                        retry_after
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    retry_delay = float(
                        2 ** attempt
                    )

                retry_delay = min(
                    max(
                        retry_delay,
                        1.0,
                    ),
                    15.0,
                )

                if (
                    attempt
                    < MAXIMUM_REQUEST_ATTEMPTS
                    - 1
                ):
                    time.sleep(
                        retry_delay
                    )

                    continue

            response.raise_for_status()

            payload = response.json()

            _write_cached_payload(
                cache_path,
                payload,
            )

            return payload

        except (
            requests.RequestException,
            ValueError,
        ) as error:
            last_error = error

            if (
                attempt
                < MAXIMUM_REQUEST_ATTEMPTS
                - 1
            ):
                time.sleep(
                    min(
                        2 ** attempt,
                        8,
                    )
                )

    stale_payload = (
        _read_cached_payload(
            cache_path,
            None,
        )
    )

    if stale_payload is not None:
        return stale_payload

    if last_error:
        raise last_error

    raise RuntimeError(
        "The evidence source did not "
        "return usable data."
    )


def request_json(
    url: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    payload = request_any_json(
        url,
        params,
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "The source returned invalid JSON."
        )

    return payload


def rank_candidates(
    claim: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    usable_candidates = [
        candidate
        for candidate in candidates
        if normalize_text(
            candidate.get(
                "evidence_text",
                "",
            )
        )
    ]

    if not usable_candidates:
        return []

    documents = [
        claim,
        *[
            candidate[
                "evidence_text"
            ]
            for candidate
            in usable_candidates
        ],
    ]

    try:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            max_features=20000,
        )

        vectors = vectorizer.fit_transform(
            documents
        )

        similarities = cosine_similarity(
            vectors[0:1],
            vectors[1:],
        )[0]

    except ValueError:
        similarities = [
            0.0
            for _ in usable_candidates
        ]

    ranked_candidates = []

    for candidate, similarity in zip(
        usable_candidates,
        similarities,
    ):
        ranked_candidate = dict(
            candidate
        )

        relevance_score = float(
            similarity
        )

        official_source = bool(
            ranked_candidate.get(
                "official_source",
                False,
            )
        )

        trust_tier = int(
            ranked_candidate.get(
                "trust_tier",
                99,
            )
        )

        official_boost = (
            0.12
            if official_source
            else 0.0
        )

        trust_boost = max(
            0.0,
            (4 - trust_tier) * 0.015,
        )

        ranked_candidate[
            "relevance_score"
        ] = round(
            relevance_score,
            4,
        )

        ranked_candidate[
            "_selection_score"
        ] = (
            relevance_score
            + official_boost
            + trust_boost
        )

        ranked_candidate[
            "excerpt"
        ] = normalize_text(
            candidate[
                "evidence_text"
            ]
        )[:500]

        ranked_candidate.pop(
            "evidence_text",
            None,
        )

        ranked_candidates.append(
            ranked_candidate
        )

    ranked_candidates.sort(
        key=lambda item: float(
            item.get(
                "_selection_score",
                0.0,
            )
        ),
        reverse=True,
    )

    selected_candidates = []
    source_counts: dict[str, int] = {}

    for candidate in ranked_candidates:
        relevance_score = float(
            candidate.get(
                "relevance_score",
                0.0,
            )
        )

        official_source = bool(
            candidate.get(
                "official_source",
                False,
            )
        )

        minimum_score = (
            0.015
            if official_source
            else MINIMUM_RELEVANCE_SCORE
        )

        if relevance_score < minimum_score:
            continue

        source_id = str(
            candidate.get(
                "source_id",
                "unknown",
            )
        )

        existing_count = (
            source_counts.get(
                source_id,
                0,
            )
        )

        if existing_count >= 3:
            continue

        candidate.pop(
            "_selection_score",
            None,
        )

        selected_candidates.append(
            candidate
        )

        source_counts[source_id] = (
            existing_count + 1
        )

        if (
            len(selected_candidates)
            >= MAX_EVIDENCE_ITEMS
        ):
            break

    return selected_candidates


def retrieve_wikipedia(
    claim: str,
) -> tuple[
    list[dict[str, Any]],
    list[str],
]:
    source = SOURCE_REGISTRY[
        "wikipedia"
    ]

    warnings = []
    page_ids = []

    queries = build_search_queries(
        claim
    )[:2]

    for query in queries:
        try:
            payload = request_json(
                source["api_url"],
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": 5,
                    "format": "json",
                    "utf8": 1,
                },
            )

            results = (
                payload.get(
                    "query",
                    {},
                ).get(
                    "search",
                    [],
                )
            )

            for result in results:
                page_id = result.get(
                    "pageid"
                )

                if page_id is None:
                    continue

                page_id = int(page_id)

                if page_id not in page_ids:
                    page_ids.append(
                        page_id
                    )

        except (
            requests.RequestException,
            ValueError,
        ) as error:
            warnings.append(
                "Wikipedia search failed: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    page_ids = page_ids[:8]

    if not page_ids:
        return [], warnings

    try:
        payload = request_json(
            source["api_url"],
            {
                "action": "query",
                "pageids": "|".join(
                    str(page_id)
                    for page_id in page_ids
                ),
                "prop": "extracts",
                "explaintext": 1,
                "redirects": 1,
                "format": "json",
                "utf8": 1,
            },
        )

        pages = (
            payload.get(
                "query",
                {},
            ).get(
                "pages",
                {},
            )
        )

        candidates = []

        for page in pages.values():
            title = str(
                page.get(
                    "title",
                    "Wikipedia",
                )
            )

            extract = str(
                page.get(
                    "extract",
                    "",
                )
            )[
                :MAX_PAGE_CHARACTERS
            ]

            page_id = page.get(
                "pageid"
            )

            page_url = (
                "https://en.wikipedia.org/wiki/"
                + quote(
                    title.replace(
                        " ",
                        "_",
                    )
                )
            )

            for chunk in split_evidence_text(
                extract
            ):
                candidates.append(
                    {
                        "source_id": (
                            "wikipedia"
                        ),
                        "source_name": (
                            source["name"]
                        ),
                        "source_type": (
                            source[
                                "source_type"
                            ]
                        ),
                        "trust_tier": (
                            source[
                                "trust_tier"
                            ]
                        ),
                        "official_source": False,
                        "title": title,
                        "source_url": page_url,
                        "page_id": page_id,
                        "evidence_text": chunk,
                    }
                )

        return candidates, warnings

    except (
        requests.RequestException,
        ValueError,
    ) as error:
        warnings.append(
            "Wikipedia page retrieval failed: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        return [], warnings


def retrieve_wikidata(
    claim: str,
) -> tuple[
    list[dict[str, Any]],
    list[str],
]:
    source = SOURCE_REGISTRY[
        "wikidata"
    ]

    warnings = []
    candidates = []
    seen_entities = set()

    queries = build_search_queries(
        claim
    )

    if not queries:
        return [], []

    query = queries[0]

    try:
        payload = request_json(
            source["api_url"],
            {
                "action": (
                    "wbsearchentities"
                ),
                "search": query,
                "language": "en",
                "limit": 8,
                "format": "json",
            },
        )

        for result in payload.get(
            "search",
            [],
        ):
            entity_id = str(
                result.get(
                    "id",
                    "",
                )
            )

            if (
                not entity_id
                or entity_id
                in seen_entities
            ):
                continue

            seen_entities.add(
                entity_id
            )

            label = str(
                result.get(
                    "label",
                    "",
                )
            )

            description = str(
                result.get(
                    "description",
                    "",
                )
            )

            if not description:
                continue

            candidates.append(
                {
                    "source_id": (
                        "wikidata"
                    ),
                    "source_name": (
                        source["name"]
                    ),
                    "source_type": (
                        source[
                            "source_type"
                        ]
                    ),
                    "trust_tier": (
                        source[
                            "trust_tier"
                        ]
                    ),
                    "official_source": False,
                    "title": (
                        f"{label} "
                        f"({entity_id})"
                    ),
                    "source_url": (
                        "https://www.wikidata.org/"
                        f"wiki/{entity_id}"
                    ),
                    "evidence_text": (
                        f"{label}: "
                        f"{description}."
                    ),
                }
            )

    except (
        requests.RequestException,
        ValueError,
    ) as error:
        warnings.append(
            "Wikidata retrieval failed: "
            f"{type(error).__name__}: "
            f"{error}"
        )

    return candidates, warnings


def extract_webpage_text(
    url: str,
) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html",
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    document = lxml_html.fromstring(
        response.content
    )

    for element in document.xpath(
        "//script|//style|//noscript|"
        "//svg|//header|//footer|//nav"
    ):
        parent = element.getparent()

        if parent is not None:
            parent.remove(element)

    return normalize_text(
        document.text_content()
    )[
        :200000
    ]


def retrieve_official_fact_check_page(
    source_id: str,
) -> tuple[
    list[dict[str, Any]],
    list[str],
]:
    source = SOURCE_REGISTRY[
        source_id
    ]

    try:
        page_text = extract_webpage_text(
            source["base_url"]
        )

        candidates = []

        for chunk in split_evidence_text(
            page_text
        ):
            candidates.append(
                {
                    "source_id": source_id,
                    "source_name": (
                        source["name"]
                    ),
                    "source_type": (
                        source[
                            "source_type"
                        ]
                    ),
                    "trust_tier": (
                        source[
                            "trust_tier"
                        ]
                    ),
                    "official_source": True,
                    "title": source["name"],
                    "source_url": (
                        source["base_url"]
                    ),
                    "evidence_text": chunk,
                }
            )

        return candidates, []

    except Exception as error:
        return (
            [],
            [
                (
                    f"{source['name']} retrieval "
                    f"failed: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            ],
        )


@lru_cache(maxsize=1)
def retrieve_world_bank_countries() -> list[
    dict[str, Any]
]:
    source = SOURCE_REGISTRY[
        "world_bank"
    ]

    payload = request_any_json(
        (
            f"{source['api_url']}"
            "country"
        ),
        {
            "format": "json",
            "per_page": 400,
        },
    )

    if (
        not isinstance(payload, list)
        or len(payload) < 2
        or not isinstance(
            payload[1],
            list,
        )
    ):
        return []

    return payload[1]


def detect_world_bank_country(
    claim: str,
) -> tuple[str, str] | None:
    claim_casefolded = (
        claim.casefold()
    )

    if re.search(
        r"\bworld(?:wide)?\b",
        claim_casefolded,
    ):
        return "WLD", "World"

    countries = (
        retrieve_world_bank_countries()
    )

    possible_matches = []

    for country in countries:
        country_name = str(
            country.get(
                "name",
                "",
            )
        ).strip()

        country_code = str(
            country.get(
                "id",
                "",
            )
        ).strip()

        if (
            not country_name
            or not country_code
        ):
            continue

        if (
            country_name.casefold()
            in claim_casefolded
        ):
            possible_matches.append(
                (
                    len(country_name),
                    country_code,
                    country_name,
                )
            )

    if not possible_matches:
        return None

    possible_matches.sort(
        reverse=True
    )

    _, country_code, country_name = (
        possible_matches[0]
    )

    return (
        country_code,
        country_name,
    )


def select_world_bank_indicators(
    claim: str,
    topics: list[str],
) -> list[dict[str, str]]:
    claim_casefolded = (
        claim.casefold()
    )

    selected = []

    if "population" in topics:
        selected.append(
            WORLD_BANK_INDICATORS[
                "population"
            ]
        )

    if "life expectancy" in claim_casefolded:
        selected.append(
            WORLD_BANK_INDICATORS[
                "life_expectancy"
            ]
        )

    if "gdp" in claim_casefolded:
        selected.append(
            WORLD_BANK_INDICATORS[
                "gdp"
            ]
        )

    if "inflation" in claim_casefolded:
        selected.append(
            WORLD_BANK_INDICATORS[
                "inflation"
            ]
        )

    if "unemployment" in claim_casefolded:
        selected.append(
            WORLD_BANK_INDICATORS[
                "unemployment"
            ]
        )

    unique_indicators = []

    for indicator in selected:
        if (
            indicator
            not in unique_indicators
        ):
            unique_indicators.append(
                indicator
            )

    return unique_indicators


def retrieve_world_bank(
    claim: str,
    topics: list[str],
) -> tuple[
    list[dict[str, Any]],
    list[str],
]:
    source = SOURCE_REGISTRY[
        "world_bank"
    ]

    try:
        country = (
            detect_world_bank_country(
                claim
            )
        )

        indicators = (
            select_world_bank_indicators(
                claim,
                topics,
            )
        )

        if not country or not indicators:
            return [], []

        country_code, country_name = (
            country
        )

        candidates = []

        for indicator in indicators:
            endpoint = (
                f"{source['api_url']}"
                f"country/{country_code}/"
                "indicator/"
                f"{indicator['indicator']}"
            )

            payload = request_any_json(
                endpoint,
                {
                    "format": "json",
                    "per_page": 100,
                },
            )

            if (
                not isinstance(
                    payload,
                    list,
                )
                or len(payload) < 2
                or not isinstance(
                    payload[1],
                    list,
                )
            ):
                continue

            latest_record = next(
                (
                    record
                    for record in payload[1]
                    if record.get(
                        "value"
                    )
                    is not None
                ),
                None,
            )

            if not latest_record:
                continue

            value = latest_record.get(
                "value"
            )

            year = latest_record.get(
                "date"
            )

            if isinstance(
                value,
                (int, float),
            ):
                formatted_value = (
                    f"{value:,}"
                )
            else:
                formatted_value = str(
                    value
                )

            candidates.append(
                {
                    "source_id": (
                        "world_bank"
                    ),
                    "source_name": (
                        source["name"]
                    ),
                    "source_type": (
                        source[
                            "source_type"
                        ]
                    ),
                    "trust_tier": (
                        source[
                            "trust_tier"
                        ]
                    ),
                    "official_source": True,
                    "title": (
                        indicator["name"]
                    ),
                    "source_url": endpoint,
                    "evidence_text": (
                        f"According to the World "
                        f"Bank indicator "
                        f"{indicator['name']}, "
                        f"the value for "
                        f"{country_name} was "
                        f"{formatted_value} "
                        f"in {year}."
                    ),
                }
            )

        return candidates, []

    except (
        requests.RequestException,
        ValueError,
    ) as error:
        return (
            [],
            [
                (
                    "World Bank retrieval failed: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            ],
        )


def retrieve_google_fact_checks(
    claim: str,
) -> tuple[
    list[dict[str, Any]],
    list[str],
]:
    source = SOURCE_REGISTRY[
        "google_fact_check"
    ]

    api_key = os.getenv(
        "GOOGLE_FACT_CHECK_API_KEY"
    )

    if not api_key:
        return [], []

    try:
        payload = request_json(
            source["api_url"],
            {
                "query": claim,
                "languageCode": "en",
                "pageSize": 10,
                "key": api_key,
            },
        )

        candidates = []

        for claim_result in payload.get(
            "claims",
            [],
        ):
            checked_claim = str(
                claim_result.get(
                    "text",
                    "",
                )
            )

            claimant = str(
                claim_result.get(
                    "claimant",
                    "",
                )
            )

            for review in claim_result.get(
                "claimReview",
                [],
            ):
                publisher = review.get(
                    "publisher",
                    {},
                )

                publisher_name = str(
                    publisher.get(
                        "name",
                        "Fact-check publisher",
                    )
                )

                rating = str(
                    review.get(
                        "textualRating",
                        "Unrated",
                    )
                )

                review_url = str(
                    review.get(
                        "url",
                        source["base_url"],
                    )
                )

                candidates.append(
                    {
                        "source_id": (
                            "google_fact_check"
                        ),
                        "source_name": (
                            f"{source['name']} — "
                            f"{publisher_name}"
                        ),
                        "source_type": (
                            source[
                                "source_type"
                            ]
                        ),
                        "trust_tier": (
                            source[
                                "trust_tier"
                            ]
                        ),
                        "official_source": False,
                        "title": (
                            f"Published rating: "
                            f"{rating}"
                        ),
                        "source_url": (
                            review_url
                        ),
                        "evidence_text": (
                            f"Previously fact-checked "
                            f"claim: {checked_claim}. "
                            f"Claimant: {claimant}. "
                            f"Published rating: "
                            f"{rating}."
                        ),
                    }
                )

        return candidates, []

    except (
        requests.RequestException,
        ValueError,
    ) as error:
        return (
            [],
            [
                (
                    "Google Fact Check retrieval "
                    f"failed: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )
            ],
        )


def retrieve_fact_check_evidence(
    text: str,
) -> dict[str, Any]:
    claim = normalize_text(text)

    source_plan = (
        build_fact_check_source_plan(
            claim
        )
    )

    if not claim:
        return {
            "available": True,
            "claim": "",
            "retrieval_status": (
                "NO_CLAIM"
            ),
            "evidence_found": False,
            "evidence": [],
            "official_sources_consulted": (
                False
            ),
            "official_source_names": [],
            "automatic_enforcement_allowed": (
                False
            ),
            "warnings": [
                "No claim text was supplied."
            ],
            "source_plan": source_plan,
        }

    all_candidates = []
    warnings = list(
        source_plan.get(
            "warnings",
            [],
        )
    )

    cached_official_candidates, cache_warnings = (
        retrieve_official_cached_evidence(
            claim
        )
    )

    all_candidates.extend(
        cached_official_candidates
    )

    warnings.extend(
        cache_warnings
    )

    wikipedia_candidates, new_warnings = (
        retrieve_wikipedia(claim)
    )

    all_candidates.extend(
        wikipedia_candidates
    )

    warnings.extend(new_warnings)

    wikidata_candidates, new_warnings = (
        retrieve_wikidata(claim)
    )

    all_candidates.extend(
        wikidata_candidates
    )

    warnings.extend(new_warnings)

    recommended_source_ids = {
        source["source_id"]
        for source
        in source_plan.get(
            "recommended_sources",
            [],
        )
    }

    for official_source_id in [
        "pib_fact_check",
        "eci_myth_reality",
    ]:
        if (
            official_source_id
            not in recommended_source_ids
        ):
            continue

        candidates, new_warnings = (
            retrieve_official_fact_check_page(
                official_source_id
            )
        )

        all_candidates.extend(
            candidates
        )

        warnings.extend(new_warnings)

    if (
        "world_bank"
        in recommended_source_ids
    ):
        candidates, new_warnings = (
            retrieve_world_bank(
                claim,
                source_plan.get(
                    "topics",
                    [],
                ),
            )
        )

        all_candidates.extend(
            candidates
        )

        warnings.extend(new_warnings)

    google_candidates, new_warnings = (
        retrieve_google_fact_checks(
            claim
        )
    )

    all_candidates.extend(
        google_candidates
    )

    warnings.extend(new_warnings)

    ranked_evidence = rank_candidates(
        claim,
        all_candidates,
    )

    consulted_official_evidence = [
        evidence
        for evidence in all_candidates
        if evidence.get(
            "official_source",
            False,
        )
    ]

    relevant_official_evidence = [
        evidence
        for evidence in ranked_evidence
        if evidence.get(
            "official_source",
            False,
        )
        and float(
            evidence.get(
                "relevance_score",
                0.0,
            )
        )
        >= OFFICIAL_SOURCE_RELEVANCE_SCORE
    ]

    official_source_names = sorted(
        {
            str(
                evidence[
                    "source_name"
                ]
            )
            for evidence
            in consulted_official_evidence
        }
    )

    relevant_official_source_names = sorted(
        {
            str(
                evidence[
                    "source_name"
                ]
            )
            for evidence
            in relevant_official_evidence
        }
    )

    fact_check_matches = [
        evidence
        for evidence in ranked_evidence
        if evidence.get(
            "source_type"
        )
        in {
            "official_fact_check",
            "fact_check_aggregator",
        }
    ]

    if ranked_evidence:
        retrieval_status = (
            "EVIDENCE_FOUND"
        )
    else:
        retrieval_status = (
            "NOT_ENOUGH_EVIDENCE"
        )

    manual_sources_not_retrieved = [
        source["name"]
        for source
        in source_plan.get(
            "manual_official_sources",
            [],
        )
        if source["source_id"]
        not in {
            "pib_fact_check",
            "eci_myth_reality",
        }
    ]

    if manual_sources_not_retrieved:
        warnings.append(
            "The following recommended official "
            "sources still require a dedicated "
            "retrieval adapter: "
            + ", ".join(
                manual_sources_not_retrieved
            )
            + "."
        )

    return {
        "available": True,
        "claim": claim,
        "retrieval_status": (
            retrieval_status
        ),
        "evidence_found": bool(
            ranked_evidence
        ),
        "evidence_count": len(
            ranked_evidence
        ),
        "evidence": ranked_evidence,
        "fact_check_matches": (
            fact_check_matches
        ),
        "official_sources_consulted": bool(
            consulted_official_evidence
        ),
        "official_source_names": (
            official_source_names
        ),
        "relevant_official_sources_found": bool(
            relevant_official_evidence
        ),
        "relevant_official_source_names": (
            relevant_official_source_names
        ),
        "india_context_detected": (
            source_plan.get(
                "india_context_detected",
                False,
            )
        ),
        "topics": source_plan.get(
            "topics",
            [],
        ),
        "high_impact_claim": (
            source_plan.get(
                "high_impact_claim",
                False,
            )
        ),
        "confidence_cap": (
            source_plan.get(
                "confidence_cap",
                0.80,
            )
        ),
        "automatic_enforcement_allowed": (
            False
        ),
        "warnings": warnings,
        "source_plan": source_plan,
        "limitations": [
            (
                "Retrieved evidence has not yet "
                "been converted into a true, false "
                "or uncertain verdict."
            ),
            (
                "A relevant passage may discuss "
                "the claim without proving or "
                "refuting it."
            ),
            (
                "Freshness, date, location and "
                "scope must be checked before "
                "using evidence."
            ),
        ],
    }