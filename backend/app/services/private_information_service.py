from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from typing import Any

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider


PRIVATE_CATEGORY = "Publishing Private Information"
NORMAL_CATEGORY = "Normal/Ignore"


# ---------------------------------------------------------------------------
# India-specific and security-sensitive patterns
# ---------------------------------------------------------------------------

INDIAN_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+91[\s.-]?|0?)[6-9]\d{4}[\s.-]?\d{5}(?!\d)"
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}\b",
    re.IGNORECASE,
)

PAN_PATTERN = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    re.IGNORECASE,
)

AADHAAR_PATTERN = re.compile(
    r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)"
)

PAYMENT_CARD_PATTERN = re.compile(
    r"(?<!\d)(?:\d[\s-]?){13,19}(?!\d)"
)

IPV4_PATTERN = re.compile(
    r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"
)

COORDINATE_PATTERN = re.compile(
    r"""
    (?<![\d.-])
    [-+]?(?:[0-8]?\d(?:\.\d{3,})?|90(?:\.0+)?)
    \s*[,;]\s*
    [-+]?(?:
        (?:1[0-7]\d|\d?\d)(?:\.\d{3,})?
        |
        180(?:\.0+)?
    )
    (?![\d.-])
    """,
    re.VERBOSE,
)

CREDENTIAL_PATTERN = re.compile(
    r"""
    \b
    (?:
        password
        |
        passcode
        |
        otp
        |
        pin
        |
        cvv
        |
        security[\s_-]*code
        |
        recovery[\s_-]*code
        |
        api[\s_-]*key
        |
        secret[\s_-]*key
        |
        access[\s_-]*token
    )
    \s*
    (?:is|equals|=|:)
    \s*
    ["']?
    [A-Z0-9@#$%^&*_.!+\-/]{3,}
    ["']?
    """,
    re.IGNORECASE | re.VERBOSE,
)

BANK_ACCOUNT_PATTERN = re.compile(
    r"""
    \b
    (?:
        account
        |
        bank[\s_-]*account
        |
        a/c
        |
        acct
    )
    \s*
    (?:number|no|\#)?
    \s*
    (?:is|equals|=|:)?
    \s*
    \d{9,18}
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


CUSTOM_ACTIONABLE_PATTERNS = (
    ("email_address", EMAIL_PATTERN),
    ("indian_phone_number", INDIAN_PHONE_PATTERN),
    ("pan_like_identifier", PAN_PATTERN),
    ("aadhaar_like_identifier", AADHAAR_PATTERN),
    ("credential", CREDENTIAL_PATTERN),
    ("bank_account_number", BANK_ACCOUNT_PATTERN),
)


# Coordinates are context-only unless another actionable entity exists.
CUSTOM_CONTEXT_PATTERNS = (
    ("location_coordinates", COORDINATE_PATTERN),
)


# ---------------------------------------------------------------------------
# Presidio entity filtering
# ---------------------------------------------------------------------------

# These entities can represent contact details, financial information,
# credentials, government identifiers, or device/network identifiers.
ACTIONABLE_PRESIDIO_TYPES = {
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "IBAN_CODE",
    "CRYPTO",
    "MEDICAL_LICENSE",
    "US_SSN",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_ITIN",
    "US_PASSPORT",
    "UK_NHS",
    "AU_ABN",
    "AU_ACN",
    "AU_TFN",
    "AU_MEDICARE",
    "IN_AADHAAR",
    "IN_PAN",
    "IN_PASSPORT",
    "IN_VOTER",
    "IN_VEHICLE_REGISTRATION",
    "IN_GSTIN",
    "SG_NRIC_FIN",
    "SG_UEN",
    "SG_BANK_ACCOUNT",
    "SG_PASSPORT",
    "ES_NIF",
    "ES_NIE",
    "IT_FISCAL_CODE",
    "IT_DRIVER_LICENSE",
    "IT_VAT_CODE",
    "IT_PASSPORT",
    "IT_IDENTITY_CARD",
    "PL_PESEL",
    "FI_PERSONAL_IDENTITY_CODE",
    "KR_RRN",
    "KR_DRIVER_LICENSE",
}


# These entities frequently appear in ordinary news and are not private
# information violations by themselves.
CONTEXT_ONLY_PRESIDIO_TYPES = {
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "DATE_TIME",
    "NRP",
    "URL",
}


# ---------------------------------------------------------------------------
# Context phrases
# ---------------------------------------------------------------------------

SAFE_CONTEXT_PHRASES = (
    "example.com",
    "example.org",
    "example.net",
    "dummy",
    "fictional",
    "placeholder",
    "sample data",
    "test data",
    "redacted",
    "masked",
    "do not share",
    "don't share",
    "never share",
    "should not share",
    "must not share",
    "avoid sharing",
    "protect your",
    "privacy training",
    "security training",
    "for demonstration",
    "training example",
)


# These are deliberately stronger than generic words such as "publish"
# because ordinary news frequently uses "published" and "posted".
STRONG_EXPOSURE_PHRASES = (
    "leak their",
    "leak his",
    "leak her",
    "leaked their",
    "leaked his",
    "leaked her",
    "expose their",
    "expose his",
    "expose her",
    "dox them",
    "dox him",
    "dox her",
    "doxx them",
    "doxx him",
    "doxx her",
    "here is their private",
    "here is his private",
    "here is her private",
    "share their private",
    "share his private",
    "share her private",
    "their home address is",
    "his home address is",
    "her home address is",
    "contact them at",
    "login with this password",
    "use this password",
    "send money to this account",
)


# ---------------------------------------------------------------------------
# Presidio setup
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_presidio_analyzer() -> AnalyzerEngine:
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [
            {
                "lang_code": "en",
                "model_name": "en_core_web_lg",
            }
        ],
    }

    provider = NlpEngineProvider(
        nlp_configuration=configuration
    )

    return AnalyzerEngine(
        nlp_engine=provider.create_engine(),
        supported_languages=["en"],
    )


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _contains_phrase(
    normalized_text: str,
    phrases: tuple[str, ...],
) -> bool:
    return any(
        phrase in normalized_text
        for phrase in phrases
    )


def _digits_only(value: str) -> str:
    return "".join(
        character
        for character in value
        if character.isdigit()
    )


def _passes_luhn_check(value: str) -> bool:
    digits = _digits_only(value)

    if not 13 <= len(digits) <= 19:
        return False

    if len(set(digits)) == 1:
        return False

    checksum = 0
    parity = len(digits) % 2

    for index, character in enumerate(digits):
        digit = int(character)

        if index % 2 == parity:
            digit *= 2

            if digit > 9:
                digit -= 9

        checksum += digit

    return checksum % 10 == 0


def _valid_ipv4(value: str) -> bool:
    try:
        ipaddress.IPv4Address(value)
        return True
    except ipaddress.AddressValueError:
        return False


def _safe_placeholder(
    information_type: str,
) -> str:
    cleaned_type = re.sub(
        r"[^A-Za-z0-9_]+",
        "_",
        information_type,
    ).upper()

    return f"<{cleaned_type}_REDACTED>"


def _make_match(
    information_type: str,
    start: int,
    end: int,
    score: float,
    source: str,
) -> dict[str, Any]:
    return {
        "type": information_type,
        "start": start,
        "end": end,
        "score": round(float(score), 4),
        "source": source,
        "masked_value": _safe_placeholder(
            information_type
        ),
    }


def _matches_overlap(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:
    return (
        first["start"] < second["end"]
        and second["start"] < first["end"]
    )


def _deduplicate_matches(
    matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ordered = sorted(
        matches,
        key=lambda item: (
            item["start"],
            -(item["end"] - item["start"]),
            -item["score"],
        ),
    )

    accepted: list[dict[str, Any]] = []

    for candidate in ordered:
        duplicate = False

        for existing in list(accepted):
            if (
                candidate["type"] == existing["type"]
                and _matches_overlap(candidate, existing)
            ):
                duplicate = True

                if candidate["score"] > existing["score"]:
                    accepted.remove(existing)
                    accepted.append(candidate)

                break

        if not duplicate:
            accepted.append(candidate)

    return sorted(
        accepted,
        key=lambda item: (
            item["start"],
            item["end"],
        ),
    )


# ---------------------------------------------------------------------------
# Match collection
# ---------------------------------------------------------------------------

def _collect_presidio_matches(
    text: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    bool,
    str,
]:
    try:
        analyzer = _get_presidio_analyzer()

        results = analyzer.analyze(
            text=text,
            language="en",
            score_threshold=0.35,
        )

        actionable_matches: list[
            dict[str, Any]
        ] = []

        context_matches: list[
            dict[str, Any]
        ] = []

        for result in results:
            match = _make_match(
                information_type=result.entity_type,
                start=result.start,
                end=result.end,
                score=result.score,
                source="presidio",
            )

            if (
                result.entity_type
                in ACTIONABLE_PRESIDIO_TYPES
            ):
                actionable_matches.append(match)

            elif (
                result.entity_type
                in CONTEXT_ONLY_PRESIDIO_TYPES
            ):
                context_matches.append(match)

            # Unknown Presidio entities are ignored instead of
            # automatically being treated as violations.

        return (
            actionable_matches,
            context_matches,
            True,
            "",
        )

    except Exception as error:
        warning = (
            "Presidio was unavailable. Custom "
            "recognizers were used instead. "
            f"Reason: {type(error).__name__}"
        )

        return [], [], False, warning


def _collect_custom_matches(
    text: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    actionable_matches: list[
        dict[str, Any]
    ] = []

    context_matches: list[
        dict[str, Any]
    ] = []

    for (
        information_type,
        pattern,
    ) in CUSTOM_ACTIONABLE_PATTERNS:
        for match in pattern.finditer(text):
            actionable_matches.append(
                _make_match(
                    information_type=information_type,
                    start=match.start(),
                    end=match.end(),
                    score=0.88,
                    source="custom",
                )
            )

    for (
        information_type,
        pattern,
    ) in CUSTOM_CONTEXT_PATTERNS:
        for match in pattern.finditer(text):
            context_matches.append(
                _make_match(
                    information_type=information_type,
                    start=match.start(),
                    end=match.end(),
                    score=0.75,
                    source="custom",
                )
            )

    for match in PAYMENT_CARD_PATTERN.finditer(text):
        if _passes_luhn_check(match.group(0)):
            actionable_matches.append(
                _make_match(
                    information_type=(
                        "payment_card_number"
                    ),
                    start=match.start(),
                    end=match.end(),
                    score=0.97,
                    source="custom",
                )
            )

    for match in IPV4_PATTERN.finditer(text):
        if _valid_ipv4(match.group(0)):
            actionable_matches.append(
                _make_match(
                    information_type="ipv4_address",
                    start=match.start(),
                    end=match.end(),
                    score=0.95,
                    source="custom",
                )
            )

    return actionable_matches, context_matches


def _public_matches(
    matches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "type": match["type"],
            "confidence": match["score"],
            "source": match["source"],
            "masked_value": match["masked_value"],
        }
        for match in matches
    ]


def _context_type_counts(
    matches: list[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}

    for match in matches:
        information_type = str(
            match["type"]
        )

        counts[information_type] = (
            counts.get(information_type, 0)
            + 1
        )

    return counts


def _calculate_confidence(
    matches: list[dict[str, Any]],
    exposure_context_detected: bool,
) -> float:
    if not matches:
        return 0.91

    scores = [
        float(match["score"])
        for match in matches
    ]

    highest_score = max(scores)
    average_score = sum(scores) / len(scores)

    confidence = (
        highest_score * 0.65
        + average_score * 0.35
    )

    if len(matches) >= 2:
        confidence += 0.03

    if exposure_context_detected:
        confidence += 0.03

    return round(
        min(max(confidence, 0.50), 0.98),
        2,
    )


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

def analyze_private_information(
    text: str,
) -> dict[str, Any]:
    cleaned_text = _normalize_text(text)

    if not cleaned_text:
        return {
            "available": True,
            "presidio_available": True,
            "category": NORMAL_CATEGORY,
            "detected": False,
            "pii_detected": False,
            "policy_violation": False,
            "confidence": 0.50,
            "information_types": [],
            "match_count": 0,
            "masked_matches": [],
            "context_entities_detected": False,
            "context_entity_types": {},
            "safe_context_detected": False,
            "exposure_context_detected": False,
            "human_review_required": False,
            "action": "Allow",
            "reason": "No readable text was available.",
            "warnings": [],
            "raw_values_stored": False,
        }

    normalized_lower = cleaned_text.casefold()

    safe_context_detected = _contains_phrase(
        normalized_lower,
        SAFE_CONTEXT_PHRASES,
    )

    exposure_context_detected = _contains_phrase(
        normalized_lower,
        STRONG_EXPOSURE_PHRASES,
    )

    (
        presidio_actionable,
        presidio_context,
        presidio_available,
        warning,
    ) = _collect_presidio_matches(
        cleaned_text
    )

    (
        custom_actionable,
        custom_context,
    ) = _collect_custom_matches(
        cleaned_text
    )

    actionable_matches = _deduplicate_matches(
        presidio_actionable
        + custom_actionable
    )

    context_matches = _deduplicate_matches(
        presidio_context
        + custom_context
    )

    information_types = sorted(
        {
            match["type"]
            for match in actionable_matches
        }
    )

    pii_detected = bool(
        actionable_matches
    )

    context_entities_detected = bool(
        context_matches
    )

    confidence = _calculate_confidence(
        actionable_matches,
        exposure_context_detected,
    )

    warnings: list[str] = []

    if warning:
        warnings.append(warning)

    if not pii_detected:
        category = NORMAL_CATEGORY
        action = "Allow"
        human_review_required = False

        if context_entities_detected:
            reason = (
                "Only ordinary contextual entities such "
                "as people, organizations, locations, "
                "dates, nationalities, or URLs were "
                "detected. These do not constitute "
                "private information by themselves."
            )
        else:
            reason = (
                "No actionable private-information "
                "entity was detected."
            )

    elif safe_context_detected:
        category = NORMAL_CATEGORY
        action = "Allow"
        human_review_required = False

        reason = (
            "Actionable private-information-like content "
            "was detected in a masked, fictional, testing, "
            "educational, or preventative context."
        )

    else:
        category = PRIVATE_CATEGORY
        action = "Refer to human review"
        human_review_required = True

        if exposure_context_detected:
            reason = (
                "Actionable private information and "
                "possible exposure language were detected. "
                "Human review is required to determine "
                "consent and the policy outcome."
            )
        else:
            reason = (
                "Actionable private information was "
                "detected. Human review is required to "
                "determine ownership, consent, context, "
                "and whether a violation occurred."
            )

    return {
        "available": True,
        "presidio_available": presidio_available,
        "category": category,
        "detected": pii_detected,
        "pii_detected": pii_detected,

        # Human review must confirm the policy violation.
        "policy_violation": False,

        "confidence": confidence,
        "information_types": information_types,
        "match_count": len(
            actionable_matches
        ),
        "masked_matches": _public_matches(
            actionable_matches
        ),
        "context_entities_detected": (
            context_entities_detected
        ),
        "context_entity_types": (
            _context_type_counts(
                context_matches
            )
        ),
        "safe_context_detected": (
            safe_context_detected
        ),
        "exposure_context_detected": (
            exposure_context_detected
        ),
        "human_review_required": (
            human_review_required
        ),
        "action": action,
        "reason": reason,
        "warnings": warnings,
        "raw_values_stored": False,
    }
