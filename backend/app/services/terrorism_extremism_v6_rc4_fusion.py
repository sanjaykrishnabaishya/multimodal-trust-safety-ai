from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.terrorism_extremism_service import (
    NORMAL_CATEGORY,
    TERRORISM_CATEGORY,
    UNCERTAIN_CATEGORY,
)
from app.services.terrorism_extremism_v6_rc4_service import (
    analyze_terrorism_extremism_v6_rc4,
)
from app.services.wikidata_terrorism_candidate_v6_rc4_service import (
    analyze_wikidata_terrorism_candidate_v6_rc4,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    BACKEND_ROOT
    / "storage"
    / "candidates"
    / "terrorism-extremism-v6-rc4"
)
PACKAGED_EVIDENCE_DIRECTORY = (
    BACKEND_ROOT
    / "app"
    / "evidence"
    / "terrorism-extremism-v6-rc4"
)


def first_existing_path(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[-1]


CANDIDATE_MANIFEST = first_existing_path(
    CANDIDATE_DIRECTORY / "manifest.json",
    PACKAGED_EVIDENCE_DIRECTORY / "manifest.json",
)
INDEPENDENT_VERDICT = first_existing_path(
    CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json",
    PACKAGED_EVIDENCE_DIRECTORY / "independent_evaluation_verdict.json",
)

TEXTUAL_INPUT_SOURCES = {
    "text",
    "extracted_text",
    "ocr_text",
    "audio_transcript",
}

ALLOWED_PRIMARY_BOUNDARIES = {
    NORMAL_CATEGORY,
    UNCERTAIN_CATEGORY,
}


@lru_cache(maxsize=1)
def get_terrorism_extremism_v6_rc4_readiness() -> dict[str, object]:
    try:
        manifest = json.loads(CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
        verdict = json.loads(INDEPENDENT_VERDICT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "ready": False,
            "reason": f"Candidate evidence unavailable: {type(error).__name__}",
            "automatic_enforcement_allowed": False,
        }

    checks = {
        "candidate_identity": manifest.get("candidate")
        == "terrorism-extremism-v6-rc4",
        "development_gate": manifest.get("development_gate_passed") is True,
        "independent_gate": verdict.get("passed") is True,
        "guarded_integration_eligible": verdict.get(
            "eligible_for_guarded_live_integration"
        )
        is True,
        "candidate_automatic_enforcement_disabled": manifest.get(
            "automatic_enforcement_allowed"
        )
        is False,
        "verdict_automatic_enforcement_disabled": verdict.get(
            "automatic_enforcement_allowed"
        )
        is False,
        "community_output_uncertain_only": manifest.get(
            "permitted_community_candidate_output"
        )
        == "Uncertain only",
        "confirmed_legal_designations_zero": manifest.get(
            "confirmed_legal_designations"
        )
        == 0,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "reason": (
            "Frozen RC4 passed its synthetic independent gate."
            if all(checks.values())
            else "Frozen RC4 readiness contract is incomplete."
        ),
        "synthetic_evidence_only": True,
        "external_real_world_accuracy": False,
        "automatic_enforcement_allowed": False,
        "evidence_location": str(CANDIDATE_MANIFEST.parent),
    }


def analyze_terrorism_extremism_v6_rc4_for_fusion(
    text: str,
    input_sources: list[str],
) -> dict[str, object]:
    readiness = get_terrorism_extremism_v6_rc4_readiness()
    textual_source = bool(TEXTUAL_INPUT_SOURCES.intersection(input_sources))
    if not readiness.get("ready"):
        return {
            "available": False,
            "fusion_status": "candidate_not_ready",
            "proposed_category": "",
            "confidence": 0.0,
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "readiness": readiness,
            "behavior": {},
            "community": {},
        }
    if not textual_source:
        return {
            "available": True,
            "fusion_status": "non_textual_input_no_override",
            "proposed_category": "",
            "confidence": 0.0,
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "readiness": readiness,
            "behavior": {},
            "community": {},
        }

    behavior = analyze_terrorism_extremism_v6_rc4(text)
    community = analyze_wikidata_terrorism_candidate_v6_rc4(text)
    proposed_category = ""
    source = "none"
    confidence = 0.0
    proposed_action = ""
    proposed_severity = ""

    if behavior.get("category") == TERRORISM_CATEGORY:
        proposed_category = TERRORISM_CATEGORY
        source = "policy_behavior_and_claimed_designation"
        confidence = min(0.92, float(behavior.get("confidence", 0.86)))
        proposed_action = "Block and escalate"
        proposed_severity = "Critical"
    elif community.get("category") == UNCERTAIN_CATEGORY:
        proposed_category = UNCERTAIN_CATEGORY
        source = "unverified_wikidata_candidate_and_behavior"
        confidence = min(0.64, float(community.get("confidence", 0.58)))
        proposed_action = "Refer to human review"
        proposed_severity = "Unknown"
    elif behavior.get("category") == UNCERTAIN_CATEGORY:
        proposed_category = UNCERTAIN_CATEGORY
        source = "unverified_status_and_behavior"
        confidence = min(0.64, float(behavior.get("confidence", 0.58)))
        proposed_action = "Refer to human review"
        proposed_severity = "Unknown"

    return {
        "available": True,
        "fusion_status": (
            "review_only_candidate_found"
            if proposed_category
            else "no_terrorism_boundary_override"
        ),
        "proposed_category": proposed_category,
        "proposed_action": proposed_action,
        "proposed_severity": proposed_severity,
        "confidence": confidence,
        "human_review_required": bool(proposed_category),
        "proposal_source": source,
        "community_candidate_used": source
        == "unverified_wikidata_candidate_and_behavior",
        "community_candidate_confirmed_designation": False,
        "automatic_enforcement_allowed": False,
        "readiness": readiness,
        "behavior": behavior,
        "community": community,
    }


def apply_terrorism_extremism_v6_rc4_fusion(
    *,
    category: str,
    severity: str,
    action: str,
    confidence: float,
    human_review_required: bool,
    reason: str,
    matched_signals: list[str],
    analysis: dict[str, object],
) -> dict[str, Any]:
    unchanged: dict[str, Any] = {
        "category": category,
        "severity": severity,
        "action": action,
        "confidence": confidence,
        "human_review_required": human_review_required,
        "reason": reason,
        "matched_signals": list(matched_signals),
        "decision_applied": False,
        "fusion_status": str(
            analysis.get("fusion_status", "specialist_unavailable")
        ),
        "automatic_enforcement_allowed": False,
    }
    if not analysis.get("available"):
        return unchanged

    proposed = str(analysis.get("proposed_category", ""))
    if not proposed:
        return unchanged
    if category not in ALLOWED_PRIMARY_BOUNDARIES:
        unchanged["fusion_status"] = "blocked_by_established_category_owner"
        return unchanged

    proposal_source = str(analysis.get("proposal_source", "none"))
    proposed_confidence = float(analysis.get("confidence", 0.0))
    updated_signals = list(matched_signals)
    updated_signals.append(
        "terrorism_extremism_v6_rc4:" + proposal_source
    )

    if proposed == TERRORISM_CATEGORY:
        return {
            "category": TERRORISM_CATEGORY,
            "severity": str(analysis.get("proposed_severity", "Critical")),
            "action": "Block and escalate",
            "confidence": max(confidence, proposed_confidence),
            "human_review_required": True,
            "reason": (
                "The frozen Terrorism & Extremism RC4 policy parser found "
                "relevant behavior together with an explicit designation claim. "
                "This is a review-required recommendation and does not confirm "
                "the legal designation or permit automatic enforcement."
            ),
            "matched_signals": updated_signals,
            "decision_applied": True,
            "fusion_status": "terrorism_review_only_applied",
            "automatic_enforcement_allowed": False,
        }

    if proposed == UNCERTAIN_CATEGORY:
        return {
            "category": UNCERTAIN_CATEGORY,
            "severity": "Unknown",
            "action": "Refer to human review",
            "confidence": max(confidence, proposed_confidence),
            "human_review_required": True,
            "reason": (
                "Potential terrorism-related behavior requires human review, "
                "but organization identity or designation is unverified. "
                "Wikidata is community evidence only and cannot confirm status."
            ),
            "matched_signals": updated_signals,
            "decision_applied": True,
            "fusion_status": "unverified_terrorism_context_review_applied",
            "automatic_enforcement_allowed": False,
        }
    return unchanged
