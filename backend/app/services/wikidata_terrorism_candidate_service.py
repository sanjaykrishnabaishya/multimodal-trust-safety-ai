from __future__ import annotations

import csv
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.services.terrorism_extremism_service import (
    NORMAL_CATEGORY,
    UNCERTAIN_CATEGORY,
    analyze_terrorism_extremism,
)


ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_PATH = (
    ROOT
    / "datasets"
    / "public"
    / "wikidata_terrorism_candidates_v1"
    / "candidates.csv"
)

ORGANIZATION_CONTEXT_PATTERN = re.compile(
    r"\b(?:cell|faction|group|movement|network|organisation|organization|"
    r"outfit|party|brigade|front)\b",
    flags=re.IGNORECASE,
)

# These ordinary English words can form legitimate phrases unrelated to the
# Wikidata entity. Such names need an explicit organization word near the match.
COMMON_NAME_WORDS = {
    "army",
    "base",
    "black",
    "blood",
    "caliphate",
    "circle",
    "combat",
    "crusaders",
    "eagles",
    "force",
    "forces",
    "front",
    "god",
    "green",
    "group",
    "honour",
    "kingdom",
    "league",
    "liberation",
    "movement",
    "national",
    "of",
    "organization",
    "patriotic",
    "popular",
    "resistance",
    "revolt",
    "secret",
    "star",
    "state",
    "the",
    "union",
    "united",
    "vanguard",
    "white",
}


def normalize_for_matching(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = value.replace("’", "'").replace("‘", "'")
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def parse_bool(value: object) -> bool:
    return str(value or "").strip().casefold() == "true"


def is_ambiguous_name(value: str) -> bool:
    tokens = normalize_for_matching(value).split()
    return bool(tokens) and len(tokens) <= 4 and all(
        token in COMMON_NAME_WORDS for token in tokens
    )


def contains_exact_name(normalized_text: str, normalized_name: str) -> bool:
    return bool(
        re.search(
            rf"(?<!\w){re.escape(normalized_name)}(?!\w)",
            normalized_text,
            flags=re.UNICODE,
        )
    )


def ambiguity_guard_passes(
    normalized_text: str,
    normalized_name: str,
) -> bool:
    escaped_name = re.escape(normalized_name)
    organization_word = ORGANIZATION_CONTEXT_PATTERN.pattern
    return bool(
        re.search(
            rf"(?:{organization_word}).{{0,35}}(?<!\w){escaped_name}(?!\w)"
            rf"|(?<!\w){escaped_name}(?!\w).{{0,35}}(?:{organization_word})",
            normalized_text,
            flags=re.IGNORECASE | re.UNICODE,
        )
    )


@lru_cache(maxsize=1)
def load_candidate_index() -> tuple[dict[str, object], ...]:
    if not CANDIDATE_PATH.exists():
        return ()

    index: list[dict[str, object]] = []
    with CANDIDATE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("community_status") != "UNVERIFIED_COMMUNITY_CANDIDATE":
                continue
            if parse_bool(row.get("confirmed_legal_designation")):
                continue
            if parse_bool(row.get("automatic_enforcement_allowed")):
                continue

            names: list[tuple[str, str]] = []
            if parse_bool(row.get("primary_name_match_allowed")):
                primary = str(row.get("primary_name", "")).strip()
                if primary:
                    names.append((primary, "primary_name"))
            try:
                aliases = json.loads(row.get("matchable_aliases_json") or "[]")
            except json.JSONDecodeError:
                aliases = []
            if isinstance(aliases, list):
                names.extend(
                    (str(alias).strip(), "alias")
                    for alias in aliases
                    if str(alias).strip()
                )

            seen: set[str] = set()
            for name, name_type in names:
                normalized_name = normalize_for_matching(name)
                if not normalized_name or normalized_name in seen:
                    continue
                seen.add(normalized_name)
                index.append(
                    {
                        "qid": str(row.get("qid", "")),
                        "primary_name": str(row.get("primary_name", "")),
                        "matched_name": name,
                        "name_type": name_type,
                        "normalized_name": normalized_name,
                        "ambiguous_name": is_ambiguous_name(name),
                        "source_url": str(row.get("source_url", "")),
                    }
                )

    index.sort(key=lambda item: len(str(item["normalized_name"])), reverse=True)
    return tuple(index)


def find_candidate_matches(text: str) -> tuple[list[dict[str, object]], int]:
    normalized_text = normalize_for_matching(text)
    accepted: list[dict[str, object]] = []
    ambiguity_blocked = 0
    accepted_qids: set[str] = set()

    for item in load_candidate_index():
        normalized_name = str(item["normalized_name"])
        if not contains_exact_name(normalized_text, normalized_name):
            continue
        if bool(item["ambiguous_name"]) and not ambiguity_guard_passes(
            normalized_text,
            normalized_name,
        ):
            ambiguity_blocked += 1
            continue
        qid = str(item["qid"])
        if qid in accepted_qids:
            continue
        accepted_qids.add(qid)
        accepted.append(
            {
                "qid": qid,
                "primary_name": item["primary_name"],
                "matched_name": item["matched_name"],
                "name_type": item["name_type"],
                "source_url": item["source_url"],
                "community_status": "UNVERIFIED_COMMUNITY_CANDIDATE",
                "confirmed_legal_designation": False,
            }
        )
        if len(accepted) >= 5:
            break
    return accepted, ambiguity_blocked


def result(
    *,
    category: str | None,
    status: str,
    confidence: float,
    action: str,
    human_review_required: bool,
    matches: list[dict[str, object]],
    ambiguity_blocked: int,
    behavior: dict[str, object],
    reason: str,
) -> dict[str, object]:
    return {
        "available": bool(load_candidate_index()),
        "category": category,
        "status": status,
        "confidence": round(confidence, 2),
        "action": action,
        "human_review_required": human_review_required,
        "candidate_match_count": len(matches),
        "candidate_matches": matches,
        "ambiguous_matches_blocked": ambiguity_blocked,
        "behavior_families": list(behavior.get("behavior_families", [])),
        "community_data_used": bool(matches),
        "confirmed_legal_designation": False,
        "supporting_evidence_only": True,
        "automatic_category_allowed": False,
        "automatic_enforcement_allowed": False,
        "neutral_mention_is_violation": False,
        "connected_to_live_moderation": False,
        "reason": reason,
    }


def analyze_wikidata_terrorism_candidate(text: str) -> dict[str, object]:
    behavior = analyze_terrorism_extremism(text)
    matches, ambiguity_blocked = find_candidate_matches(text)

    if not matches:
        status = (
            "ambiguous_candidate_name_blocked"
            if ambiguity_blocked
            else "no_community_candidate_match"
        )
        return result(
            category=None,
            status=status,
            confidence=0.0,
            action="No boundary override",
            human_review_required=False,
            matches=[],
            ambiguity_blocked=ambiguity_blocked,
            behavior=behavior,
            reason=(
                "No sufficiently distinctive exact community-candidate name "
                "was found."
            ),
        )

    behavior_status = str(behavior.get("status", ""))
    if behavior.get("safe_context_detected") or behavior_status in {
        "safe_reporting_education_history_or_condemnation",
        "legitimate_recruitment_or_operational_context",
    } or behavior.get("category") == NORMAL_CATEGORY:
        return result(
            category=None,
            status="candidate_mention_blocked_by_safe_context",
            confidence=0.0,
            action="No boundary override",
            human_review_required=False,
            matches=matches,
            ambiguity_blocked=ambiguity_blocked,
            behavior=behavior,
            reason=(
                "An exact community-candidate name appears only in legitimate, "
                "reporting, educational, historical, or condemning context."
            ),
        )

    behavior_families = list(behavior.get("behavior_families", []))
    if not behavior_families:
        return result(
            category=None,
            status="neutral_candidate_mention_no_override",
            confidence=0.0,
            action="No boundary override",
            human_review_required=False,
            matches=matches,
            ambiguity_blocked=ambiguity_blocked,
            behavior=behavior,
            reason=(
                "A neutral community-candidate name mention is not a policy "
                "violation."
            ),
        )

    confidence = min(0.64, 0.58 + 0.02 * (len(behavior_families) - 1))
    return result(
        category=UNCERTAIN_CATEGORY,
        status="community_candidate_behavior_requires_review",
        confidence=confidence,
        action="Refer to human review",
        human_review_required=True,
        matches=matches,
        ambiguity_blocked=ambiguity_blocked,
        behavior=behavior,
        reason=(
            "A Wikidata community-candidate name and potentially relevant "
            "behavior appear together. Wikidata does not prove a current legal "
            "designation, so the result is Uncertain and review-only."
        ),
    )


def get_wikidata_terrorism_candidate_status() -> dict[str, object]:
    index = load_candidate_index()
    return {
        "available": bool(index),
        "candidate_path": str(CANDIDATE_PATH),
        "matchable_name_records": len(index),
        "community_data_only": True,
        "confirmed_legal_designations": 0,
        "automatic_category_allowed": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
