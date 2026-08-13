from __future__ import annotations

import re

from app.services.terrorism_extremism_service import NORMAL_CATEGORY, UNCERTAIN_CATEGORY
from app.services.terrorism_extremism_v4_rc2_service import (
    analyze_terrorism_extremism_v4_rc2,
)
from app.services.wikidata_terrorism_candidate_service import (
    ORGANIZATION_CONTEXT_PATTERN,
    contains_exact_name,
    load_candidate_index,
    normalize_for_matching,
)


GENERIC_CLASS_NAME_KEYS = {
    "terrorist group",
    "terrorist organization",
    "terrorist organisation",
    "extremist group",
    "extremist organization",
    "extremist organisation",
}

ADDITIONAL_AMBIGUOUS_NAME_KEYS = {
    "army of god",
    "black star",
    "caliphate state",
    "crusaders",
    "kingdom of israel",
    "national vanguard",
    "secret group",
    "the base",
    "the black eagles",
    "the revolt",
}


def external_organization_context_passes(
    normalized_text: str,
    normalized_name: str,
) -> bool:
    """Require an organization word outside the ambiguous matched span."""
    match = re.search(
        rf"(?<!\w){re.escape(normalized_name)}(?!\w)",
        normalized_text,
        flags=re.UNICODE,
    )
    if not match:
        return False
    before = normalized_text[max(0, match.start() - 36):match.start()]
    after = normalized_text[match.end():match.end() + 36]
    return bool(
        ORGANIZATION_CONTEXT_PATTERN.search(before)
        or ORGANIZATION_CONTEXT_PATTERN.search(after)
    )


def find_candidate_matches_v4_rc2(
    text: str,
) -> tuple[list[dict[str, object]], int]:
    normalized_text = normalize_for_matching(text)
    accepted: list[dict[str, object]] = []
    blocked = 0
    accepted_qids: set[str] = set()
    for item in load_candidate_index():
        normalized_name = str(item["normalized_name"])
        if normalized_name in GENERIC_CLASS_NAME_KEYS:
            continue
        if not contains_exact_name(normalized_text, normalized_name):
            continue
        ambiguous_name = (
            bool(item["ambiguous_name"])
            or normalized_name in ADDITIONAL_AMBIGUOUS_NAME_KEYS
        )
        if ambiguous_name and not external_organization_context_passes(
            normalized_text, normalized_name
        ):
            blocked += 1
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
    return accepted, blocked


def output(
    *,
    category: str | None,
    status: str,
    confidence: float,
    action: str,
    review: bool,
    matches: list[dict[str, object]],
    blocked: int,
    behavior: dict[str, object],
) -> dict[str, object]:
    return {
        "available": bool(load_candidate_index()),
        "candidate": "terrorism-extremism-v4-rc2-community-guard",
        "category": category,
        "status": status,
        "confidence": round(confidence, 2),
        "action": action,
        "human_review_required": review,
        "candidate_match_count": len(matches),
        "candidate_matches": matches,
        "ambiguous_matches_blocked": blocked,
        "behavior_families": list(behavior.get("behavior_families", [])),
        "community_data_used": bool(matches),
        "community_candidates_are_confirmed_designations": False,
        "supporting_evidence_only": True,
        "automatic_category_allowed": False,
        "automatic_enforcement_allowed": False,
        "neutral_mention_is_violation": False,
        "connected_to_live_moderation": False,
    }


def analyze_wikidata_terrorism_candidate_v4_rc2(text: str) -> dict[str, object]:
    behavior = analyze_terrorism_extremism_v4_rc2(text)
    matches, blocked = find_candidate_matches_v4_rc2(text)
    # Community data must never replace or downgrade a stronger policy-owned
    # result derived without Wikidata.
    if behavior.get("category") not in {None, NORMAL_CATEGORY, UNCERTAIN_CATEGORY}:
        return output(
            category=None,
            status="blocked_by_stronger_policy_owner",
            confidence=0.0,
            action="No boundary override",
            review=False,
            matches=matches,
            blocked=blocked,
            behavior=behavior,
        )
    if not matches:
        return output(
            category=None,
            status=(
                "ambiguous_candidate_name_blocked"
                if blocked
                else "no_community_candidate_match"
            ),
            confidence=0.0,
            action="No boundary override",
            review=False,
            matches=[],
            blocked=blocked,
            behavior=behavior,
        )

    if behavior.get("safe_context_detected") or behavior.get("category") == NORMAL_CATEGORY or behavior.get("status") in {
        "safe_reporting_education_history_or_condemnation",
        "legitimate_recruitment_or_operational_context",
    }:
        return output(
            category=None,
            status="candidate_mention_blocked_by_safe_context",
            confidence=0.0,
            action="No boundary override",
            review=False,
            matches=matches,
            blocked=blocked,
            behavior=behavior,
        )

    families = list(behavior.get("behavior_families", []))
    if not families:
        return output(
            category=None,
            status="neutral_candidate_mention_no_override",
            confidence=0.0,
            action="No boundary override",
            review=False,
            matches=matches,
            blocked=blocked,
            behavior=behavior,
        )

    return output(
        category=UNCERTAIN_CATEGORY,
        status="community_candidate_behavior_requires_review",
        confidence=min(0.64, 0.58 + 0.02 * (len(families) - 1)),
        action="Refer to human review",
        review=True,
        matches=matches,
        blocked=blocked,
        behavior=behavior,
    )


def get_wikidata_terrorism_candidate_v4_rc2_status() -> dict[str, object]:
    return {
        "available": bool(load_candidate_index()),
        "candidate": "terrorism-extremism-v4-rc2-community-guard",
        "ambiguous_name_requires_external_organization_context": True,
        "community_candidates_are_confirmed_designations": False,
        "permitted_community_output": "Uncertain only",
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
