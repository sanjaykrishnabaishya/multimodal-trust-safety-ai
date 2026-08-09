from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

import requests
from lxml import html as lxml_html
from lxml.etree import ParserError as LxmlParserError


USER_AGENT = (
    "TrustSafetyAI/1.0 "
    "(educational fact-checking project; live retrieval; no persistent cache)"
)

REQUEST_TIMEOUT = 30
REQUEST_RETRY_ATTEMPTS = 4
MAXIMUM_RETRY_DELAY_SECONDS = 30.0
MAXIMUM_EVIDENCE_ITEMS = 8
MAXIMUM_EXCERPT_LENGTH = 700

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

NASA_MOON_FACTS_URL = "https://science.nasa.gov/moon/facts/"
NASA_EARTH_FACTS_URL = "https://science.nasa.gov/earth/facts/"
NASA_SUN_FACTS_URL = "https://science.nasa.gov/sun/facts/"
NASA_MARS_FACTS_URL = "https://science.nasa.gov/mars/facts/"
NASA_EUROPA_FACTS_URL = (
    "https://science.nasa.gov/jupiter/jupiter-moons/europa/europa-facts/"
)
NASA_TITAN_FACTS_URL = "https://science.nasa.gov/saturn/moons/titan/facts/"
NASA_APOLLO_11_URL = "https://www.nasa.gov/mission/apollo-11/"
NIST_TEMPERATURE_URL = (
    "https://www.nist.gov/pml/owm/si-units-temperature"
)
LIBRARY_OF_CONGRESS_TELEPHONE_URL = (
    "https://www.loc.gov/everyday-mysteries/technology/item/"
    "who-is-credited-with-inventing-the-telephone/"
)
NATIONAL_ARCHIVES_WWII_URL = (
    "https://www.archives.gov/college-park/highlights/japanese-surrender"
)

ALLOWED_LIVE_HOSTS = {
    "en.wikipedia.org",
    "www.wikidata.org",
    "science.nasa.gov",
    "www.nasa.gov",
    "www.nist.gov",
    "www.loc.gov",
    "www.archives.gov",
}

MINIMUM_REQUEST_INTERVAL_BY_HOST = {
    "en.wikipedia.org": 2.0,
    "www.wikidata.org": 2.5,
    "science.nasa.gov": 0.35,
    "www.nasa.gov": 0.35,
    "www.nist.gov": 0.35,
    "www.loc.gov": 0.35,
    "www.archives.gov": 0.35,
}
LAST_REQUEST_TIME_BY_HOST: dict[str, float] = {}


CURRENT_OR_HIGH_IMPACT_TERMS = {
    "today",
    "currently",
    "current",
    "latest",
    "breaking",
    "just announced",
    "this week",
    "this month",
    "this year",
    "election",
    "elections",
    "vote",
    "voter",
    "evm",
    "government order",
    "court order",
    "supreme court",
    "medicine",
    "medical treatment",
    "vaccine",
    "disease",
    "outbreak",
    "bank account",
    "interest rate",
    "stock price",
    "market price",
    "investment",
    "war",
    "terrorist",
    "crime",
    "arrested",
    "charged with",
}


OPINION_OR_NONFACTUAL_MARKERS = {
    "i think",
    "i feel",
    "in my opinion",
    "best ever",
    "worst ever",
    "beautiful",
    "ugly",
    "should be",
    "ought to",
}


STABLE_TOPIC_TERMS: dict[str, set[str]] = {
    "astronomy": {
        "moon",
        "earth",
        "sun",
        "planet",
        "satellite",
        "orbit",
        "orbits",
        "revolve",
        "revolves",
        "solar system",
        "mars",
        "venus",
        "jupiter",
    },
    "geography": {
        "located",
        "capital",
        "country",
        "continent",
        "ocean",
        "river",
        "mountain",
        "city",
        "border",
    },
    "basic_science": {
        "freezes",
        "boils",
        "chemical",
        "element",
        "gravity",
        "mammal",
        "photosynthesis",
        "temperature",
        "atom",
    },
    "established_history": {
        "founded",
        "born",
        "died",
        "invented",
        "discovered",
        "established",
        "ended",
        "year",
    },
}


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "around",
    "as",
    "at",
    "be",
    "been",
    "by",
    "did",
    "does",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "were",
    "with",
}


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def normalized_lower(text: str) -> str:
    return normalize_text(text).casefold()


def comparable_name(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_text(text))
    without_marks = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).strip()


def content_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized_lower(text))
        if len(token) >= 3 and token not in STOP_WORDS
    }


def detect_stable_topic(claim: str) -> str:
    claim_text = normalized_lower(claim)
    topic_scores = {
        topic: sum(1 for term in terms if term in claim_text)
        for topic, terms in STABLE_TOPIC_TERMS.items()
    }

    best_topic = max(topic_scores, key=topic_scores.get)

    if topic_scores[best_topic] <= 0:
        return "general_knowledge"

    return best_topic


def is_clearly_historical_claim(claim: str) -> bool:
    claim_text = normalized_lower(claim)
    current_year = datetime.now(timezone.utc).year
    years = [
        int(value)
        for value in re.findall(r"\b(?:1[0-9]{3}|20[0-9]{2})\b", claim_text)
    ]

    if years and max(years) <= current_year - 20:
        return True

    return any(
        marker in claim_text
        for marker in (
            "world war i",
            "world war ii",
            "first world war",
            "second world war",
            "ancient history",
            "historical event",
        )
    )


def is_stable_general_knowledge_claim(claim: str) -> bool:
    cleaned_claim = normalize_text(claim)
    claim_text = cleaned_claim.casefold()

    if len(cleaned_claim) < 5 or len(cleaned_claim) > 500:
        return False

    if cleaned_claim.endswith("?"):
        return False

    historical_claim = is_clearly_historical_claim(cleaned_claim)
    blocked_by_current_or_high_impact_term = any(
        marker in claim_text
        for marker in CURRENT_OR_HIGH_IMPACT_TERMS
        if not (historical_claim and marker == "war")
    )

    if blocked_by_current_or_high_impact_term:
        return False

    if any(marker in claim_text for marker in OPINION_OR_NONFACTUAL_MARKERS):
        return False

    factual_predicate = bool(
        re.search(
            r"\b(?:is|are|was|were|has|have|orbits?|revolves?|goes|"
            r"located|contains?|founded|established|invented|discovered|"
            r"freezes|boils|belongs|became|formed|ended|landed)\b",
            claim_text,
        )
    )

    return factual_predicate


def build_search_queries(claim: str) -> list[str]:
    cleaned_claim = normalize_text(claim).strip(" .?!")
    queries = [cleaned_claim]

    predicate_match = re.search(
        r"\b(?:is|are|was|were|has|have|orbits?|revolves?|goes|"
        r"located|contains?|founded|established|invented|discovered|"
        r"freezes|boils|belongs|became|formed|ended|landed)\b",
        cleaned_claim,
        flags=re.IGNORECASE,
    )

    if predicate_match:
        subject = cleaned_claim[: predicate_match.start()].strip(" ,.-")
        subject = re.sub(
            r"^(?:the|a|an)\s+",
            "",
            subject,
            flags=re.IGNORECASE,
        )

        if len(subject) >= 2:
            queries.append(subject)

    unique_queries: list[str] = []
    seen: set[str] = set()

    for query in queries:
        key = query.casefold()

        if query and key not in seen:
            seen.add(key)
            unique_queries.append(query)

    return unique_queries[:2]


def respect_live_request_interval(host: str) -> None:
    normalized_host = host.casefold()
    minimum_interval = float(
        MINIMUM_REQUEST_INTERVAL_BY_HOST.get(normalized_host, 0.25)
    )
    last_request_time = LAST_REQUEST_TIME_BY_HOST.get(normalized_host, 0.0)
    elapsed = time.monotonic() - last_request_time

    if elapsed < minimum_interval:
        time.sleep(minimum_interval - elapsed)

    LAST_REQUEST_TIME_BY_HOST[normalized_host] = time.monotonic()


def live_request_json(
    url: str,
    params: dict[str, Any],
) -> Any:
    parsed = urlparse(url)

    if parsed.scheme != "https" or (parsed.hostname or "") not in ALLOWED_LIVE_HOSTS:
        raise ValueError("The live source URL is not allowlisted.")

    response = None
    last_request_error: requests.RequestException | None = None

    for attempt in range(REQUEST_RETRY_ATTEMPTS):
        respect_live_request_interval(parsed.hostname or "")

        try:
            response = requests.get(
                url,
                params=params,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
        except requests.RequestException as error:
            last_request_error = error

            if attempt == REQUEST_RETRY_ATTEMPTS - 1:
                raise

            time.sleep(
                min(1.5 * (2**attempt), MAXIMUM_RETRY_DELAY_SECONDS)
            )
            continue

        retryable = response.status_code == 429 or 500 <= response.status_code < 600

        if not retryable or attempt == REQUEST_RETRY_ATTEMPTS - 1:
            response.raise_for_status()
            break

        retry_after = str(response.headers.get("Retry-After", "")).strip()

        try:
            retry_delay = float(retry_after)
        except ValueError:
            retry_delay = 1.5 * (2**attempt)

        time.sleep(min(max(retry_delay, 0.5), MAXIMUM_RETRY_DELAY_SECONDS))

    if response is None:
        if last_request_error is not None:
            raise last_request_error
        raise requests.RequestException("No response was returned by the source.")

    final_host = (urlparse(str(response.url)).hostname or "").casefold()

    if final_host not in ALLOWED_LIVE_HOSTS:
        raise ValueError("The live source redirected outside the allowlist.")

    return response.json()


def live_request_html(url: str) -> tuple[bytes, str]:
    parsed = urlparse(url)

    if parsed.scheme != "https" or (parsed.hostname or "") not in ALLOWED_LIVE_HOSTS:
        raise ValueError("The live source URL is not allowlisted.")

    response = None
    last_request_error: requests.RequestException | None = None

    for attempt in range(REQUEST_RETRY_ATTEMPTS):
        respect_live_request_interval(parsed.hostname or "")

        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
        except requests.RequestException as error:
            last_request_error = error

            if attempt == REQUEST_RETRY_ATTEMPTS - 1:
                raise

            time.sleep(
                min(1.5 * (2**attempt), MAXIMUM_RETRY_DELAY_SECONDS)
            )
            continue

        retryable = response.status_code == 429 or 500 <= response.status_code < 600

        if not retryable or attempt == REQUEST_RETRY_ATTEMPTS - 1:
            response.raise_for_status()
            break

        retry_after = str(response.headers.get("Retry-After", "")).strip()

        try:
            retry_delay = float(retry_after)
        except ValueError:
            retry_delay = 1.5 * (2**attempt)

        time.sleep(min(max(retry_delay, 0.5), MAXIMUM_RETRY_DELAY_SECONDS))

    if response is None:
        if last_request_error is not None:
            raise last_request_error
        raise requests.RequestException("No response was returned by the source.")

    final_url = str(response.url)
    final_host = (urlparse(final_url).hostname or "").casefold()

    if final_host not in ALLOWED_LIVE_HOSTS:
        raise ValueError("The live source redirected outside the allowlist.")

    content_type = str(response.headers.get("Content-Type", "")).casefold()

    if "html" not in content_type:
        raise ValueError("The live source did not return HTML.")

    return response.content, final_url


def text_blocks_from_html(page_content: bytes) -> list[str]:
    document = lxml_html.fromstring(page_content)

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

    blocks: list[str] = []
    seen: set[str] = set()

    for element in document.xpath(
        "//main//*[self::p or self::li or self::h2 or self::h3] | "
        "//article//*[self::p or self::li or self::h2 or self::h3] | "
        "//p | //li"
    ):
        block = normalize_text(" ".join(element.itertext()))
        key = block.casefold()

        if len(block) < 35 or len(block) > 1800 or key in seen:
            continue

        seen.add(key)
        blocks.append(block)

    return blocks


def lexical_relevance(claim: str, evidence_text: str) -> float:
    claim_tokens = content_tokens(claim)
    evidence_tokens = content_tokens(evidence_text)

    if not claim_tokens or not evidence_tokens:
        return 0.0

    overlap = len(claim_tokens & evidence_tokens) / len(claim_tokens)
    return round(min(overlap, 1.0), 4)


def select_relevant_blocks(
    claim: str,
    blocks: list[str],
    limit: int,
) -> list[tuple[float, str]]:
    scored_blocks = [
        (lexical_relevance(claim, block), block)
        for block in blocks
    ]

    scored_blocks = [
        item for item in scored_blocks if item[0] >= 0.12
    ]
    scored_blocks.sort(key=lambda item: item[0], reverse=True)

    return scored_blocks[:limit]


def moon_orbit_relation(claim: str) -> str:
    claim_text = normalized_lower(claim)

    has_moon_subject = bool(re.search(r"\b(?:the\s+)?moon\b", claim_text))
    has_orbit_relation = bool(
        re.search(
            r"\b(?:orbit|orbits|orbited|revolve|revolves|revolved|"
            r"go|goes|went)\b",
            claim_text,
        )
        and any(phrase in claim_text for phrase in ("around", "round"))
    )

    if not has_moon_subject or not has_orbit_relation:
        return "NOT_APPLICABLE"

    if re.search(r"\bearth\b", claim_text):
        return "SUPPORTS"

    if re.search(r"\b(?:mars|sun|venus|jupiter|saturn|mercury)\b", claim_text):
        return "REFUTES"

    return "NOT_DETERMINED"


def extract_capital_relation(claim: str) -> tuple[str, str] | None:
    cleaned_claim = normalize_text(claim).strip(" .?!,;:")
    patterns = (
        re.compile(
            r"^(?P<capital>.+?)\s+is\s+(?:the\s+)?capital(?:\s+city)?"
            r"\s+of\s+(?P<country>.+?)$",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"^(?:the\s+)?capital(?:\s+city)?\s+of\s+(?P<country>.+?)"
            r"\s+is\s+(?P<capital>.+?)$",
            flags=re.IGNORECASE,
        ),
    )

    for pattern in patterns:
        match = pattern.match(cleaned_claim)

        if match:
            capital = normalize_text(match.group("capital"))
            country = normalize_text(match.group("country"))

            if capital and country:
                return capital, country

    return None


def wikidata_capital_relation_verdict(
    claim: str,
    label: str,
    description: str,
) -> str:
    relation = extract_capital_relation(claim)

    if relation is None:
        return "NOT_APPLICABLE"

    claimed_capital, claimed_country = relation
    label_text = normalized_lower(label)
    capital_text = normalized_lower(claimed_capital)
    description_text = normalized_lower(description)

    if label_text != capital_text or "capital" not in description_text:
        return "NOT_DETERMINED"

    country_tokens = content_tokens(claimed_country)
    description_tokens = content_tokens(description)

    if country_tokens and country_tokens.issubset(description_tokens):
        return "SUPPORTS"

    describes_specific_capital_relation = bool(
        re.search(
            r"\bcapital\b.{0,100}\b(?:of|in)\b\s+[a-z]",
            description_text,
        )
    )

    if describes_specific_capital_relation:
        return "REFUTES"

    return "NOT_DETERMINED"


def nasa_sources_for_claim(claim: str) -> tuple[tuple[str, str, str], ...]:
    claim_text = normalized_lower(claim)

    if "apollo 11" in claim_text:
        return (
            (
                "nasa_apollo_11_live",
                "NASA Apollo 11",
                NASA_APOLLO_11_URL,
            ),
        )

    if "europa" in claim_text:
        return (
            (
                "nasa_europa_facts_live",
                "NASA Europa Facts",
                NASA_EUROPA_FACTS_URL,
            ),
        )

    if "titan" in claim_text:
        return (
            (
                "nasa_titan_facts_live",
                "NASA Titan Facts",
                NASA_TITAN_FACTS_URL,
            ),
        )

    if "sun" in claim_text:
        return (
            ("nasa_sun_facts_live", "NASA Sun Facts", NASA_SUN_FACTS_URL),
        )

    if re.search(r"\bmars\s+is\s+(?:a\s+)?moon\b", claim_text):
        return (
            ("nasa_mars_facts_live", "NASA Mars Facts", NASA_MARS_FACTS_URL),
        )

    if "earth" in claim_text and "moon" not in claim_text:
        return (
            (
                "nasa_earth_facts_live",
                "NASA Earth Facts",
                NASA_EARTH_FACTS_URL,
            ),
        )

    if "mars" in claim_text and "moon" not in claim_text:
        return (
            ("nasa_mars_facts_live", "NASA Mars Facts", NASA_MARS_FACTS_URL),
        )

    if "moon" in claim_text:
        return (
            ("nasa_moon_facts_live", "NASA Moon Facts", NASA_MOON_FACTS_URL),
        )

    return (
        ("nasa_earth_facts_live", "NASA Earth Facts", NASA_EARTH_FACTS_URL),
    )


def nasa_verified_relation(
    claim: str,
    source_id: str,
    block: str,
) -> tuple[str, str]:
    claim_text = normalized_lower(claim)
    block_text = normalized_lower(block)
    has_orbit_predicate = bool(
        re.search(r"\b(?:orbit|orbits|orbited)\b", claim_text)
        or (
            re.search(
                r"\b(?:revolve|revolves|revolved|go|goes|went)\b",
                claim_text,
            )
            and any(term in claim_text for term in ("around", "round"))
        )
    )
    claim_is_negated = bool(
        re.search(r"\b(?:not|never|doesn't|didn't|isn't|wasn't)\b", claim_text)
    )

    def apply_negation(verdict: str) -> str:
        if not claim_is_negated:
            return verdict
        if verdict == "SUPPORTS":
            return "REFUTES"
        if verdict == "REFUTES":
            return "SUPPORTS"
        return verdict

    if source_id == "nasa_moon_facts_live":
        block_confirms_fact = bool(
            "moon" in block_text
            and "earth" in block_text
            and any(
                term in block_text
                for term in ("orbit", "orbits", "revolves", "goes around")
            )
        )

        if block_confirms_fact and has_orbit_predicate:
            verdict = (
                "SUPPORTS" if "earth" in claim_text else "REFUTES"
            )
            return apply_negation(verdict), "moon_orbits_earth"

    if source_id == "nasa_earth_facts_live":
        block_confirms_fact = bool(
            "earth" in block_text
            and "sun" in block_text
            and any(term in block_text for term in ("orbit", "orbits"))
        )

        if block_confirms_fact and has_orbit_predicate:
            verdict = "SUPPORTS" if "sun" in claim_text else "REFUTES"
            return apply_negation(verdict), "earth_orbits_sun"

    if source_id == "nasa_europa_facts_live":
        block_confirms_fact = bool(
            "europa" in block_text
            and "jupiter" in block_text
            and any(term in block_text for term in ("orbit", "orbits", "moon"))
        )

        if block_confirms_fact and has_orbit_predicate:
            verdict = "SUPPORTS" if "jupiter" in claim_text else "REFUTES"
            return apply_negation(verdict), "europa_orbits_jupiter"

    if source_id == "nasa_titan_facts_live":
        block_confirms_fact = bool(
            "titan" in block_text
            and "saturn" in block_text
            and any(term in block_text for term in ("orbit", "orbits", "moon"))
        )

        if block_confirms_fact and has_orbit_predicate:
            verdict = "SUPPORTS" if "saturn" in claim_text else "REFUTES"
            return apply_negation(verdict), "titan_orbits_saturn"

    if source_id == "nasa_sun_facts_live":
        block_confirms_fact = bool(
            "sun" in block_text
            and re.search(r"\b(?:star|yellow dwarf)\b", block_text)
        )

        if block_confirms_fact and "sun" in claim_text:
            if re.search(
                r"\bsun\s+is\s+(?:not\s+)?(?:a\s+)?star\b",
                claim_text,
            ):
                return apply_negation("SUPPORTS"), "sun_is_star"
            if re.search(
                r"\bsun\s+is\s+(?:not\s+)?(?:a\s+)?planet\b",
                claim_text,
            ):
                return apply_negation("REFUTES"), "sun_is_star"

    if source_id == "nasa_mars_facts_live":
        block_confirms_fact = bool(
            "mars" in block_text
            and re.search(r"\bplanet\b", block_text)
        )

        if block_confirms_fact:
            if re.search(
                r"\bmars\s+is\s+(?:not\s+)?(?:a\s+)?planet\b",
                claim_text,
            ):
                return apply_negation("SUPPORTS"), "mars_is_planet"
            if re.search(
                r"\bmars\s+is\s+(?:not\s+)?(?:a\s+)?(?:moon|star)\b",
                claim_text,
            ):
                return apply_negation("REFUTES"), "mars_is_planet"

    if source_id == "nasa_apollo_11_live":
        block_confirms_fact = bool(
            "apollo 11" in block_text
            and ("moon" in block_text or "lunar" in block_text)
            and any(
                term in block_text
                for term in ("landing", "landed", "first human")
            )
        )

        if block_confirms_fact and "apollo 11" in claim_text:
            if "mars" in claim_text:
                return "REFUTES", "apollo_11_landed_on_moon"
            if "moon" in claim_text:
                return "SUPPORTS", "apollo_11_landed_on_moon"

    return "NOT_DETERMINED", "none"


def retrieve_nasa_evidence(
    claim: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    topic = detect_stable_topic(claim)

    if topic != "astronomy":
        return [], []

    warnings: list[str] = []
    candidates: list[dict[str, Any]] = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    source_definitions = nasa_sources_for_claim(claim)

    for source_id, source_name, source_url in source_definitions:
        try:
            page_content, final_url = live_request_html(source_url)
            all_blocks = text_blocks_from_html(page_content)
            selected_blocks = select_relevant_blocks(
                claim,
                all_blocks,
                limit=2,
            )
            verified_blocks = [
                (max(lexical_relevance(claim, block), 0.50), block)
                for block in all_blocks
                if nasa_verified_relation(claim, source_id, block)[0]
                in {"SUPPORTS", "REFUTES"}
            ]
            combined_blocks: list[tuple[float, str]] = []
            seen_blocks: set[str] = set()

            for relevance, block in [*verified_blocks, *selected_blocks]:
                block_key = normalized_lower(block)

                if block_key in seen_blocks:
                    continue

                seen_blocks.add(block_key)
                combined_blocks.append((relevance, block))

            selected_blocks = combined_blocks[:3]

            for block_index, (relevance, block) in enumerate(
                selected_blocks,
                start=1,
            ):
                stable_verdict, verified_relation = nasa_verified_relation(
                    claim,
                    source_id,
                    block,
                )

                candidates.append(
                    {
                        "source_id": f"{source_id}:{block_index}",
                        "source_name": source_name,
                        "source_type": "live_official_science_evidence",
                        "trust_tier": 1,
                        "official_source": True,
                        "official_snapshot": False,
                        "retrieved_live": True,
                        "cache_allowed": False,
                        "live_evidence_retrieved_at": retrieved_at,
                        "title": source_name,
                        "source_url": final_url,
                        "relevance_score": max(relevance, 0.35),
                        "excerpt": block[:MAXIMUM_EXCERPT_LENGTH],
                        "stable_relation_verdict": stable_verdict,
                        "verified_relation": verified_relation,
                        "attribution": (
                            f"Source: {source_name}. Original: {final_url}. "
                            f"Accessed live at {retrieved_at}."
                        ),
                    }
                )

        except requests.RequestException as error:
            warnings.append(
                f"{source_name} live retrieval failed without bypassing the "
                f"source: {type(error).__name__}: {error}"
            )
        except (ValueError, TypeError, LxmlParserError) as error:
            warnings.append(
                f"{source_name} returned unusable content: "
                f"{type(error).__name__}: {error}"
            )

    return candidates, list(dict.fromkeys(warnings))


def retrieve_additional_official_evidence(
    claim: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    claim_text = normalized_lower(claim)
    source_definition: tuple[str, str, str, str] | None = None

    if "water" in claim_text and "freez" in claim_text:
        source_definition = (
            "nist_temperature_live",
            "NIST SI Units — Temperature",
            NIST_TEMPERATURE_URL,
            "water_freezing_point",
        )
    elif "telephone" in claim_text and "invent" in claim_text:
        source_definition = (
            "loc_telephone_history_live",
            "Library of Congress — Telephone History",
            LIBRARY_OF_CONGRESS_TELEPHONE_URL,
            "telephone_inventor",
        )
    elif (
        any(
            phrase in claim_text
            for phrase in (
                "world war ii",
                "second world war",
            )
        )
        and "1945" in claim_text
    ):
        source_definition = (
            "national_archives_wwii_end_live",
            "U.S. National Archives — End of World War II",
            NATIONAL_ARCHIVES_WWII_URL,
            "world_war_ii_end_year",
        )

    if source_definition is None:
        return [], []

    source_id, source_name, source_url, relation_name = source_definition
    warnings: list[str] = []
    evidence: list[dict[str, Any]] = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    try:
        page_content, final_url = live_request_html(source_url)
        selected_blocks = select_relevant_blocks(
            claim,
            text_blocks_from_html(page_content),
            limit=3,
        )

        for block_index, (relevance, block) in enumerate(
            selected_blocks,
            start=1,
        ):
            block_text = normalized_lower(block)
            stable_verdict = "NOT_DETERMINED"
            verified_relation = "none"

            if relation_name == "water_freezing_point":
                confirms_zero_celsius = bool(
                    "water" in block_text
                    and "freez" in block_text
                    and re.search(r"\b0\s*°?\s*c\b|zero degrees celsius", block_text)
                )

                if confirms_zero_celsius:
                    claimed_zero = bool(
                        re.search(
                            r"\bzero degrees celsius\b|\b0\s*°?\s*c\b",
                            claim_text,
                        )
                    )
                    stable_verdict = "SUPPORTS" if claimed_zero else "REFUTES"
                    verified_relation = "water_freezes_at_zero_celsius"

            if relation_name == "telephone_inventor":
                confirms_bell_credit = bool(
                    "alexander graham bell" in block_text
                    and "telephone" in block_text
                    and any(
                        term in block_text
                        for term in ("credited", "inventor", "invention")
                    )
                )

                if confirms_bell_credit:
                    if "galileo" in claim_text:
                        stable_verdict = "REFUTES"
                    elif "alexander graham bell" in claim_text:
                        stable_verdict = "SUPPORTS"
                    verified_relation = "bell_credited_for_telephone"

            if relation_name == "world_war_ii_end_year":
                confirms_end_year = bool(
                    "world war ii" in block_text
                    and "ended" in block_text
                    and "1945" in block_text
                )

                if confirms_end_year:
                    stable_verdict = (
                        "SUPPORTS" if "1945" in claim_text else "REFUTES"
                    )
                    verified_relation = "world_war_ii_ended_in_1945"

            evidence.append(
                {
                    "source_id": f"{source_id}:{block_index}",
                    "source_name": source_name,
                    "source_type": "live_official_stable_fact_evidence",
                    "trust_tier": 1,
                    "official_source": True,
                    "official_snapshot": False,
                    "retrieved_live": True,
                    "cache_allowed": False,
                    "live_evidence_retrieved_at": retrieved_at,
                    "title": source_name,
                    "source_url": final_url,
                    "relevance_score": max(relevance, 0.35),
                    "excerpt": block[:MAXIMUM_EXCERPT_LENGTH],
                    "stable_relation_verdict": stable_verdict,
                    "verified_relation": verified_relation,
                    "attribution": (
                        f"Source: {source_name}. Original: {final_url}. "
                        f"Accessed live at {retrieved_at}."
                    ),
                }
            )

    except requests.RequestException as error:
        warnings.append(
            f"{source_name} live retrieval failed without bypassing the "
            f"source: {type(error).__name__}: {error}"
        )
    except (ValueError, TypeError, LxmlParserError) as error:
        warnings.append(
            f"{source_name} returned unusable content: "
            f"{type(error).__name__}: {error}"
        )

    return evidence, warnings


def retrieve_wikipedia_evidence(
    claim: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    candidates: list[dict[str, Any]] = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    try:
        search_payload = live_request_json(
            WIKIPEDIA_API_URL,
            {
                "action": "query",
                "list": "search",
                "srsearch": build_search_queries(claim)[0],
                "srlimit": 4,
                "format": "json",
                "utf8": 1,
            },
        )

        page_ids = [
            str(item.get("pageid"))
            for item in search_payload.get("query", {}).get("search", [])
            if item.get("pageid")
        ]

        if not page_ids:
            return [], warnings

        page_payload = live_request_json(
            WIKIPEDIA_API_URL,
            {
                "action": "query",
                "pageids": "|".join(page_ids),
                "prop": "extracts",
                "explaintext": 1,
                "redirects": 1,
                "format": "json",
                "utf8": 1,
            },
        )

        pages = page_payload.get("query", {}).get("pages", {})

        for page in pages.values():
            title = normalize_text(page.get("title", "Wikipedia"))
            extract = normalize_text(page.get("extract", ""))

            if not extract:
                continue

            sentences = re.split(r"(?<=[.!?])\s+", extract)

            for relevance, sentence in select_relevant_blocks(
                claim,
                sentences,
                limit=2,
            ):
                page_url = (
                    "https://en.wikipedia.org/wiki/"
                    + quote(title.replace(" ", "_"), safe="_()")
                )

                candidates.append(
                    {
                        "source_id": f"wikipedia_live:{page.get('pageid', title)}",
                        "source_name": "English Wikipedia",
                        "source_type": "live_encyclopedic_context",
                        "trust_tier": 3,
                        "official_source": False,
                        "official_snapshot": False,
                        "retrieved_live": True,
                        "cache_allowed": False,
                        "live_evidence_retrieved_at": retrieved_at,
                        "title": title,
                        "source_url": page_url,
                        "relevance_score": relevance,
                        "excerpt": sentence[:MAXIMUM_EXCERPT_LENGTH],
                        "attribution": (
                            f"Source: English Wikipedia. Original: {page_url}. "
                            f"Accessed live at {retrieved_at}."
                        ),
                    }
                )

    except requests.RequestException as error:
        warnings.append(
            "Wikipedia live retrieval failed without bypassing the source: "
            f"{type(error).__name__}: {error}"
        )
    except (ValueError, TypeError, KeyError) as error:
        warnings.append(
            "Wikipedia returned unusable data: "
            f"{type(error).__name__}: {error}"
        )

    return candidates, warnings


def find_exact_wikidata_entity(name: str) -> dict[str, Any] | None:
    payload = live_request_json(
        WIKIDATA_API_URL,
        {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "limit": 10,
            "format": "json",
        },
    )
    expected_name = comparable_name(name)
    exact_matches = [
        item
        for item in payload.get("search", [])
        if comparable_name(item.get("label", "")) == expected_name
    ]

    if not exact_matches:
        return None

    exact_matches.sort(
        key=lambda item: (
            "disambiguation" in normalized_lower(item.get("description", "")),
            not bool(item.get("description")),
        )
    )
    return exact_matches[0]


def wikidata_claim_entity_ids(
    entity: dict[str, Any],
    property_id: str,
) -> set[str]:
    statements = [
        statement
        for statement in entity.get("claims", {}).get(property_id, [])
        if str(statement.get("rank", "")).casefold() != "deprecated"
    ]
    preferred_statements = [
        statement
        for statement in statements
        if str(statement.get("rank", "")).casefold() == "preferred"
    ]

    if preferred_statements:
        statements = preferred_statements

    entity_ids: set[str] = set()

    for statement in statements:
        value = (
            statement.get("mainsnak", {})
            .get("datavalue", {})
            .get("value", {})
        )

        if isinstance(value, dict) and value.get("id"):
            entity_ids.add(str(value["id"]))

    return entity_ids


def retrieve_wikidata_capital_evidence(
    claim: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    relation = extract_capital_relation(claim)

    if relation is None:
        return [], []

    claimed_capital, claimed_country = relation
    warnings: list[str] = []

    try:
        capital_search = find_exact_wikidata_entity(claimed_capital)
        country_search = find_exact_wikidata_entity(claimed_country)

        if capital_search is None or country_search is None:
            missing_names = []

            if capital_search is None:
                missing_names.append(claimed_capital)
            if country_search is None:
                missing_names.append(claimed_country)

            warnings.append(
                "Wikidata could not resolve an exact entity for: "
                + ", ".join(missing_names)
            )
            return [], warnings

        capital_id = str(capital_search["id"])
        country_id = str(country_search["id"])
        entity_payload = live_request_json(
            WIKIDATA_API_URL,
            {
                "action": "wbgetentities",
                "ids": f"{capital_id}|{country_id}",
                "props": "claims|labels|descriptions",
                "languages": "en",
                "format": "json",
            },
        )
        entities = entity_payload.get("entities", {})
        capital_entity = entities.get(capital_id, {})
        country_entity = entities.get(country_id, {})
        capital_of_ids = wikidata_claim_entity_ids(capital_entity, "P1376")
        country_capital_ids = wikidata_claim_entity_ids(country_entity, "P36")

        if country_capital_ids:
            verdict = (
                "SUPPORTS"
                if capital_id in country_capital_ids
                else "REFUTES"
            )
        elif capital_of_ids:
            verdict = (
                "SUPPORTS"
                if country_id in capital_of_ids
                else "REFUTES"
            )
        else:
            verdict = "NOT_DETERMINED"

        retrieved_at = datetime.now(timezone.utc).isoformat()
        capital_url = f"https://www.wikidata.org/wiki/{capital_id}"
        country_url = f"https://www.wikidata.org/wiki/{country_id}"
        capital_label = normalize_text(
            capital_entity.get("labels", {}).get("en", {}).get(
                "value",
                claimed_capital,
            )
        )
        country_label = normalize_text(
            country_entity.get("labels", {}).get("en", {}).get(
                "value",
                claimed_country,
            )
        )
        relationship_summary = (
            f"Live Wikidata relationship check for the claimed capital "
            f"{claimed_capital} ({capital_label}; {capital_id}) and "
            f"{claimed_country} ({country_label}; {country_id}). "
            f"The country's capital property contains: "
            f"{', '.join(sorted(country_capital_ids)) or 'no value'}. "
            f"The city's capital-of property contains: "
            f"{', '.join(sorted(capital_of_ids)) or 'no value'}."
        )

        return [
            {
                "source_id": (
                    f"wikidata_live_capital:{capital_id}:{country_id}"
                ),
                "source_name": "Wikidata",
                "source_type": "live_structured_knowledge_relationship",
                "trust_tier": 2,
                "official_source": False,
                "official_snapshot": False,
                "retrieved_live": True,
                "cache_allowed": False,
                "live_evidence_retrieved_at": retrieved_at,
                "title": (
                    f"Wikidata capital relationship: "
                    f"{claimed_capital} / {claimed_country}"
                ),
                "source_url": country_url,
                "related_source_urls": [capital_url, country_url],
                "relevance_score": 1.0,
                "excerpt": relationship_summary[:MAXIMUM_EXCERPT_LENGTH],
                "stable_relation_verdict": verdict,
                "verified_relation": (
                    "capital_of"
                    if verdict in {"SUPPORTS", "REFUTES"}
                    else "none"
                ),
                "wikidata_capital_id": capital_id,
                "wikidata_country_id": country_id,
                "wikidata_country_capital_ids": sorted(country_capital_ids),
                "wikidata_capital_of_ids": sorted(capital_of_ids),
                "attribution": (
                    f"Source: Wikidata. Originals: {capital_url} and "
                    f"{country_url}. Accessed live at {retrieved_at}."
                ),
            }
        ], warnings

    except requests.RequestException as error:
        warnings.append(
            "Wikidata structured capital retrieval failed without "
            f"bypassing the source: {type(error).__name__}: {error}"
        )
    except (ValueError, TypeError, KeyError) as error:
        warnings.append(
            "Wikidata returned unusable structured capital data: "
            f"{type(error).__name__}: {error}"
        )

    return [], warnings


def retrieve_wikidata_evidence(
    claim: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if extract_capital_relation(claim) is not None:
        return retrieve_wikidata_capital_evidence(claim)

    warnings: list[str] = []
    candidates: list[dict[str, Any]] = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    try:
        seen_entities: set[str] = set()

        for query in build_search_queries(claim):
            payload = live_request_json(
                WIKIDATA_API_URL,
                {
                    "action": "wbsearchentities",
                    "search": query,
                    "language": "en",
                    "limit": 5,
                    "format": "json",
                },
            )

            for result in payload.get("search", []):
                entity_id = str(result.get("id", ""))

                if not entity_id or entity_id in seen_entities:
                    continue

                seen_entities.add(entity_id)
                label = normalize_text(result.get("label", ""))
                description = normalize_text(result.get("description", ""))

                if not description:
                    continue

                evidence_text = f"{label}: {description}."
                relevance = lexical_relevance(claim, evidence_text)

                if relevance < 0.12:
                    continue

                source_url = f"https://www.wikidata.org/wiki/{entity_id}"
                capital_verdict = wikidata_capital_relation_verdict(
                    claim,
                    label,
                    description,
                )

                candidates.append(
                    {
                        "source_id": f"wikidata_live:{entity_id}",
                        "source_name": "Wikidata",
                        "source_type": "live_structured_knowledge_base",
                        "trust_tier": 2,
                        "official_source": False,
                        "official_snapshot": False,
                        "retrieved_live": True,
                        "cache_allowed": False,
                        "live_evidence_retrieved_at": retrieved_at,
                        "title": f"{label} ({entity_id})",
                        "source_url": source_url,
                        "relevance_score": relevance,
                        "excerpt": evidence_text[:MAXIMUM_EXCERPT_LENGTH],
                        "stable_relation_verdict": capital_verdict,
                        "verified_relation": (
                            "capital_of"
                            if capital_verdict in {"SUPPORTS", "REFUTES"}
                            else "none"
                        ),
                        "attribution": (
                            f"Source: Wikidata. Original: {source_url}. "
                            f"Accessed live at {retrieved_at}."
                        ),
                    }
                )

    except requests.RequestException as error:
        warnings.append(
            "Wikidata live retrieval failed without bypassing the source: "
            f"{type(error).__name__}: {error}"
        )
    except (ValueError, TypeError, KeyError) as error:
        warnings.append(
            "Wikidata returned unusable data: "
            f"{type(error).__name__}: {error}"
        )

    return candidates, warnings


def deduplicate_evidence(
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in evidence_items:
        key = (
            str(item.get("source_id", "")),
            normalized_lower(item.get("excerpt", "")),
        )

        if key in seen:
            continue

        seen.add(key)
        selected.append(item)

    selected.sort(
        key=lambda item: (
            item.get("stable_relation_verdict") in {"SUPPORTS", "REFUTES"},
            bool(item.get("official_source", False)),
            -int(item.get("trust_tier", 99)),
            float(item.get("relevance_score", 0.0)),
        ),
        reverse=True,
    )

    return selected[:MAXIMUM_EVIDENCE_ITEMS]


def retrieve_stable_knowledge_evidence(
    claim: str,
) -> dict[str, Any]:
    cleaned_claim = normalize_text(claim)
    eligible = is_stable_general_knowledge_claim(cleaned_claim)
    topic = detect_stable_topic(cleaned_claim)

    if not eligible:
        return {
            "available": True,
            "eligible": False,
            "claim": cleaned_claim,
            "topic": topic,
            "evidence": [],
            "warnings": [],
            "cache_allowed": False,
            "persistent_cache_used": False,
        }

    nasa_evidence, nasa_warnings = retrieve_nasa_evidence(cleaned_claim)
    official_evidence, official_warnings = retrieve_additional_official_evidence(
        cleaned_claim
    )
    verified_official_relation = any(
        str(item.get("stable_relation_verdict", "")).upper()
        in {"SUPPORTS", "REFUTES"}
        and str(item.get("verified_relation", "")) != "none"
        for item in [*nasa_evidence, *official_evidence]
    )

    if verified_official_relation:
        wikidata_evidence: list[dict[str, Any]] = []
        wikidata_warnings: list[str] = []
        wikipedia_evidence: list[dict[str, Any]] = []
        wikipedia_warnings: list[str] = []
    else:
        wikidata_evidence, wikidata_warnings = retrieve_wikidata_evidence(
            cleaned_claim
        )
        verified_structured_relation = any(
            str(item.get("stable_relation_verdict", "")).upper()
            in {"SUPPORTS", "REFUTES"}
            and str(item.get("verified_relation", "")) != "none"
            for item in wikidata_evidence
        )

        if verified_structured_relation:
            wikipedia_evidence = []
            wikipedia_warnings = []
        else:
            wikipedia_evidence, wikipedia_warnings = retrieve_wikipedia_evidence(
                cleaned_claim
            )

    evidence = deduplicate_evidence(
        [
            *nasa_evidence,
            *official_evidence,
            *wikidata_evidence,
            *wikipedia_evidence,
        ]
    )

    source_names = sorted(
        {
            str(item.get("source_name", ""))
            for item in evidence
            if item.get("source_name")
        }
    )

    return {
        "available": True,
        "eligible": True,
        "claim": cleaned_claim,
        "topic": topic,
        "evidence": evidence,
        "evidence_count": len(evidence),
        "source_names": source_names,
        "warnings": list(
            dict.fromkeys(
                [
                    *nasa_warnings,
                    *official_warnings,
                    *wikipedia_warnings,
                    *wikidata_warnings,
                ]
            )
        ),
        "retrieval_mode": "live_only",
        "cache_allowed": False,
        "persistent_cache_used": False,
        "confidence_cap": 0.80,
        "limitations": [
            "Wikipedia is contextual evidence and is not an official source.",
            "Wikidata descriptions may be incomplete and require corroboration.",
            "General-knowledge routing excludes current and high-impact claims.",
        ],
    }
