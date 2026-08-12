from __future__ import annotations

import re
import unicodedata
from typing import Any


RELIGIOUS_CATEGORY = "Religiously Offensive Content"
HATE_CATEGORY = "Hate Speech & Discrimination"

SAFE_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"religious\s+history|religious\s+studies|interfaith\s+education|"
    r"good-faith\s+criticism|good\s+faith\s+criticism|"
    r"condemn(?:s|ed|ing)?\s+(?:religious\s+hatred|insults?|attacks?|"
    r"desecration|vandalism)|"
    r"article\s+(?:reports?|reported)|news\s+report|documentary\s+reports?|"
    r"historian\s+discusses?|researchers?\s+stud(?:y|ies)|"
    r"teacher\s+explains?|lesson\s+explains?|museum\s+restored|"
    r"safety\s+campaign|public-service\s+announcement|"
    r"public\s+service\s+announcement|interfaith\s+group\s+repairs?|"
    r"respectfully\s+questions?|respectful\s+criticism|"
    r"disagrees?\s+with\s+(?:a\s+)?doctrine|"
    r"without\s+insulting\s+believers|historical\s+context|"
    r"cultural\s+meaning|as\s+evidence\s+of\s+abuse|"
    r"asks?\s+people\s+not\s+to|opposes?\s+desecration|"
    r"do\s+not\s+(?:destroy|damage|burn|desecrate|mock|insult|abuse)|"
    r"never\s+(?:destroy|damage|burn|desecrate|mock|insult|abuse)"
    r")\b",
    re.IGNORECASE,
)

FOLLOWER_OR_GROUP_PATTERN = re.compile(
    r"\b(?:"
    r"people|persons?|followers?|members?|worshippers?|believers?|workers?|"
    r"community|communities|group|groups|religious\s+group|"
    r"religious\s+community|protected\s+group|employees?|students?|families"
    r")\b",
    re.IGNORECASE,
)

PROTECTED_RELIGION_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"religion|religious|faith|worshippers?|believers?|followers?|"
    r"religious\s+identity|religious\s+community|religious\s+group"
    r")\b",
    re.IGNORECASE,
)

FOLLOWER_ATTACK_PATTERN = re.compile(
    r"\b(?:"
    r"inferior|criminals?|parasites?|not\s+human|less\s+than\s+human|"
    r"should\s+not\s+exist|should\s+be\s+(?:excluded|expelled|forced\s+to\s+leave)|"
    r"exclude|expel|remove|boycott|attack|harm|destroy|discriminat(?:e|ion)|"
    r"deny\s+(?:jobs?|homes?|housing|education)|do\s+not\s+rent|"
    r"block\s+.*?from|terminate\s+workers?|inherently\s+dangerous"
    r")\b",
    re.IGNORECASE,
)

SACRED_OBJECT_PATTERN = re.compile(
    r"\b(?:"
    r"religious\s+symbols?|sacred\s+(?:symbols?|emblems?|objects?|images?|"
    r"statues?|texts?|books?|scriptures?|flags?|monuments?|carvings?|fixtures?)|"
    r"holy\s+(?:texts?|books?|scriptures?|objects?|symbols?|sites?)|"
    r"religious\s+(?:books?|scriptures?|emblems?|flags?|statues?|objects?)|"
    r"prayer\s+beads?|ceremonial\s+symbols?|religious\s+monument"
    r")\b",
    re.IGNORECASE,
)

SACRED_FIGURE_PATTERN = re.compile(
    r"\b(?:"
    r"god|gods|deity|deities|prophet|prophets|religious\s+figure|"
    r"religious\s+figurehead|spiritual\s+leader|religious\s+leader|"
    r"revered\s+religious\s+teacher|sacred\s+figurehead|"
    r"sacred\s+religious\s+leader|reincarnation"
    r")\b",
    re.IGNORECASE,
)

RELIGIOUS_PLACE_PATTERN = re.compile(
    r"\b(?:"
    r"temple|church|mosque|gurudwara|gurdwara|shrine|prayer\s+hall|"
    r"place\s+of\s+worship|worship\s+building|religious\s+building|"
    r"sanctuary|altar|monastery|chapel|sacred\s+site|prayer\s+space"
    r")\b",
    re.IGNORECASE,
)

DESECRATION_ACTION_PATTERN = re.compile(
    r"\b(?:"
    r"destroy|damage|burn|set\s+fire\s+to|desecrate|tear\s+apart|rip|"
    r"smash|deface|break|crush|cut\s+up|spit\s+on|vandalize|vandalise|"
    r"mutilate|dismantle|demolish|tear\s+down|throw\s+.*?into\s+the\s+fire|"
    r"paint\s+(?:abusive|degrading|obscene)\s+(?:words?|messages?)\s+(?:on|across)"
    r")\b",
    re.IGNORECASE,
)

DENIGRATION_ACTION_PATTERN = re.compile(
    r"\b(?:"
    r"mock|mocks|mocked|mocking|insult|insults|insulted|insulting|"
    r"abuse|abuses|abused|abusing|ridicule|ridicules|ridiculed|ridiculing|"
    r"demean|demeans|demeaned|demeaning|degrade|degrades|degraded|degrading|"
    r"humiliate|humiliates|humiliated|humiliating|"
    r"disgusting|filthy|repulsive|worthless|obscene\s+insults?|"
    r"abusive\s+(?:caricature|depiction|image)|degrading\s+(?:edit|image)|"
    r"morphed\s+image|morph\s+.*?image"
    r")\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"\s+", " ", value).strip()


def analyze_religiously_offensive_v2(text: str) -> dict[str, Any]:
    value = normalize_text(text)
    result: dict[str, Any] = {
        "available": True,
        "candidate": "religiously-offensive-v2-development",
        "detected": False,
        "decision": "no_religious_boundary_override",
        "primary_category": "",
        "boundary_category": "",
        "confidence": 0.0,
        "severity": "None",
        "action": "",
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "signals": [],
        "reason": "No supported Religiously Offensive Content boundary was detected.",
    }
    if not value:
        result["reason"] = "Empty text was not analyzed."
        return result

    safe_context = bool(SAFE_CONTEXT_PATTERN.search(value))
    group_reference = bool(FOLLOWER_OR_GROUP_PATTERN.search(value))
    religion_context = bool(PROTECTED_RELIGION_CONTEXT_PATTERN.search(value))
    follower_attack = bool(FOLLOWER_ATTACK_PATTERN.search(value))
    object_reference = bool(SACRED_OBJECT_PATTERN.search(value))
    figure_reference = bool(SACRED_FIGURE_PATTERN.search(value))
    place_reference = bool(RELIGIOUS_PLACE_PATTERN.search(value))
    desecration_action = bool(DESECRATION_ACTION_PATTERN.search(value))
    denigration_action = bool(DENIGRATION_ACTION_PATTERN.search(value))

    if safe_context:
        result.update(
            {
                "decision": "safe_reporting_education_or_criticism",
                "signals": ["safe_context"],
                "reason": (
                    "The wording appears in reporting, education, condemnation, "
                    "restoration, prevention, or good-faith criticism."
                ),
            }
        )
        return result

    # People targeted because of religion belong to Hate Speech, not this category.
    if group_reference and religion_context and follower_attack:
        result.update(
            {
                "decision": "protected_followers_hate_boundary",
                "boundary_category": HATE_CATEGORY,
                "confidence": 0.90,
                "human_review_required": True,
                "signals": ["protected_religious_followers_targeted"],
                "reason": (
                    "The attack targets people because of religion. The primary "
                    "policy boundary is Hate Speech & Discrimination."
                ),
            }
        )
        return result

    signals: list[str] = []
    if object_reference and desecration_action:
        signals.append("sacred_object_or_scripture_desecration")
    if place_reference and desecration_action:
        signals.append("religious_place_desecration")
    if figure_reference and denigration_action:
        signals.append("deity_prophet_or_religious_figure_denigration")

    if signals:
        confidence = min(0.95, 0.88 + 0.03 * (len(signals) - 1))
        result.update(
            {
                "detected": True,
                "decision": "religiously_offensive_review_only",
                "primary_category": RELIGIOUS_CATEGORY,
                "confidence": round(confidence, 2),
                "severity": "High",
                "action": "Remove and send for human review",
                "human_review_required": True,
                "signals": signals,
                "reason": (
                    "The content attacks, desecrates, damages, or deliberately "
                    "denigrates a sacred object, religious figure, or place of worship."
                ),
            }
        )
    return result
