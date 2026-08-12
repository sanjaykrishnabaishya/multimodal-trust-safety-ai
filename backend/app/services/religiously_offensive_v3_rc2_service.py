from __future__ import annotations

import re
import unicodedata
from typing import Any


RELIGIOUS_CATEGORY = "Religiously Offensive Content"
HATE_CATEGORY = "Hate Speech & Discrimination"
ACTION = "Remove and send for human review"


SAFE_MARKERS = (
    "article reports",
    "article reported",
    "news report",
    "documentary",
    "historian",
    "history lesson",
    "religious studies",
    "researcher",
    "museum exhibit",
    "museum restored",
    "teacher explains",
    "lesson explains",
    "educational discussion",
    "academic discussion",
    "historical context",
    "cultural context",
    "good faith criticism",
    "respectful criticism",
    "respectfully questions",
    "disagrees with the doctrine",
    "interfaith group",
    "interfaith campaign",
    "condemns",
    "condemned",
    "condemning",
    "opposes",
    "opposed",
    "warns against",
    "warning against",
    "asks people not to",
    "urged people not to",
    "prevent",
    "prevented",
    "prevention campaign",
    "restored",
    "repaired",
)

NEGATION_PATTERN = re.compile(
    r"\b(?:do\s+not|don't|never|must\s+not|should\s+not|shouldn't|"
    r"cannot|can't|stop|avoid|prevent)\b.{0,90}\b(?:"
    r"burn|damage|destroy|desecrate|deface|smash|break|tear|rip|"
    r"trample|vandalize|vandalise|mock|insult|ridicule|abuse|demolish"
    r")\b",
    re.IGNORECASE,
)

FOLLOWER_TERMS = (
    "religious followers",
    "followers of the faith",
    "followers of that faith",
    "followers of this faith",
    "people of that religion",
    "people of this religion",
    "people because of their religion",
    "religious believers",
    "worshippers",
    "faith community",
    "religious community",
    "religious group",
    "members of the religion",
    "members of that religion",
    "members of this religion",
    "families of that faith",
    "workers of that faith",
    "students of that faith",
)

FOLLOWER_ATTACK_STEMS = (
    "inferior",
    "parasite",
    "parasites",
    "not human",
    "less than human",
    "criminal",
    "inherently dangerous",
    "should not exist",
    "exclude",
    "expel",
    "force",
    "exclude",
    "expel",
    "boycott",
    "attack",
    "harm",
    "deny",
    "denied",
    "do not rent",
    "refuse",
    "refused",
    "remove",
    "removed",
    "ban",
    "keep them out",
    "kept out",
    "terminate",
)

SACRED_OBJECT_TERMS = (
    "holy book",
    "holy books",
    "holy text",
    "holy texts",
    "holy scripture",
    "holy scriptures",
    "sacred book",
    "sacred books",
    "sacred text",
    "sacred texts",
    "sacred scripture",
    "sacred scriptures",
    "religious book",
    "religious books",
    "religious scripture",
    "religious scriptures",
    "sacred object",
    "sacred objects",
    "religious object",
    "religious objects",
    "religious symbol",
    "religious symbols",
    "sacred symbol",
    "sacred symbols",
    "religious emblem",
    "religious emblems",
    "sacred emblem",
    "sacred emblems",
    "sacred image",
    "sacred images",
    "religious image",
    "religious images",
    "sacred statue",
    "sacred statues",
    "religious statue",
    "religious statues",
    "prayer beads",
    "ceremonial symbol",
    "ceremonial symbols",
    "sacred banner",
    "religious banner",
    "religious flag",
    "sacred flag",
    "religious monument",
    "sacred monument",
)

RELIGIOUS_PLACE_TERMS = (
    "temple",
    "church",
    "mosque",
    "gurudwara",
    "gurdwara",
    "shrine",
    "chapel",
    "monastery",
    "sanctuary",
    "altar",
    "prayer hall",
    "prayer space",
    "place of worship",
    "worship building",
    "religious building",
    "sacred site",
)

SACRED_FIGURE_TERMS = (
    "god",
    "gods",
    "deity",
    "deities",
    "prophet",
    "prophets",
    "religious figure",
    "religious figurehead",
    "sacred figure",
    "spiritual leader",
    "religious leader",
    "revered teacher",
    "revered religious teacher",
    "sacred leader",
)

PHYSICAL_ATTACK_STEMS = (
    "burn",
    "scorch",
    "torch",
    "destroy",
    "damage",
    "desecrat",
    "defac",
    "smash",
    "break",
    "crush",
    "tear",
    "rip",
    "shred",
    "cut up",
    "trample",
    "spit on",
    "soil",
    "drag through mud",
    "throw into fire",
    "throw in the fire",
    "vandal",
    "mutilat",
    "dismantl",
    "demolish",
    "tear down",
    "raze",
    "wreck",
    "spray obscene",
    "paint obscene",
    "cover with obscene",
    "cover in obscene",
)

DENIGRATION_STEMS = (
    "mock",
    "insult",
    "ridicul",
    "demean",
    "degrad",
    "humiliat",
    "vilif",
    "derid",
    "revile",
    "abuse",
    "obscene caricature",
    "abusive caricature",
    "degrading caricature",
    "obscene depiction",
    "abusive depiction",
    "degrading depiction",
    "morphed image",
    "filthy fraud",
    "disgusting fraud",
    "worthless fraud",
)


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = value.replace("’", "'")
    return re.sub(r"\s+", " ", value).strip()


def split_clauses(text: str) -> list[str]:
    clauses = re.split(
        r"(?:[.!?;\n]+|\bbut\b|\bhowever\b|\balthough\b|\bwhile\b)",
        text,
        flags=re.IGNORECASE,
    )
    return [clause.strip(" ,:-") for clause in clauses if clause.strip(" ,:-")]


def contains_term(text: str, terms: tuple[str, ...]) -> bool:
    padded = f" {text} "
    return any(f" {term} " in padded for term in terms)


def contains_stem(text: str, stems: tuple[str, ...]) -> bool:
    return any(stem in text for stem in stems)


def is_safe_clause(clause: str) -> bool:
    if contains_stem(clause, SAFE_MARKERS):
        return True
    return bool(NEGATION_PATTERN.search(clause))


def base_result() -> dict[str, Any]:
    return {
        "available": True,
        "candidate": "religiously-offensive-v3-rc2-development",
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


def analyze_religiously_offensive_v3_rc2(text: str) -> dict[str, Any]:
    value = normalize_text(text)
    result = base_result()
    if not value:
        result["reason"] = "Empty text was not analyzed."
        return result

    safe_clauses: list[str] = []
    boundary_signals: list[str] = []
    religious_signals: list[str] = []

    for clause in split_clauses(value):
        if is_safe_clause(clause):
            safe_clauses.append(clause)
            continue

        follower_reference = contains_term(clause, FOLLOWER_TERMS)
        follower_attack = contains_stem(clause, FOLLOWER_ATTACK_STEMS)
        if follower_reference and follower_attack:
            boundary_signals.append("protected_religious_followers_targeted")
            continue

        physical_attack = contains_stem(clause, PHYSICAL_ATTACK_STEMS)
        denigration = contains_stem(clause, DENIGRATION_STEMS)
        sacred_object = contains_term(clause, SACRED_OBJECT_TERMS)
        religious_place = contains_term(clause, RELIGIOUS_PLACE_TERMS)
        sacred_figure = contains_term(clause, SACRED_FIGURE_TERMS)

        if sacred_object and physical_attack:
            religious_signals.append("sacred_object_or_scripture_attack")
        if religious_place and physical_attack:
            religious_signals.append("place_of_worship_attack")
        if sacred_figure and (denigration or physical_attack):
            religious_signals.append("deity_prophet_or_religious_figure_attack")

    signals = list(dict.fromkeys(religious_signals))
    if signals:
        confidence = min(0.95, 0.89 + 0.02 * (len(signals) - 1))
        result.update(
            {
                "detected": True,
                "decision": "religiously_offensive_review_only",
                "primary_category": RELIGIOUS_CATEGORY,
                "confidence": round(confidence, 2),
                "severity": "High",
                "action": ACTION,
                "human_review_required": True,
                "signals": signals,
                "reason": (
                    "The content attacks, desecrates, damages, or deliberately "
                    "denigrates a sacred object, religious figure, or place of worship."
                ),
            }
        )
        return result

    if boundary_signals:
        result.update(
            {
                "decision": "protected_followers_hate_boundary",
                "boundary_category": HATE_CATEGORY,
                "confidence": 0.90,
                "human_review_required": True,
                "signals": list(dict.fromkeys(boundary_signals)),
                "reason": (
                    "The attack targets people because of religion. Category "
                    "ownership remains with Hate Speech & Discrimination."
                ),
            }
        )
        return result

    if safe_clauses:
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
