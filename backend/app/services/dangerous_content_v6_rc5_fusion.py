from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.dangerous_content_v6_rc5_service import (
    DANGEROUS_ACTION,
    DANGEROUS_CATEGORY,
    analyze_dangerous_content_v6_rc5,
)
from app.services.cyberbullying_depiction_boundary_service import (
    analyze_cyberbullying_depiction_boundary,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    BACKEND_ROOT / "storage" / "candidates" / "dangerous-content-v6-rc5"
)
PACKAGED_EVIDENCE_DIRECTORY = (
    BACKEND_ROOT / "app" / "evidence" / "dangerous-content-v6-rc5"
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
    "Normal/Ignore",
    "Uncertain",
    "Abusive Words",
}


@lru_cache(maxsize=1)
def get_dangerous_content_v6_rc5_readiness() -> dict[str, object]:
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
        == "dangerous-content-v6-rc5",
        "development_gate": manifest.get("development_gate_passed") is True,
        "independent_gate": verdict.get(
            "passed_synthetic_independent_readiness_gate"
        )
        is True,
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
        "permitted_output_is_dangerous_only": manifest.get(
            "permitted_active_output"
        )
        == "Dangerous Content only",
        "raw_holdout_not_stored": verdict.get("raw_challenge_text_stored")
        is False,
        "predictions_not_stored": verdict.get("individual_predictions_stored")
        is False,
    }
    ready = all(checks.values())
    return {
        "ready": ready,
        "checks": checks,
        "reason": (
            "Frozen RC5 passed its synthetic independent gate."
            if ready
            else "Frozen RC5 readiness contract is incomplete."
        ),
        "synthetic_evidence_only": True,
        "external_real_world_accuracy": False,
        "automatic_enforcement_allowed": False,
        "evidence_location": str(CANDIDATE_MANIFEST.parent),
    }


def analyze_dangerous_content_v6_rc5_for_fusion(
    text: str,
    input_sources: list[str],
) -> dict[str, object]:
    readiness = get_dangerous_content_v6_rc5_readiness()
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
            "analysis": {},
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
            "analysis": {},
        }

    depiction_boundary = analyze_cyberbullying_depiction_boundary(text)
    if depiction_boundary.get("confirmed_third_person_depiction") is True:
        return {
            "available": True,
            "fusion_status": "blocked_by_violent_depiction_boundary",
            "proposed_category": "",
            "confidence": 0.0,
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "readiness": readiness,
            "depiction_boundary": depiction_boundary,
            "analysis": {},
        }

    analysis = analyze_dangerous_content_v6_rc5(
        text,
        existing_category="Normal/Ignore",
    )
    proposed = (
        DANGEROUS_CATEGORY
        if analysis.get("category") == DANGEROUS_CATEGORY
        else ""
    )
    return {
        "available": True,
        "fusion_status": (
            "review_only_candidate_found"
            if proposed
            else "no_dangerous_boundary_override"
        ),
        "proposed_category": proposed,
        "proposed_action": DANGEROUS_ACTION if proposed else "",
        "proposed_severity": "High" if proposed else "",
        "confidence": (
            min(0.88, float(analysis.get("confidence", 0.76)))
            if proposed
            else 0.0
        ),
        "human_review_required": bool(proposed),
        "proposal_source": str(
            analysis.get("dangerous_content_v6_rc5_status", "none")
        ),
        "automatic_enforcement_allowed": False,
        "readiness": readiness,
        "depiction_boundary": depiction_boundary,
        "analysis": analysis,
    }


def apply_dangerous_content_v6_rc5_fusion(
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
    if category == DANGEROUS_CATEGORY:
        unchanged["fusion_status"] = "dangerous_content_owner_already_applied"
        return unchanged
    if category not in ALLOWED_PRIMARY_BOUNDARIES:
        unchanged["fusion_status"] = "blocked_by_established_category_owner"
        return unchanged

    proposed_confidence = float(analysis.get("confidence", 0.0))
    proposal_source = str(analysis.get("proposal_source", "unknown"))
    updated_signals = list(matched_signals)
    updated_signals.append("dangerous_content_v6_rc5:" + proposal_source)
    return {
        "category": DANGEROUS_CATEGORY,
        "severity": "High",
        "action": DANGEROUS_ACTION,
        "confidence": max(confidence, proposed_confidence),
        "human_review_required": True,
        "reason": (
            "The independently evaluated Dangerous Content RC5 specialist "
            "found advocacy plus physical-hazard evidence. This is a "
            "review-required recommendation based on synthetic validation; "
            "it does not permit automatic enforcement."
        ),
        "matched_signals": updated_signals,
        "decision_applied": True,
        "fusion_status": "dangerous_content_review_only_applied",
        "automatic_enforcement_allowed": False,
    }
