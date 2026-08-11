from __future__ import annotations

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


ABUSIVE_CATEGORY = "Abusive Words"
CYBER_CATEGORY = "Cyberbullying & Harassment"
HATE_CATEGORY = "Hate Speech & Discrimination"
SEXUAL_HARASSMENT_CATEGORY = "Sexual Harassment"

REPO_ROOT = Path(__file__).resolve().parents[3]
LEXICON_PATH = (
    REPO_ROOT
    / "datasets"
    / "development"
    / "hindi_abusive_rc3"
    / "lexicon.csv"
)

HINDI_CONTEXT_WORDS = {
    "aap",
    "ab",
    "aisa",
    "aisi",
    "aur",
    "bol",
    "bola",
    "bolta",
    "bolti",
    "hai",
    "hain",
    "har",
    "ho",
    "isko",
    "kar",
    "karta",
    "karti",
    "ke",
    "ki",
    "ko",
    "kya",
    "mat",
    "mein",
    "mera",
    "meri",
    "mujhe",
    "nahi",
    "ne",
    "par",
    "pe",
    "saale",
    "sale",
    "se",
    "tera",
    "tere",
    "teri",
    "tha",
    "thi",
    "tu",
    "tujhe",
    "tum",
    "tumhara",
    "tumhari",
    "usko",
    "wala",
    "wali",
    "ye",
    "yeh",
}

DIRECT_TARGET_PATTERN = re.compile(
    r"\b(?:aap|isko|mujhe|saale|sale|tera|tere|teri|tu|tujhe|tum|"
    r"tumhara|tumhari|usko|you|your|u|ye|yeh)\b",
    re.IGNORECASE,
)

REPORTING_OR_EDUCATION_PATTERN = re.compile(
    r"\b(?:abusive\s+(?:term|word|language)|article|dictionary|education|"
    r"example|guide|ka\s+matlab|means|moderation|moderator|news\s+report|"
    r"quoted?|report(?:ed|ing)?|research|slur\s+list|translation|"
    r"word\s+means|do\s+not\s+use|don't\s+use|mat\s+bolo|gali\s+mat)\b",
    re.IGNORECASE,
)

CYBER_REPETITION_PATTERN = re.compile(
    r"\b(?:again\s+and\s+again|daily|every\s+(?:day|night|time)|har\s+din|"
    r"har\s+raat|keeps?|lagatar|multiple\s+times|repeatedly|roz|"
    r"will\s+not\s+stop|won't\s+stop)\b",
    re.IGNORECASE,
)

CYBER_COORDINATION_PATTERN = re.compile(
    r"\b(?:all\s+of\s+you|everyone|followers|group|sab\s+log|"
    r"whole\s+group)\b[^.!?]{0,90}\b(?:abuse|comment|flood|harass|"
    r"insult|message|mock|target|troll)\b|"
    r"\b(?:join\s+me|let(?:'s|\s+us)|sab\s+milkar|we\s+should)\b"
    r"[^.!?]{0,90}\b(?:abuse|harass|insult|mock|target|troll)\b",
    re.IGNORECASE,
)

CYBER_UNWANTED_CONTACT_PATTERN = re.compile(
    r"\b(?:after\s+(?:i|she|he|they)\s+(?:blocked|said\s+no)|"
    r"block\s+karne\s+ke\s+baad|despite\s+being\s+blocked|"
    r"leave\s+me\s+alone|mana\s+karne\s+ke\s+baad|"
    r"told\s+(?:him|her|them|you)\s+to\s+stop)\b",
    re.IGNORECASE,
)

TARGETED_THREAT_PATTERN = re.compile(
    r"\b(?:i|we|main|hum)\b[^.!?]{0,60}\b(?:will|karunga|karenge|"
    r"going\s+to)\b[^.!?]{0,60}\b(?:attack|beat|harm|hurt|maar|"
    r"smash|stab)\b|"
    r"\b(?:you|tujhe|tumko)\b[^.!?]{0,50}\b(?:beat|harm|hurt|"
    r"maarunga|smash|stab)\b",
    re.IGNORECASE,
)

PROTECTED_GROUP_PATTERN = re.compile(
    r"\b(?:caste|dalit|ethnic|hindus?|jews?|muslims?|race|racial|"
    r"religion|religious|sikhs?|tribe|protected\s+group)\b",
    re.IGNORECASE,
)

SEXUAL_HARASSMENT_PATTERN = re.compile(
    r"\b(?:forced\s+sexual|send\s+(?:me\s+)?nudes?|sexual\s+message|"
    r"sexual\s+comments?|touch(?:ed|ing)?\s+(?:her|him|me)|"
    r"unwanted\s+sexual)\b",
    re.IGNORECASE,
)

SAFE_BC_PATTERN = re.compile(
    r"\b(?:before\s+christ|british\s+columbia|business\s+continuity)\b|"
    r"\b\d{1,4}\s*(?:bc|b\.c\.)\b|"
    r"\b(?:bc|b\.c\.)\s*(?:canada|era|period)\b",
    re.IGNORECASE,
)

SAFE_MC_PATTERN = re.compile(
    r"\b(?:master\s+of\s+ceremonies|minecraft|motorcycle\s+club)\b|"
    r"\bthe\s+(?:mc|m\.c\.)\s+(?:announced|hosted|introduced|spoke)\b",
    re.IGNORECASE,
)


def normalize_text(text: object) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = value.replace("’", "'")
    return re.sub(r"\s+", " ", value).strip()


def term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![\w]){re.escape(term)}(?![\w])",
        re.IGNORECASE,
    )


@lru_cache(maxsize=1)
def load_lexicon() -> tuple[dict[str, Any], ...]:
    if not LEXICON_PATH.is_file():
        return ()

    entries: list[dict[str, Any]] = []
    with LEXICON_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            transliteration = normalize_text(row.get("transliteration"))
            devanagari = normalize_text(row.get("devanagari"))
            patterns: list[tuple[str, re.Pattern[str]]] = []
            if transliteration:
                patterns.append(("romanized", term_pattern(transliteration)))
            if devanagari:
                patterns.append(("devanagari", term_pattern(devanagari)))
            if not patterns:
                continue
            entries.append(
                {
                    "entry_id": row.get("entry_id", ""),
                    "transliteration": transliteration,
                    "evidence_mode": row.get("evidence_mode", "context_required"),
                    "patterns": tuple(patterns),
                }
            )
    return tuple(entries)


def get_status() -> dict[str, Any]:
    entries = load_lexicon()
    return {
        "available": bool(entries),
        "lexicon_path": str(LEXICON_PATH),
        "entry_count": len(entries),
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "candidate": "hindi-abusive-context-rc3-development",
    }


def find_matches(text: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for entry in load_lexicon():
        for script, pattern in entry["patterns"]:
            for match in pattern.finditer(text):
                key = (entry["entry_id"], match.start(), match.end())
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    {
                        "entry_id": entry["entry_id"],
                        "transliteration": entry["transliteration"],
                        "evidence_mode": entry["evidence_mode"],
                        "script": script,
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
    matches.sort(key=lambda item: (item["start"], -(item["end"] - item["start"])))
    return matches


def mask_spans(text: str, matches: list[dict[str, Any]]) -> str:
    if not matches:
        return text
    accepted: list[tuple[int, int]] = []
    for item in sorted(matches, key=lambda value: (value["start"], -value["end"])):
        span = (int(item["start"]), int(item["end"]))
        if accepted and span[0] < accepted[-1][1]:
            continue
        accepted.append(span)
    output: list[str] = []
    cursor = 0
    for start, end in accepted:
        output.append(text[cursor:start])
        value = text[start:end]
        visible = value[0] if value else ""
        output.append(visible + ("*" * max(0, len(value) - 1)))
        cursor = end
    output.append(text[cursor:])
    return "".join(output)


def hinglish_score(normalized: str) -> int:
    tokens = set(re.findall(r"[a-z]+", normalized))
    score = len(tokens & HINDI_CONTEXT_WORDS)
    if re.search(r"[\u0900-\u097f]", normalized):
        score += 2
    return score


def result_template(text: str) -> dict[str, Any]:
    status = get_status()
    return {
        **status,
        "detected": False,
        "primary_category": "",
        "supporting_categories": [],
        "deferred_to_category": "",
        "confidence": 0.0,
        "severity": "None",
        "action": "",
        "human_review_required": False,
        "decision_type": "none",
        "matched_entry_count": 0,
        "context_required_match_count": 0,
        "matched_scripts": [],
        "masked_text": text,
        "signals": [],
        "reason": "No supported Hindi/Hinglish abusive-language evidence was detected.",
    }


def analyze_hindi_abusive_context(text: str) -> dict[str, Any]:
    original = str(text or "")
    normalized = normalize_text(original)
    result = result_template(original)
    if not normalized or not result["available"]:
        return result

    matches = find_matches(normalized)
    if not matches:
        return result

    result["matched_entry_count"] = len({item["entry_id"] for item in matches})
    result["context_required_match_count"] = len(
        {
            item["entry_id"]
            for item in matches
            if item["evidence_mode"] == "context_required"
        }
    )
    result["matched_scripts"] = sorted({item["script"] for item in matches})

    if REPORTING_OR_EDUCATION_PATTERN.search(normalized):
        result.update(
            {
                "decision_type": "reporting_education_or_counterspeech",
                "reason": "The matched term appears in reporting, education, translation, or counterspeech context.",
            }
        )
        return result

    if PROTECTED_GROUP_PATTERN.search(normalized):
        result.update(
            {
                "decision_type": "defer_to_hate_speech_boundary",
                "deferred_to_category": HATE_CATEGORY,
                "reason": "A protected-group signal is present, so this layer must not replace the hate-speech specialist.",
            }
        )
        return result

    if SEXUAL_HARASSMENT_PATTERN.search(normalized):
        result.update(
            {
                "decision_type": "defer_to_sexual_harassment_boundary",
                "deferred_to_category": SEXUAL_HARASSMENT_CATEGORY,
                "reason": "An unwanted sexual-conduct signal is present, so this layer must not replace the sexual-harassment specialist.",
            }
        )
        return result

    direct_target = bool(DIRECT_TARGET_PATTERN.search(normalized))
    hindi_score = hinglish_score(normalized)
    ambiguous_matches = [
        item for item in matches if item["evidence_mode"] == "context_required"
    ]
    lexical_matches = [
        item for item in matches if item["evidence_mode"] != "context_required"
    ]

    safe_abbreviation = bool(
        SAFE_BC_PATTERN.search(normalized) or SAFE_MC_PATTERN.search(normalized)
    )
    accepted_matches = list(lexical_matches)
    if ambiguous_matches and direct_target and hindi_score >= 1 and not safe_abbreviation:
        accepted_matches.extend(ambiguous_matches)

    if not accepted_matches:
        result.update(
            {
                "decision_type": "ambiguous_or_untargeted_term_without_context",
                "signals": ["ambiguous_lexical_match"],
                "reason": "A possible term was found, but supported Hindi/Hinglish and direct-target context was absent.",
            }
        )
        return result

    cyber_signals: list[str] = []
    if CYBER_REPETITION_PATTERN.search(normalized):
        cyber_signals.append("repeated_targeting")
    if CYBER_COORDINATION_PATTERN.search(normalized):
        cyber_signals.append("coordinated_harassment")
    if CYBER_UNWANTED_CONTACT_PATTERN.search(normalized):
        cyber_signals.append("continued_unwanted_contact")
    if TARGETED_THREAT_PATTERN.search(normalized):
        cyber_signals.append("targeted_intimidation")

    result["masked_text"] = mask_spans(original, accepted_matches)
    result["signals"] = cyber_signals or ["contextual_abusive_language"]

    if cyber_signals:
        result.update(
            {
                "detected": True,
                "primary_category": CYBER_CATEGORY,
                "supporting_categories": [ABUSIVE_CATEGORY],
                "confidence": 0.88,
                "severity": "High" if "targeted_intimidation" in cyber_signals else "Medium",
                "action": "Limit, flag, and refer to human review",
                "human_review_required": True,
                "decision_type": "cyberbullying_with_abusive_language",
                "reason": "Abusive-language evidence occurs with repetition, coordination, unwanted contact, or targeted intimidation.",
            }
        )
        return result

    contains_ambiguous = any(
        item["evidence_mode"] == "context_required" for item in accepted_matches
    )
    confidence = 0.78 if contains_ambiguous else (0.90 if direct_target else 0.82)
    result.update(
        {
            "detected": True,
            "primary_category": ABUSIVE_CATEGORY,
            "confidence": confidence,
            "severity": "Medium",
            "action": "Mask abusive terms and limit distribution",
            "human_review_required": contains_ambiguous,
            "decision_type": "contextual_abusive_words",
            "reason": "The term is supported by abusive-language context without a stronger cyberbullying, hate-speech, or sexual-harassment boundary.",
        }
    )
    return result

