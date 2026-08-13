from __future__ import annotations

from app.services.terrorism_extremism_service import (
    NORMAL_CATEGORY,
    TERRORISM_CATEGORY,
    UNCERTAIN_CATEGORY,
)
from app.services.terrorism_extremism_v5_rc3_service import (
    analyze_terrorism_extremism_v5_rc3,
)
from app.services.wikidata_terrorism_candidate_service import load_candidate_index
from app.services.wikidata_terrorism_candidate_v4_rc2_service import (
    find_candidate_matches_v4_rc2,
)


def response(
    *,
    category: str | None,
    status: str,
    confidence: float,
    action: str,
    review: bool,
    matches: list[dict[str, object]],
    blocked: int,
    base: dict[str, object],
) -> dict[str, object]:
    return {
        "available": bool(load_candidate_index()),
        "candidate": "terrorism-extremism-v5-rc3-community-guard",
        "category": category,
        "status": status,
        "confidence": round(confidence, 2),
        "action": action,
        "human_review_required": review,
        "candidate_match_count": len(matches),
        "candidate_matches": matches,
        "ambiguous_matches_blocked": blocked,
        "behavior_families": list(base.get("behavior_families", [])),
        "community_data_used": bool(matches),
        "community_candidates_are_confirmed_designations": False,
        "supporting_evidence_only": True,
        "automatic_category_allowed": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }


def analyze_wikidata_terrorism_candidate_v5_rc3(text: str) -> dict[str, object]:
    base = analyze_terrorism_extremism_v5_rc3(text)
    matches, blocked = find_candidate_matches_v4_rc2(text)

    if base.get("category") == TERRORISM_CATEGORY:
        return response(
            category=None,
            status="blocked_by_stronger_policy_owner",
            confidence=0.0,
            action="No boundary override",
            review=False,
            matches=matches,
            blocked=blocked,
            base=base,
        )
    if not matches:
        return response(
            category=None,
            status=("ambiguous_candidate_name_blocked" if blocked else "no_community_candidate_match"),
            confidence=0.0,
            action="No boundary override",
            review=False,
            matches=[],
            blocked=blocked,
            base=base,
        )
    if base.get("category") == NORMAL_CATEGORY or base.get("safe_context_detected"):
        return response(
            category=None,
            status="candidate_mention_blocked_by_safe_context",
            confidence=0.0,
            action="No boundary override",
            review=False,
            matches=matches,
            blocked=blocked,
            base=base,
        )
    families = list(base.get("behavior_families", []))
    if not families:
        return response(
            category=None,
            status="neutral_candidate_mention_no_override",
            confidence=0.0,
            action="No boundary override",
            review=False,
            matches=matches,
            blocked=blocked,
            base=base,
        )
    return response(
        category=UNCERTAIN_CATEGORY,
        status="community_candidate_behavior_requires_review",
        confidence=min(0.64, 0.58 + 0.02 * (len(families) - 1)),
        action="Refer to human review",
        review=True,
        matches=matches,
        blocked=blocked,
        base=base,
    )


def get_wikidata_terrorism_candidate_v5_rc3_status() -> dict[str, object]:
    return {
        "available": bool(load_candidate_index()),
        "candidate": "terrorism-extremism-v5-rc3-community-guard",
        "safe_context_veto_priority": True,
        "community_candidates_are_confirmed_designations": False,
        "permitted_community_output": "Uncertain only",
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
