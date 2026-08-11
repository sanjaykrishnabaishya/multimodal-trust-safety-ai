from __future__ import annotations

import re
import unicodedata
from typing import Any


CYBER_CATEGORY = "Cyberbullying & Harassment"
ABUSIVE_CATEGORY = "Abusive Words"


ABUSIVE_TERMS = (
    "motherfucker",
    "motherfucking",
    "asshole",
    "bastard",
    "bitch",
    "fucker",
    "worthless",
    "pathetic",
    "disgusting",
    "useless",
    "idiot",
    "stupid",
    "loser",
    "ugly",
)

ABUSIVE_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in ABUSIVE_TERMS) + r")\b",
    re.IGNORECASE,
)

REPETITION_PATTERN = re.compile(
    r"\b(?:repeatedly|every\s+(?:day|night|week|morning|time)|again\s+and\s+again|"
    r"keeps?|continue[sd]?|continuing|several\s+(?:days|times)|multiple|dozens\s+of|"
    r"third\s+time|(?:three|four|five|six|seven|eight|nine|ten)\s+|"
    r"under\s+each|on\s+every|each\s+(?:day|night|week|morning)|whenever|all\s+night|"
    r"after\s+(?:being\s+)?(?:asked|told)\s+(?:him|her|them)?\s*to\s+stop|"
    r"despite\s+(?:her|his|their|my)?\s*(?:objection|refusal|request))\b"
)

HARASSMENT_BEHAVIOR_PATTERN = re.compile(
    r"\b(?:mock(?:s|ed|ing)?|ridicul(?:e|es|ed|ing)|humiliat(?:e|es|ed|ing|ion)|"
    r"embarrass(?:es|ed|ing)?|insult(?:s|ed|ing)?|degrad(?:e|es|ed|ing)|"
    r"cruel\s+memes?|insulting\s+(?:comments?|collages?|edits?|messages?)|"
    r"abusive\s+(?:messages?|comments?|voice\s+notes?)|"
    r"failure|nobody\s+likes?|everyone\s+would\s+be\s+happier\s+without)\b"
)

COORDINATION_PATTERN = re.compile(
    r"\b(?:everyone|all\s+of\s+you|followers?|members?|whole\s+group|friends?|"
    r"the\s+group|administrator|channel|the\s+post)\b"
    r"[^.!?]{0,100}\b(?:flood|target|mock|ridicule|humiliate|harass|abuse|insult|"
    r"report|tag|repost|send|comment|pile-on|publish|harass(?:ing)?|insulting)\b|"
    r"\b(?:let(?:'s|\s+us)|join\s+me|recruit|coordinate|bring\s+more\s+people|"
    r"plans?\s+shifts?|encourages?|instructs?|agrees?\s+to|we\s+should|go)\b"
    r"[^.!?]{0,100}\b(?:target|mock|ridicule|humiliate|harass|abuse|insult|"
    r"bully|shame|pile-on|send(?:ing)?|report|call|fill|pressure|publish|"
    r"harass(?:ing)?|humiliat(?:e|ing)|insulting)\b"
)

CONTACT_PATTERN = re.compile(
    r"\b(?:phone\s+number|mobile\s+number|personal\s+number|private\s+number|"
    r"(?:my|your|his|her|their)\s+number|private\s+(?:message|chat|video\s+call)|"
    r"direct\s+messages?|messages?|messaging|calling|contacts?|reply|respond|"
    r"replacement\s+(?:profiles?|accounts?)|meet\s+privately|"
    r"address|personal\s+contact\s+details?)\b"
)

REFUSAL_PATTERN = re.compile(
    r"\b(?:said\s+no|told\s+(?:him|her|them|you)\s+to\s+stop|asked\s+.*?to\s+stop|"
    r"leave\s+(?:me|her|him|them)\s+alone|blocked|declined|refus(?:e|ed|al)|"
    r"no\s+contact|despite\s+.*?(?:objection|refusal)|will\s+not\s+stop|"
    r"won't\s+stop|keep\s+(?:asking|messaging|bothering|contacting))\b"
)

THREAT_PATTERN = re.compile(
    r"\b(?:i|we)\b[^.!?]{0,55}\b(?:will|plan\s+to|intend\s+to|going\s+to|"
    r"coming\s+to|waiting\s+to)\b[^.!?]{0,55}\b(?:hurt|harm|attack|beat|stab|"
    r"shoot|burn|break|smash|injure|assault)\b|"
    r"\b(?:your|his|her)\s+(?:brother|sister|parents?|family)\b[^.!?]{0,55}"
    r"\b(?:will\s+be|going\s+to\s+be)\s+(?:hurt|harmed|attacked|beaten)\b|"
    r"\b(?:someone\s+should|go|let(?:'s|\s+us))\s+(?:physically\s+)?"
    r"(?:attack|beat|hurt|harm|stab|shoot|smash)\b|"
    r"\bdeserves?\s+to\s+(?:have\s+.*?)?(?:be\s+)?(?:beaten|hurt|harmed|"
    r"attacked|broken)\b|"
    r"\b(?:i|we)\b[^.!?]{0,55}\b(?:waiting|coming)\b[^.!?]{0,55}\b"
    r"(?:hurt|harm|attack|beat|stab|shoot|burn|break|smash|injure|assault)\b|"
    r"\b(?:i|we)\b[^.!?]{0,55}\b(?:knife|gun|weapon)\b[^.!?]{0,55}\b"
    r"(?:for\s+you|against\s+you|use\s+it\s+on\s+you)\b|"
    r"\byou\s+will\s+(?:be\s+)?(?:beaten|hurt|harmed|attacked|injured)\b|"
    r"\b(?:pay|comply|obey|delete|remove)\b[^.!?]{0,35}\bor\b[^.!?]{0,55}"
    r"\b(?:hurt|harm|attack|beat|stab|shoot|burn|injure|assault)\b|"
    r"\byou\b[^.!?]{0,55}\b(?:hospital|ambulance)\b[^.!?]{0,45}"
    r"\b(?:after|when|next)\b|"
    r"\byour\s+(?:parents?|family)\s+will\s+suffer\b"
)

REPORTING_CONTEXT_PATTERN = re.compile(
    r"\b(?:article|documentary|news\s+report|workshop|teacher\s+explained|"
    r"safety\s+guide|history\s+lesson|classroom\s+lesson|reported\s+the|"
    r"saved\s+the|as\s+evidence|moderator\s+removed|"
    r"prevent\s+cyberbullying|fictional\s+bully|teaches?\s+respectful|"
    r"never\s+(?:pressure|threaten|harass|humiliate))\b"
)

GOOD_FAITH_PATTERN = re.compile(
    r"\b(?:i\s+(?:disagree|oppose)|critique|criticism|negative\s+but\s+factual\s+review|"
    r"poorly\s+written|argument|proposal|policy\s+position|respect\s+.*?right\s+to\s+speak|"
    r"fine\s+to\s+say\s+no|no\s+problem\s+if\s+not|if\s+convenient)\b"
)

PERSON_TARGET_PATTERN = re.compile(
    r"\b(?:you|your|him|his|her|she|he|them|their|student|classmate|coworker|"
    r"employee|creator|journalist|teacher|boy|girl|woman|man|person|user|account)\b"
)


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = value.replace("’", "'")
    return re.sub(r"\s+", " ", value).strip()


def mask_abusive_terms(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        if len(value) <= 1:
            return "*"
        return value[0] + ("*" * (len(value) - 1))

    return ABUSIVE_PATTERN.sub(replace, str(text or ""))


def analyze_cyberbullying_boundary(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    abusive_matches = sorted({match.group(0).casefold() for match in ABUSIVE_PATTERN.finditer(text)})
    result: dict[str, Any] = {
        "available": True,
        "detected": False,
        "primary_category": "",
        "supporting_categories": [],
        "confidence": 0.0,
        "severity": "None",
        "action": "",
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "decision_type": "none",
        "abusive_terms_detected": bool(abusive_matches),
        "abusive_term_count": len(abusive_matches),
        "masked_text": mask_abusive_terms(text) if abusive_matches else text,
        "signals": [],
        "reason": "No supported cyberbullying or abusive-word boundary was detected.",
    }
    if not normalized:
        return result

    reporting = bool(REPORTING_CONTEXT_PATTERN.search(normalized))
    good_faith = bool(GOOD_FAITH_PATTERN.search(normalized))
    repeated = bool(REPETITION_PATTERN.search(normalized))
    harassment = bool(HARASSMENT_BEHAVIOR_PATTERN.search(normalized)) or bool(abusive_matches)
    coordinated = bool(COORDINATION_PATTERN.search(normalized))
    contact_pressure = bool(
        REPETITION_PATTERN.search(normalized)
        or REFUSAL_PATTERN.search(normalized)
        or re.search(r"\b(?:pressure|pressuring|demand|demands|demanding|keep\s+asking|"
                     r"keep\s+messaging|continue\s+(?:calling|messaging)|ignores?\s+.*?request)\b", normalized)
    )
    unwanted_contact = bool(CONTACT_PATTERN.search(normalized) and contact_pressure)
    targeted_threat = bool(THREAT_PATTERN.search(normalized))
    person_target = bool(PERSON_TARGET_PATTERN.search(normalized))

    signals: list[str] = []
    if repeated and harassment:
        signals.append("repeated_targeted_abuse")
    if coordinated:
        signals.append("coordinated_harassment")
    if unwanted_contact:
        signals.append("continued_unwanted_contact")
    if targeted_threat:
        signals.append("targeted_intimidation")
    result["signals"] = signals

    if reporting or good_faith:
        result["decision_type"] = "allowed_reporting_education_or_criticism"
        result["reason"] = "The wording appears in reporting, education, prevention, or good-faith criticism."
        return result

    if signals:
        confidence = 0.88 + min(0.07, 0.02 * (len(signals) - 1))
        supporting = [ABUSIVE_CATEGORY] if abusive_matches else []
        result.update(
            {
                "detected": True,
                "primary_category": CYBER_CATEGORY,
                "supporting_categories": supporting,
                "confidence": round(confidence, 2),
                "severity": "High" if targeted_threat else "Medium",
                "action": "Limit, flag, and send for human review",
                "human_review_required": True,
                "decision_type": "cyberbullying_or_harassment",
                "reason": (
                    "The content contains supported evidence of repeated targeted abuse, "
                    "continued unwanted contact, coordinated harassment, or targeted intimidation."
                ),
            }
        )
        return result

    if abusive_matches and person_target:
        result.update(
            {
                "detected": True,
                "primary_category": ABUSIVE_CATEGORY,
                "confidence": 0.90,
                "severity": "Medium",
                "action": "Mask abusive terms and limit distribution",
                "human_review_required": False,
                "decision_type": "targeted_abusive_words_without_harassment_pattern",
                "reason": (
                    "Abusive language targets a person, but there is not enough evidence "
                    "of repetition, coordinated harassment, unwanted contact, or intimidation."
                ),
            }
        )
    return result
