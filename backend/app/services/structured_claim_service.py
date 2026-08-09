from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Pattern


CURRENT_TIME_MARKERS = {
    "now",
    "today",
    "tonight",
    "yesterday",
    "tomorrow",
    "currently",
    "right now",
    "latest",
    "breaking",
    "recently",
    "newly",
    "as of",
    "this week",
    "this month",
    "this year",
    "next week",
    "next month",
    "next year",
    "last week",
    "last month",
    "just announced",
}

HIGH_IMPACT_MARKERS = {
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
    "investment",
    "war",
    "terrorist",
    "crime",
    "arrested",
    "charged with",
}

OPINION_OR_SUBJECTIVE_MARKERS = {
    "i think",
    "i believe",
    "i feel",
    "in my opinion",
    "my favorite",
    "my favourite",
    "most beautiful",
    "beautiful",
    "best",
    "worst",
    "better than",
    "worse than",
    "should be",
    "ought to",
}

# These forms may contain a factual-looking clause, but the complete input is
# a report, prediction, instruction, personal statement, or uncertain claim.
# They belong to the general fact-check/policy path instead of the stable
# subject-relation-object path.
ROUTING_EXCLUSION_MARKERS = {
    "according to",
    "allegedly",
    "apparently",
    "could be",
    "i heard",
    "it is claimed",
    "it is rumored",
    "it is rumoured",
    "may be",
    "might be",
    "possibly",
    "probably",
    "report claims",
    "report says",
    "reports say",
    "rumor says",
    "rumour says",
    "someone said",
    "sources say",
    "unconfirmed",
}

REPORTING_PREFIX_PATTERN = re.compile(
    r"^\s*(?:(?:a|an|the|this)\s+)?(?:article|blog|broadcast|caption|"
    r"documentary|email|headline|message|news|post|report|rumou?r|"
    r"screenshot|social\s+media\s+post|text|video)\s+"
    r"(?:alleges?|announces?|claims?|mentions?|reports?|says?|states?|"
    r"suggests?)\b",
    flags=re.IGNORECASE,
)

COMMAND_OR_REQUEST_PATTERN = re.compile(
    r"^\s*(?:please\s+)?(?:allow|ban|block|buy|call|click|confirm|contact|"
    r"delete|download|forward|give|open|pay|remove|reply|report|send|share|"
    r"sign|transfer|upload|verify|visit)\b",
    flags=re.IGNORECASE,
)

FUTURE_OR_MODAL_PATTERN = re.compile(
    r"\b(?:will\s+(?:be|become)|would\s+be|shall\s+be|going\s+to|"
    r"expected\s+to|scheduled\s+to|plans?\s+to|predicted\s+to|"
    r"(?:may|might|could)\s+(?:belong|border|boil|circle|freeze|lie|"
    r"orbit|revolve|sit|serve))\b",
    flags=re.IGNORECASE,
)

TRANSIENT_SUBJECT_PATTERN = re.compile(
    r"^(?:i|you|he|she|we|they|someone|somebody|my\s+friend|our\s+team|"
    r"(?:the\s+)?meeting|(?:the\s+)?event|(?:the\s+)?appointment|"
    r"(?:the\s+)?delivery|(?:the\s+)?package|(?:this\s+)?message|"
    r"(?:this\s+)?post|(?:this\s+)?report)$",
    flags=re.IGNORECASE,
)

QUESTION_PREFIXES = (
    "who ",
    "what ",
    "when ",
    "where ",
    "why ",
    "how ",
    "is ",
    "are ",
    "was ",
    "were ",
    "did ",
    "does ",
    "do ",
    "can ",
    "could ",
    "will ",
    "would ",
)

NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no longer|neither|nor|didn't|doesn't|isn't|"
    r"aren't|wasn't|weren't|hasn't|haven't|cannot|can't)\b",
    flags=re.IGNORECASE,
)

YEAR_PATTERN = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2}|2100)\b")
NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*%)?"
)
DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?|"
    r"\d{1,2}\s+(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December)(?:\s+\d{4})?"
    r")\b",
    flags=re.IGNORECASE,
)
UNIT_PATTERN = re.compile(
    r"\b(?:degrees?\s+(?:celsius|fahrenheit)|°\s*[cf]|kelvin|km|"
    r"kilomet(?:er|re)s?|miles?|met(?:er|re)s?|centimet(?:er|re)s?|"
    r"millimet(?:er|re)s?|kg|kilograms?|grams?|tonnes?|tons?|"
    r"seconds?|minutes?|hours?|days?|years?|percent)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class RelationRule:
    relation: str
    topic: str
    wikidata_property: str | None
    pattern: Pattern[str]
    query_hint: str


@dataclass(frozen=True)
class StructuredClaim:
    original_claim: str
    normalized_claim: str
    language: str
    is_statement: bool
    is_question: bool
    is_negated: bool
    polarity: str
    subject: str
    relation: str
    object: str
    topic: str
    relation_confidence: float
    wikidata_property: str | None
    years: list[int]
    dates: list[str]
    numbers: list[str]
    units: list[str]
    has_current_time_marker: bool
    current_time_markers: list[str]
    high_impact: bool
    high_impact_markers: list[str]
    opinion_or_subjective: bool
    opinion_markers: list[str]
    suitable_for_stable_knowledge: bool
    search_queries: list[str]
    warnings: list[str]


def _compile(pattern: str) -> Pattern[str]:
    return re.compile(pattern, flags=re.IGNORECASE)


ENTITY = r"(?P<{name}>[A-Za-z0-9][A-Za-z0-9 .,'’()\-&/]*?)"
NEGATION = r"(?P<negation>not\s+)?"
ENDING = r"\s*[.!]?\s*$"


RELATION_RULES: tuple[RelationRule, ...] = (
    RelationRule(
        "capital_of",
        "geography",
        "P36",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:is|was|serves\s+as|served\s+as)\s+{NEGATION}"
            rf"(?:the\s+)?capital(?:\s+city)?\s+of\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "capital",
    ),
    RelationRule(
        "capital_of",
        "geography",
        "P36",
        _compile(
            rf"^\s*(?:the\s+)?capital(?:\s+city)?\s+of\s+"
            rf"{ENTITY.format(name='object')}\s+(?:is|was)\s+{NEGATION}"
            rf"{ENTITY.format(name='subject')}{ENDING}"
        ),
        "capital",
    ),
    RelationRule(
        "capital_of",
        "geography",
        "P36",
        _compile(
            rf"^\s*{ENTITY.format(name='object')}\s+"
            rf"(?:has|had)\s+{ENTITY.format(name='subject')}\s+as\s+"
            rf"{NEGATION}(?:its|the)\s+capital(?:\s+city)?{ENDING}"
        ),
        "capital",
    ),
    RelationRule(
        "located_in",
        "geography",
        "P131",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:(?:is|was)\s+{NEGATION}(?:located|situated|found)\s+|"
            rf"(?:is|was|lies|lie|sits|sit)\s+(?:not\s+)?)"
            rf"(?:in|within|inside)\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "location",
    ),
    RelationRule(
        "country_of",
        "geography",
        "P17",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:(?:is|was)\s+{NEGATION}(?:in|part\s+of)\s+|"
            rf"(?:does\s+(?:not\s+)?)?belong(?:s)?\s+to\s+)"
            rf"(?:the\s+country\s+of\s+)?{ENTITY.format(name='object')}{ENDING}"
        ),
        "country",
    ),
    RelationRule(
        "continent_of",
        "geography",
        "P30",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:is|was)\s+{NEGATION}(?:located\s+)?(?:in|on)\s+"
            rf"(?:the\s+continent\s+of\s+)?{ENTITY.format(name='object')}{ENDING}"
        ),
        "continent",
    ),
    RelationRule(
        "borders",
        "geography",
        "P47",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:does\s+{NEGATION})?(?:border|borders|shares\s+a\s+border\s+with)\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "border",
    ),
    RelationRule(
        "borders",
        "geography",
        "P47",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:is\s+{NEGATION})?(?:adjacent\s+to|neighbou?rs?)\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "border",
    ),
    RelationRule(
        "orbits",
        "astronomy",
        None,
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:does\s+{NEGATION})?(?:(?:orbit|orbits)\s+|"
            rf"(?:revolve|revolves|go|goes|circle|circles)\s+"
            rf"(?:around|round)\s+)"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "orbit",
    ),
    RelationRule(
        "freezes_at",
        "basic_science",
        None,
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:does\s+{NEGATION})?(?:freeze|freezes)\s+at\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "freezing point",
    ),
    RelationRule(
        "boils_at",
        "basic_science",
        None,
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:does\s+{NEGATION})?(?:boil|boils)\s+at\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "boiling point",
    ),
    RelationRule(
        "chemical_symbol",
        "basic_science",
        "P246",
        _compile(
            rf"^\s*(?:the\s+)?chemical\s+symbol\s+"
            rf"(?:for|of)\s+{ENTITY.format(name='subject')}\s+"
            rf"(?:is|was)\s+{NEGATION}{ENTITY.format(name='object')}{ENDING}"
        ),
        "chemical symbol",
    ),
    RelationRule(
        "chemical_symbol",
        "basic_science",
        "P246",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:has|uses)\s+{NEGATION}(?:the\s+)?chemical\s+symbol\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "chemical symbol",
    ),
    RelationRule(
        "atomic_number",
        "basic_science",
        "P1086",
        _compile(
            rf"^\s*(?:the\s+)?atomic\s+number\s+"
            rf"(?:for|of)\s+{ENTITY.format(name='subject')}\s+"
            rf"(?:is|was)\s+{NEGATION}{ENTITY.format(name='object')}{ENDING}"
        ),
        "atomic number",
    ),
    RelationRule(
        "atomic_number",
        "basic_science",
        "P1086",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"has\s+{NEGATION}(?:the\s+)?atomic\s+number\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "atomic number",
    ),
    RelationRule(
        "founded_by",
        "established_history",
        "P112",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:was|is)\s+{NEGATION}(?:founded|established|created)\s+by\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "founder",
    ),
    RelationRule(
        "founded_in",
        "established_history",
        "P571",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:was|is)\s+{NEGATION}(?:founded|established|created)\s+in\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "inception",
    ),
    RelationRule(
        "invented_by",
        "established_history",
        None,
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:was|is)\s+{NEGATION}(?:invented|developed|created)\s+by\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "inventor",
    ),
    RelationRule(
        "discovered_by",
        "established_history",
        "P61",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:was|is)\s+{NEGATION}discovered\s+by\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "discoverer",
    ),
    RelationRule(
        "born_in",
        "established_history",
        "P19",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:was|is)\s+{NEGATION}born\s+in\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "place of birth",
    ),
    RelationRule(
        "born_in",
        "established_history",
        "P19",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"had\s+{NEGATION}(?:a|the)?\s*birthplace\s+(?:in|of)\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "place of birth",
    ),
    RelationRule(
        "born_on",
        "established_history",
        "P569",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:was|is)\s+{NEGATION}born\s+on\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "date of birth",
    ),
    RelationRule(
        "ended_in",
        "established_history",
        None,
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:did\s+{NEGATION})?(?:end|ended|conclude|concluded)\s+in\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "end date",
    ),
    RelationRule(
        "ended_in",
        "established_history",
        None,
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:came|comes)\s+to\s+an\s+end\s+in\s+"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "end date",
    ),
    RelationRule(
        "instance_of",
        "basic_science",
        "P31",
        _compile(
            rf"^\s*{ENTITY.format(name='subject')}\s+"
            rf"(?:is|was)\s+{NEGATION}(?:an?\s+|the\s+)?"
            rf"{ENTITY.format(name='object')}{ENDING}"
        ),
        "type",
    ),
)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return " ".join(text.split())


def _normalized_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_text(value))
    without_marks = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).strip()


def _clean_entity(value: str) -> str:
    cleaned = normalize_text(value).strip(" \t\r\n,.;:!?\"'")
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        key = _normalized_key(value)
        if value and key and key not in seen:
            seen.add(key)
            output.append(value)

    return output


def _find_markers(text: str, markers: set[str]) -> list[str]:
    text_key = text.casefold()
    matches: list[str] = []
    for marker in markers:
        marker_pattern = re.escape(marker.casefold()).replace(r"\ ", r"\s+")
        if re.search(
            rf"(?<![a-z0-9]){marker_pattern}(?![a-z0-9])",
            text_key,
        ):
            matches.append(marker)
    return sorted(matches)


def _extract_relation(
    claim: str,
) -> tuple[str, str, str, str, str, str | None, float, bool]:
    for rule in RELATION_RULES:
        match = rule.pattern.fullmatch(claim)
        if match is None:
            continue

        groups = match.groupdict()
        subject = _clean_entity(groups.get("subject", ""))
        object_value = _clean_entity(groups.get("object", ""))
        matched_negation = bool(normalize_text(groups.get("negation", "")))

        if not subject or not object_value:
            continue

        confidence = 0.96
        if rule.relation == "instance_of":
            confidence = 0.82

        return (
            subject,
            rule.relation,
            object_value,
            rule.topic,
            rule.query_hint,
            rule.wikidata_property,
            confidence,
            matched_negation,
        )

    return "", "unknown", "", "general_knowledge", "", None, 0.0, False


def _build_search_queries(
    normalized_claim: str,
    subject: str,
    relation: str,
    object_value: str,
    query_hint: str,
) -> list[str]:
    candidates: list[str] = []

    if subject and object_value:
        candidates.extend(
            [
                f"{subject} {query_hint} {object_value}".strip(),
                f"{subject} {object_value}".strip(),
                f"{subject} {query_hint}".strip(),
                subject,
            ]
        )
    elif subject:
        candidates.extend([f"{subject} {query_hint}".strip(), subject])

    candidates.append(normalized_claim.strip(" .?!"))
    return _unique(candidates)[:5]


def parse_structured_claim(claim: str) -> dict[str, Any]:
    original_claim = str(claim or "")
    normalized_claim = normalize_text(original_claim)
    lower_claim = normalized_claim.casefold()
    warnings: list[str] = []

    if not normalized_claim:
        return asdict(
            StructuredClaim(
                original_claim=original_claim,
                normalized_claim="",
                language="en",
                is_statement=False,
                is_question=False,
                is_negated=False,
                polarity="unknown",
                subject="",
                relation="unknown",
                object="",
                topic="general_knowledge",
                relation_confidence=0.0,
                wikidata_property=None,
                years=[],
                dates=[],
                numbers=[],
                units=[],
                has_current_time_marker=False,
                current_time_markers=[],
                high_impact=False,
                high_impact_markers=[],
                opinion_or_subjective=False,
                opinion_markers=[],
                suitable_for_stable_knowledge=False,
                search_queries=[],
                warnings=["The claim is empty."],
            )
        )

    relation_data = _extract_relation(normalized_claim)
    (
        subject,
        relation,
        object_value,
        topic,
        query_hint,
        wikidata_property,
        relation_confidence,
        pattern_negation,
    ) = relation_data

    # A proper name can begin with an auxiliary-looking word (for example,
    # "Will Smith"). A successfully parsed declarative relation without a
    # question mark remains a statement.
    is_question = bool(
        normalized_claim.endswith("?")
        or (
            relation == "unknown"
            and lower_claim.startswith(QUESTION_PREFIXES)
        )
    )
    is_statement = not is_question

    is_negated = pattern_negation or bool(NEGATION_PATTERN.search(normalized_claim))
    current_markers = _find_markers(normalized_claim, CURRENT_TIME_MARKERS)
    routing_exclusion_markers = _find_markers(
        normalized_claim,
        ROUTING_EXCLUSION_MARKERS,
    )
    reporting_prefix_detected = bool(
        REPORTING_PREFIX_PATTERN.search(normalized_claim)
    )
    command_or_request_detected = bool(
        COMMAND_OR_REQUEST_PATTERN.search(normalized_claim)
    )
    future_or_modal_detected = bool(
        FUTURE_OR_MODAL_PATTERN.search(normalized_claim)
    )
    transient_subject_detected = bool(
        subject and TRANSIENT_SUBJECT_PATTERN.fullmatch(subject)
    )
    years = sorted({int(value) for value in YEAR_PATTERN.findall(normalized_claim)})
    high_impact_markers = _find_markers(normalized_claim, HIGH_IMPACT_MARKERS)
    clearly_historical = bool(
        any(
            year <= datetime.now(timezone.utc).year - 20
            for year in years
        )
        or "world war i" in lower_claim
        or "world war ii" in lower_claim
        or "first world war" in lower_claim
        or "second world war" in lower_claim
    )
    if clearly_historical:
        high_impact_markers = [
            marker for marker in high_impact_markers if marker != "war"
        ]
    opinion_markers = _find_markers(
        normalized_claim,
        OPINION_OR_SUBJECTIVE_MARKERS,
    )
    dates = _unique(DATE_PATTERN.findall(normalized_claim))
    numbers = _unique(NUMBER_PATTERN.findall(normalized_claim))
    units = _unique(UNIT_PATTERN.findall(normalized_claim))

    if relation == "unknown":
        warnings.append("No supported subject-relationship-object structure was found.")
    if is_question:
        warnings.append("Questions are not treated as factual assertions.")
    if current_markers:
        warnings.append("Current or time-sensitive wording requires fresh evidence routing.")
    if high_impact_markers:
        warnings.append("High-impact wording requires the stricter fact-check policy.")
    if opinion_markers:
        warnings.append(
            "Subjective or opinion wording is not treated as a stable factual assertion."
        )
    if routing_exclusion_markers or reporting_prefix_detected:
        warnings.append(
            "Reported, attributed, alleged, or uncertain wording must use "
            "the general fact-check path."
        )
    if command_or_request_detected:
        warnings.append(
            "Commands and requests are not stable factual assertions."
        )
    if future_or_modal_detected:
        warnings.append(
            "Predictions and future statements are not stable general knowledge."
        )
    if transient_subject_detected:
        warnings.append(
            "The parsed subject appears personal or transient rather than "
            "a stable knowledge entity."
        )

    suitable_for_stable_knowledge = bool(
        is_statement
        and relation != "unknown"
        and subject
        and object_value
        and not current_markers
        and not high_impact_markers
        and not opinion_markers
        and not routing_exclusion_markers
        and not reporting_prefix_detected
        and not command_or_request_detected
        and not future_or_modal_detected
        and not transient_subject_detected
    )

    search_queries = _build_search_queries(
        normalized_claim,
        subject,
        relation,
        object_value,
        query_hint,
    )

    result = StructuredClaim(
        original_claim=original_claim,
        normalized_claim=normalized_claim,
        language="en",
        is_statement=is_statement,
        is_question=is_question,
        is_negated=is_negated,
        polarity="negative" if is_negated else "positive",
        subject=subject,
        relation=relation,
        object=object_value,
        topic=topic,
        relation_confidence=relation_confidence,
        wikidata_property=wikidata_property,
        years=years,
        dates=dates,
        numbers=numbers,
        units=units,
        has_current_time_marker=bool(current_markers),
        current_time_markers=current_markers,
        high_impact=bool(high_impact_markers),
        high_impact_markers=high_impact_markers,
        opinion_or_subjective=bool(opinion_markers),
        opinion_markers=opinion_markers,
        suitable_for_stable_knowledge=suitable_for_stable_knowledge,
        search_queries=search_queries,
        warnings=warnings,
    )
    return asdict(result)


def get_structured_claim_service_status() -> dict[str, Any]:
    return {
        "available": True,
        "version": "2026.08-v3",
        "language": "en",
        "relation_count": len({rule.relation for rule in RELATION_RULES}),
        "rule_count": len(RELATION_RULES),
        "contains_fact_answers": False,
        "uses_holdout_records": False,
        "persistent_cache_used": False,
    }


__all__ = [
    "get_structured_claim_service_status",
    "parse_structured_claim",
]
