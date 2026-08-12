from __future__ import annotations

from typing import Any

from app.services.religiously_offensive_v7_rc6_service import (
    analyze_religiously_offensive_v7_rc6,
)


NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
ABUSIVE_CATEGORY = "Abusive Words"
RELIGIOUS_CATEGORY = "Religiously Offensive Content"
REQUIRED_ACTION = "Remove and send for human review"

ALLOWED_REFINEMENT_CATEGORIES = {
    NORMAL_CATEGORY,
    UNCERTAIN_CATEGORY,
    ABUSIVE_CATEGORY,
    RELIGIOUS_CATEGORY,
}


def analyze_religiously_offensive_v7_rc6_for_fusion(
    text: str,
    input_sources: list[str] | None = None,
) -> dict[str, Any]:
    return analyze_religiously_offensive_v7_rc6(text, input_sources)


def apply_religiously_offensive_v7_rc6_fusion(
    *,
    category: str,
    severity: str,
    action: str,
    confidence: float,
    human_review_required: bool,
    reason: str,
    matched_signals: list[str],
    analysis: dict[str, Any],
    safe_context_confirmed: bool = False,
) -> dict[str, Any]:
    result = {
        "category": category,
        "severity": severity,
        "action": action,
        "confidence": confidence,
        "human_review_required": human_review_required,
        "reason": reason,
        "matched_signals": list(matched_signals),
        "decision_applied": False,
        "automatic_enforcement_allowed": False,
        "fusion_status": "not_applied",
    }
    if not analysis.get("available", False):
        result["fusion_status"] = "unavailable"
        return result
    if safe_context_confirmed:
        result["fusion_status"] = "blocked_by_fusion_safe_context"
        return result
    if analysis.get("policy_veto_applied", False):
        result["fusion_status"] = str(
            analysis.get("policy_veto_reason", "blocked_by_policy_veto")
        )
        return result
    if analysis.get("decision") != "religiously_offensive_review_only":
        result["fusion_status"] = str(analysis.get("decision", "not_applied"))
        return result
    if category not in ALLOWED_REFINEMENT_CATEGORIES:
        result["fusion_status"] = "blocked_by_category_isolation"
        return result

    score = float(analysis.get("confidence", 0.0))
    decision_path = str(analysis.get("decision_path", "validated_evidence"))
    signal = f"religiously_offensive_v7_rc6:{decision_path}"
    result.update(
        {
            "category": RELIGIOUS_CATEGORY,
            "severity": "High",
            "action": REQUIRED_ACTION,
            "confidence": round(max(0.55, min(score, 0.90)), 2),
            "human_review_required": True,
            "reason": str(
                analysis.get(
                    "reason",
                    "A validated sacred-target attack requires human review.",
                )
            ),
            "matched_signals": list(dict.fromkeys(matched_signals + [signal])),
            "decision_applied": True,
            "automatic_enforcement_allowed": False,
            "fusion_status": "religiously_offensive_review_only_applied",
        }
    )
    return result
