from __future__ import annotations

import re
from typing import Any, Mapping

from app.services.screen_media_llm_rag_v4_service import (
    MEDIA_REVIEW_ACTION,
    UNCERTAIN_CATEGORY,
    analyze_screen_media_llm_rag_v4,
)


NORMAL_CATEGORY = "Normal/Ignore"
ALLOW_ACTION = "Allow"
SAFE_CONTEXT_TYPES = {
    "recognized_artwork",
    "recognized_monument",
    "verified_educational_material",
}
ALLOWED_EXISTING_BOUNDARIES = {None, NORMAL_CATEGORY, UNCERTAIN_CATEGORY}
TRUSTED_EVIDENCE_SOURCES = {
    "signed_visual_pipeline",
    "trusted_visual_classifier",
    "verified_media_ingest",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _result(status: str) -> dict[str, Any]:
    return {
        "available": True,
        "category": None,
        "severity": "None",
        "action": None,
        "confidence": 0.0,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "automatic_allow_allowed": False,
        "decision_applied": False,
        "status": status,
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
        "caption_required_for_safe_context": False,
        "local_llm_used": False,
    }


def _validated_visual_safe_context(
    value: Mapping[str, Any] | None,
    *,
    content_type: str,
) -> tuple[bool, dict[str, Any]]:
    evidence = dict(value or {})
    context_type = str(evidence.get("context_type", "")).strip().lower()
    evidence_source = str(evidence.get("evidence_source", "")).strip().lower()
    model_id = " ".join(str(evidence.get("model_id", "")).split())
    model_revision = " ".join(str(evidence.get("model_revision", "")).split())
    artifact_sha256 = str(evidence.get("artifact_sha256", "")).strip().lower()
    readiness_sha256 = str(evidence.get("readiness_verdict_sha256", "")).strip().lower()
    try:
        context_confidence = float(evidence.get("context_confidence", 0.0))
        sample_coverage = float(evidence.get("sample_coverage", 0.0))
    except (TypeError, ValueError):
        context_confidence = 0.0
        sample_coverage = 0.0

    visual_media = str(content_type).strip().lower() in {"image", "video"}
    required_coverage = 1.0 if str(content_type).strip().lower() == "image" else 0.90
    identity_or_purpose_verified = bool(
        evidence.get("cultural_context_verified") is True
        if context_type in {"recognized_artwork", "recognized_monument"}
        else evidence.get("educational_context_verified") is True
        if context_type == "verified_educational_material"
        else False
    )
    safety_components_ready = bool(
        evidence.get("sexual_safety_component_ready") is True
        and evidence.get("child_safety_component_ready") is True
    )
    no_safety_concern = bool(
        evidence.get("no_visible_explicit_sexual_detail") is True
        and evidence.get("sexual_content_risk_detected") is False
        and evidence.get("child_exploitation_risk_detected") is False
        and evidence.get("sexual_harassment_risk_detected") is False
    )
    contract_checks = {
        "visual_media": visual_media,
        "approved_context_type": context_type in SAFE_CONTEXT_TYPES,
        "trusted_evidence_source": evidence_source in TRUSTED_EVIDENCE_SOURCES,
        "visual_context_component_ready": (
            evidence.get("visual_context_component_ready") is True
        ),
        "independently_validated": evidence.get("independently_validated") is True,
        "model_identity_present": bool(model_id and model_revision),
        "artifact_hash_valid": SHA256_PATTERN.fullmatch(artifact_sha256) is not None,
        "readiness_verdict_hash_valid": (
            SHA256_PATTERN.fullmatch(readiness_sha256) is not None
        ),
        "context_confidence": context_confidence >= 0.95,
        "sample_coverage": sample_coverage >= required_coverage,
        "identity_or_purpose_verified": identity_or_purpose_verified,
        "safety_components_ready": safety_components_ready,
        "no_safety_concern": no_safety_concern,
        "not_self_report_only": evidence.get("self_report_only") is not True,
        "not_llm_only": evidence.get("llm_only") is not True,
    }
    return all(contract_checks.values()), {
        "context_type": context_type,
        "context_confidence": context_confidence,
        "sample_coverage": sample_coverage,
        "required_sample_coverage": required_coverage,
        "contract_checks": contract_checks,
        "safe_context_claimed": bool(
            evidence.get("safe_context_claimed") is True or context_type
        ),
        "safety_conflict": not no_safety_concern,
    }


def analyze_captionless_visual_safe_context_v5(
    text: str,
    *,
    content_type: str,
    existing_category: str | None,
    extracted_evidence: Mapping[str, Any] | None = None,
    visual_context_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a caption-independent, evidence-gated safe-context policy.

    This layer never infers artwork, monument, or educational purpose itself.
    It consumes a separately validated visual component's signed evidence. A
    self-report, LLM guess, or unvalidated classifier can only trigger review.
    Established policy owners and visible sexual/child-safety concerns always win.
    """

    base = analyze_screen_media_llm_rag_v4(
        text,
        content_type=content_type,
        existing_category=existing_category,
        extracted_evidence=extracted_evidence or {},
        publisher_metadata=None,
        visual_evidence=None,
        llm_analysis=None,
        run_local_llm=False,
    )
    if existing_category not in ALLOWED_EXISTING_BOUNDARIES:
        return {
            **base,
            "v5_status": "blocked_by_established_category_owner",
            "visual_safe_context_used": False,
            "caption_required_for_safe_context": False,
            "local_llm_used": False,
        }
    if base.get("category") not in {None, NORMAL_CATEGORY, UNCERTAIN_CATEGORY}:
        return {
            **base,
            "v5_status": "blocked_by_existing_specialist_concern",
            "visual_safe_context_used": False,
            "caption_required_for_safe_context": False,
            "local_llm_used": False,
        }

    validated, evidence = _validated_visual_safe_context(
        visual_context_evidence,
        content_type=content_type,
    )
    common = {
        "visual_safe_context_used": validated,
        "visual_safe_context_evidence": evidence,
        "caption_required_for_safe_context": False,
        "local_llm_used": False,
        "automatic_enforcement_allowed": False,
        "automatic_allow_allowed": False,
        "connected_to_live_moderation": False,
    }
    if validated:
        return {
            **_result("validated_captionless_visual_safe_context_allow_candidate"),
            **common,
            "category": NORMAL_CATEGORY,
            "action": ALLOW_ACTION,
            "confidence": min(0.99, float(evidence["context_confidence"])),
            "decision_applied": True,
            "v5_status": "captionless_art_culture_or_education_verified_safe",
        }
    if evidence["safe_context_claimed"]:
        return {
            **_result("unverified_visual_safe_context_review_candidate"),
            **common,
            "category": UNCERTAIN_CATEGORY,
            "severity": "Unknown",
            "action": MEDIA_REVIEW_ACTION,
            "confidence": 0.5,
            "human_review_required": True,
            "decision_applied": True,
            "v5_status": (
                "visual_safety_conflict_requires_review"
                if evidence["safety_conflict"]
                else "visual_safe_context_not_fully_verified"
            ),
        }
    return {
        **base,
        **common,
        "v5_status": "no_visual_safe_context_claim_or_evidence",
    }
