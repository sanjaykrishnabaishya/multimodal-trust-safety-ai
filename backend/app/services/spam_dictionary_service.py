import csv
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_DIRECTORY = (
    Path(__file__)
    .resolve()
    .parents[3]
)

DICTIONARY_PATH = (
    PROJECT_DIRECTORY
    / "datasets"
    / "spam_dictionary.csv"
)

EXCLUSION_PATH = (
    PROJECT_DIRECTORY
    / "datasets"
    / "spam_dictionary_exclusions.csv"
)

WHITESPACE_PATTERN = re.compile(
    r"\s+"
)

URL_PATTERN = re.compile(
    r"(?i)\b(?:https?://|www\.|wa\.me/|t\.me/)"
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?\d[\d\s\-]{7,}\d)(?!\d)"
)

REPEATED_CHARACTER_PATTERN = re.compile(
    r"(.)\1{5,}",
    flags=re.IGNORECASE,
)

REPEATED_WORD_PATTERN = re.compile(
    r"\b(\w+)(?:\s+\1){2,}\b",
    flags=re.IGNORECASE,
)

HIGH_RISK_PATTERNS = {
    "credential_request": (
        "send your otp",
        "share your otp",
        "enter your otp",
        "provide your otp",
        "send otp",
        "share otp",
        "send your password",
        "share your password",
        "login details",
        "banking credentials",
        "card details",
        "credit card number",
        "debit card number",
        "cvv",
        "account pin",
        "account password",
    ),

    "money_request": (
        "send money",
        "transfer money",
        "pay the fee",
        "processing fee",
        "registration fee",
        "gift card payment",
        "crypto payment",
        "cryptocurrency payment",
        "bitcoin payment",
        "donate now",
        "bank transfer",
        "payment required",
    ),

    "prize_or_return": (
        "claim your prize",
        "you have won",
        "lottery winner",
        "lottery winnings",
        "guaranteed return",
        "guaranteed profit",
        "double your money",
        "risk free investment",
        "100% return",
        "get rich quick",
        "make money fast",
        "earn money fast",
    ),
}

CONTEXT_DEPENDENT_PRIZE_PATTERNS = (
    "you are a winner",
    "you have been selected",
    "you have been chosen",
    "your prize",
    "winner",
    "winning",
)

PRIZE_COMPANION_PATTERNS = (
    "claim",
    "prize",
    "lottery",
    "reward",
    "cash",
    "money",
    "payment",
    "fee",
    "transfer",
    "otp",
    "password",
    "card",
    "click",
    "link",
    "whatsapp",
    "telegram",
    "contact",
    "urgent",
    "immediately",
)

URGENCY_PATTERNS = (
    "act now",
    "urgent",
    "immediately",
    "limited time",
    "expires today",
    "offer expires",
    "last chance",
    "right now",
    "today only",
    "do it now",
    "respond immediately",
    "before it is too late",
    "while supplies last",
)

PROMOTIONAL_PATTERNS = (
    "special offer",
    "exclusive offer",
    "limited offer",
    "free gift",
    "huge discount",
    "special discount",
    "buy now",
    "subscribe now",
    "click here",
    "visit our website",
    "promotional message",
    "earn from home",
    "work from home",
    "guaranteed income",
    "no investment required",
    "instant income",
)

CONTACT_PATTERNS = (
    "whatsapp",
    "telegram",
    "contact me",
    "call now",
    "message me",
    "dm me",
    "reply now",
    "click the link",
    "open the link",
    "join now",
    "join group",
)

SAFE_CONTEXT_PATTERNS = (
    "spam awareness",
    "spam prevention",
    "phishing awareness",
    "phishing prevention",
    "scam awareness",
    "scam prevention",
    "cybersecurity training",
    "security training",
    "example of a scam",
    "example of phishing",
    "do not share your otp",
    "never share your otp",
    "do not share your password",
    "never share your password",
    "report this scam",
    "reported as spam",
    "warning about a scam",
    "warning about phishing",
)

ORDINARY_PRAISE_PATTERNS = (
    "born to rule",
    "proud of you",
    "you did well",
    "you deserve it",
    "keep winning",
    "winner in life",
    "winner at heart",
    "you are amazing",
    "you are the best",
)

NEGATED_SCAM_PATTERNS = (
    "this is not a scam",
    "it is not a scam",
    "not a scam message",
    "not spam",
    "this is not spam",
    "it is not spam",
)

SCAMMER_REASSURANCE_COMPANIONS = (
    "click",
    "link",
    "send",
    "share",
    "pay",
    "payment",
    "fee",
    "otp",
    "password",
    "card",
    "bank",
    "transfer",
    "whatsapp",
    "telegram",
    "contact",
    "call",
    "urgent",
    "immediately",
)


def normalize_text(
    text: str,
) -> str:
    normalized = (
        unicodedata.normalize(
            "NFKC",
            text,
        )
    )

    normalized = (
        normalized.casefold()
    )

    normalized = (
        WHITESPACE_PATTERN.sub(
            " ",
            normalized,
        )
    )

    return normalized.strip()


def safe_float(
    value: str,
    default: float = 1.0,
) -> float:
    try:
        parsed_value = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return default

    if not math.isfinite(
        parsed_value
    ):
        return default

    return max(
        0.0,
        min(
            parsed_value,
            3.0,
        ),
    )


@lru_cache(maxsize=1)
def load_exclusions() -> set[
    tuple[str, str]
]:
    exclusions: set[
        tuple[str, str]
    ] = set()

    if not EXCLUSION_PATH.exists():
        return exclusions

    with EXCLUSION_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as exclusion_file:
        reader = csv.DictReader(
            exclusion_file
        )

        for row in reader:
            language = (
                row.get(
                    "language",
                    "",
                )
                .strip()
                .casefold()
            )

            phrase = normalize_text(
                row.get(
                    "normalized_phrase",
                    "",
                )
                or row.get(
                    "phrase",
                    "",
                )
            )

            if language and phrase:
                exclusions.add(
                    (
                        language,
                        phrase,
                    )
                )

    return exclusions


@lru_cache(maxsize=1)
def load_spam_dictionary() -> tuple[
    dict[str, Any],
    ...,
]:
    if not DICTIONARY_PATH.exists():
        return ()

    exclusions = load_exclusions()

    entries: list[
        dict[str, Any]
    ] = []

    seen: set[
        tuple[str, str]
    ] = set()

    with DICTIONARY_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as dictionary_file:
        reader = csv.DictReader(
            dictionary_file
        )

        for row in reader:
            language = (
                row.get(
                    "language",
                    "",
                )
                .strip()
                .casefold()
            )

            phrase = normalize_text(
                row.get(
                    "normalized_phrase",
                    "",
                )
                or row.get(
                    "phrase",
                    "",
                )
            )

            if not language or not phrase:
                continue

            if (
                language,
                phrase,
            ) in exclusions:
                continue

            if len(phrase) < 3:
                continue

            if (
                language,
                phrase,
            ) in seen:
                continue

            seen.add(
                (
                    language,
                    phrase,
                )
            )

            entries.append(
                {
                    "language": language,
                    "phrase": phrase,
                    "display_phrase": (
                        row.get(
                            "phrase",
                            phrase,
                        ).strip()
                    ),
                    "weight": safe_float(
                        row.get(
                            "weight",
                            "1.0",
                        )
                    ),
                }
            )

    entries.sort(
        key=lambda entry: (
            -len(
                entry["phrase"]
            ),
            entry["language"],
            entry["phrase"],
        )
    )

    return tuple(entries)


def phrase_is_present(
    normalized_text: str,
    phrase: str,
) -> bool:
    if not phrase:
        return False

    if phrase not in normalized_text:
        return False

    escaped_phrase = re.escape(
        phrase
    )

    left_boundary = (
        r"(?<!\w)"
        if phrase[0].isalnum()
        else ""
    )

    right_boundary = (
        r"(?!\w)"
        if phrase[-1].isalnum()
        else ""
    )

    return bool(
        re.search(
            left_boundary
            + escaped_phrase
            + right_boundary,
            normalized_text,
            flags=re.UNICODE,
        )
    )


def find_pattern_matches(
    normalized_text: str,
    patterns: tuple[str, ...],
) -> list[str]:
    return [
        pattern
        for pattern in patterns
        if phrase_is_present(
            normalized_text,
            pattern,
        )
    ]


def contains_any_pattern(
    normalized_text: str,
    patterns: tuple[str, ...],
) -> bool:
    return any(
        phrase_is_present(
            normalized_text,
            pattern,
        )
        for pattern in patterns
    )


def find_dictionary_matches(
    normalized_text: str,
    maximum_matches: int = 30,
) -> list[dict[str, Any]]:
    matches: list[
        dict[str, Any]
    ] = []

    matched_phrases: set[
        str
    ] = set()

    for entry in load_spam_dictionary():
        phrase = entry[
            "phrase"
        ]

        if phrase in matched_phrases:
            continue

        if phrase_is_present(
            normalized_text,
            phrase,
        ):
            matched_phrases.add(
                phrase
            )

            matches.append(
                {
                    "language": entry[
                        "language"
                    ],
                    "phrase": entry[
                        "display_phrase"
                    ],
                    "normalized_phrase": (
                        phrase
                    ),
                    "weight": entry[
                        "weight"
                    ],
                }
            )

        if (
            len(matches)
            >= maximum_matches
        ):
            break

    return matches


def find_high_risk_matches(
    normalized_text: str,
) -> dict[str, list[str]]:
    results: dict[
        str,
        list[str],
    ] = {}

    for group_name, patterns in (
        HIGH_RISK_PATTERNS.items()
    ):
        matches = (
            find_pattern_matches(
                normalized_text,
                patterns,
            )
        )

        if matches:
            results[
                group_name
            ] = matches

    contextual_prize_matches = (
        find_pattern_matches(
            normalized_text,
            CONTEXT_DEPENDENT_PRIZE_PATTERNS,
        )
    )

    has_prize_companion = (
        contains_any_pattern(
            normalized_text,
            PRIZE_COMPANION_PATTERNS,
        )
    )

    if (
        contextual_prize_matches
        and has_prize_companion
    ):
        existing_matches = (
            results.get(
                "prize_or_return",
                [],
            )
        )

        results[
            "prize_or_return"
        ] = list(
            dict.fromkeys(
                existing_matches
                + contextual_prize_matches
            )
        )

    return results


def calculate_gibberish_signal(
    normalized_text: str,
) -> bool:
    if REPEATED_CHARACTER_PATTERN.search(
        normalized_text
    ):
        return True

    if REPEATED_WORD_PATTERN.search(
        normalized_text
    ):
        return True

    tokens = normalized_text.split()

    if len(tokens) < 4:
        return False

    symbol_heavy_tokens = 0

    for token in tokens:
        if not token:
            continue

        symbol_count = sum(
            not character.isalnum()
            for character in token
        )

        if (
            symbol_count
            >= max(
                2,
                len(token) // 2,
            )
        ):
            symbol_heavy_tokens += 1

    return (
        symbol_heavy_tokens
        >= 2
    )


def detect_safe_context(
    normalized_text: str,
) -> tuple[
    bool,
    list[str],
]:
    safe_context_matches = (
        find_pattern_matches(
            normalized_text,
            SAFE_CONTEXT_PATTERNS,
        )
    )

    ordinary_praise_matches = (
        find_pattern_matches(
            normalized_text,
            ORDINARY_PRAISE_PATTERNS,
        )
    )

    negation_matches = (
        find_pattern_matches(
            normalized_text,
            NEGATED_SCAM_PATTERNS,
        )
    )

    negation_has_suspicious_companion = (
        contains_any_pattern(
            normalized_text,
            SCAMMER_REASSURANCE_COMPANIONS,
        )
    )

    safe_negation_matches = (
        []
        if negation_has_suspicious_companion
        else negation_matches
    )

    combined_matches = list(
        dict.fromkeys(
            safe_context_matches
            + ordinary_praise_matches
            + safe_negation_matches
        )
    )

    return (
        bool(
            combined_matches
        ),
        combined_matches,
    )


def analyze_spam_signals(
    text: str,
) -> dict[str, Any]:
    normalized_text = (
        normalize_text(
            text
        )
    )

    if not normalized_text:
        return {
            "is_likely_spam": False,
            "score": 0.0,
            "confidence": 0.0,
            "dictionary_matches": [],
            "matched_languages": [],
            "signal_groups": [],
            "matched_signals": [],
            "safe_context_detected": False,
            "safe_context_matches": [],
            "reason": (
                "No readable text was "
                "available for spam analysis."
            ),
        }

    dictionary_matches = (
        find_dictionary_matches(
            normalized_text
        )
    )

    high_risk_matches = (
        find_high_risk_matches(
            normalized_text
        )
    )

    urgency_matches = (
        find_pattern_matches(
            normalized_text,
            URGENCY_PATTERNS,
        )
    )

    promotional_matches = (
        find_pattern_matches(
            normalized_text,
            PROMOTIONAL_PATTERNS,
        )
    )

    contact_matches = (
        find_pattern_matches(
            normalized_text,
            CONTACT_PATTERNS,
        )
    )

    (
        safe_context_detected,
        safe_context_matches,
    ) = detect_safe_context(
        normalized_text
    )

    has_url = bool(
        URL_PATTERN.search(
            normalized_text
        )
    )

    has_phone_number = bool(
        PHONE_PATTERN.search(
            normalized_text
        )
    )

    has_gibberish = (
        calculate_gibberish_signal(
            normalized_text
        )
    )

    dictionary_score = min(
        3.0,
        sum(
            match["weight"]
            for match
            in dictionary_matches
        ),
    )

    high_risk_score = min(
        4.0,
        sum(
            1.75
            for matches
            in high_risk_matches.values()
            if matches
        ),
    )

    urgency_score = (
        1.0
        if urgency_matches
        else 0.0
    )

    promotion_score = (
        1.0
        if promotional_matches
        else 0.0
    )

    contact_score = (
        1.0
        if (
            contact_matches
            or has_url
            or has_phone_number
        )
        else 0.0
    )

    gibberish_score = (
        0.75
        if has_gibberish
        else 0.0
    )

    safe_context_reduction = (
        3.0
        if safe_context_detected
        else 0.0
    )

    total_score = max(
        0.0,
        dictionary_score
        + high_risk_score
        + urgency_score
        + promotion_score
        + contact_score
        + gibberish_score
        - safe_context_reduction,
    )

    supporting_groups = 0

    if urgency_matches:
        supporting_groups += 1

    if promotional_matches:
        supporting_groups += 1

    if (
        contact_matches
        or has_url
        or has_phone_number
    ):
        supporting_groups += 1

    if has_gibberish:
        supporting_groups += 1

    high_risk_group_count = len(
        high_risk_matches
    )

    dictionary_match_count = len(
        dictionary_matches
    )

    has_contextual_support = (
        supporting_groups >= 1
        or high_risk_group_count >= 2
    )

    is_likely_spam = (
        not safe_context_detected
        and (
            (
                high_risk_group_count >= 1
                and has_contextual_support
                and total_score >= 3.25
            )
            or (
                dictionary_match_count >= 2
                and supporting_groups >= 2
                and total_score >= 4.0
            )
            or (
                supporting_groups >= 3
                and total_score >= 4.0
            )
        )
    )

    confidence = min(
        0.97,
        max(
            0.35,
            0.40
            + (
                total_score
                * 0.075
            ),
        ),
    )

    signal_groups: list[str] = []

    if dictionary_matches:
        signal_groups.append(
            "multilingual_dictionary"
        )

    signal_groups.extend(
        high_risk_matches.keys()
    )

    if urgency_matches:
        signal_groups.append(
            "urgency"
        )

    if promotional_matches:
        signal_groups.append(
            "promotion"
        )

    if contact_matches:
        signal_groups.append(
            "contact_request"
        )

    if has_url:
        signal_groups.append(
            "external_link"
        )

    if has_phone_number:
        signal_groups.append(
            "phone_number"
        )

    if has_gibberish:
        signal_groups.append(
            "gibberish_or_repetition"
        )

    if safe_context_detected:
        signal_groups.append(
            "safe_context"
        )

    matched_signals: list[str] = []

    for group_matches in (
        high_risk_matches.values()
    ):
        matched_signals.extend(
            group_matches
        )

    matched_signals.extend(
        urgency_matches
    )

    matched_signals.extend(
        promotional_matches
    )

    matched_signals.extend(
        contact_matches
    )

    matched_signals.extend(
        safe_context_matches
    )

    for match in dictionary_matches[
        :10
    ]:
        matched_signals.append(
            "dictionary:"
            f"{match['language']}:"
            f"{match['phrase']}"
        )

    matched_languages = sorted(
        {
            match["language"]
            for match
            in dictionary_matches
        }
    )

    if is_likely_spam:
        reason = (
            "Multiple spam, scam, or "
            "phishing indicators were "
            "detected together with "
            "supporting transactional, "
            "promotional, urgency, contact, "
            "or payment context."
        )

    elif safe_context_detected:
        reason = (
            "Potential spam-related terms "
            "appear in safe, negated, "
            "educational, warning, or "
            "ordinary conversational context."
        )

    elif dictionary_matches:
        reason = (
            "Dictionary terms were detected, "
            "but supporting contextual evidence "
            "was not strong enough for an "
            "automated spam decision."
        )

    else:
        reason = (
            "No meaningful spam, scam, or "
            "phishing combination was detected."
        )

    return {
        "is_likely_spam": (
            is_likely_spam
        ),
        "score": round(
            total_score,
            2,
        ),
        "confidence": round(
            confidence,
            2,
        ),
        "dictionary_matches": (
            dictionary_matches
        ),
        "matched_languages": (
            matched_languages
        ),
        "signal_groups": list(
            dict.fromkeys(
                signal_groups
            )
        ),
        "matched_signals": list(
            dict.fromkeys(
                matched_signals
            )
        ),
        "safe_context_detected": (
            safe_context_detected
        ),
        "safe_context_matches": (
            safe_context_matches
        ),
        "reason": reason,
    }


def get_spam_dictionary_status() -> (
    dict[str, Any]
):
    entries = load_spam_dictionary()

    language_counts: dict[
        str,
        int,
    ] = {}

    for entry in entries:
        language = entry[
            "language"
        ]

        language_counts[
            language
        ] = (
            language_counts.get(
                language,
                0,
            )
            + 1
        )

    return {
        "available": bool(
            entries
        ),
        "dictionary_path": str(
            DICTIONARY_PATH
        ),
        "exclusion_path": str(
            EXCLUSION_PATH
        ),
        "entry_count": len(
            entries
        ),
        "language_counts": dict(
            sorted(
                language_counts.items()
            )
        ),
        "partial_coverage_languages": [
            "kannada",
            "tamil",
            "telugu",
        ],
    }