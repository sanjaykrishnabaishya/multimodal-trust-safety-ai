from __future__ import annotations

import re
from typing import Any, Mapping

from app.services.screen_media_llm_rag_v4_service import (
    MEDIA_REVIEW_ACTION,
    UNCERTAIN_CATEGORY,
    analyze_screen_media_llm_rag_v4,
)


NORMAL_CATEGORY = "Normal/Ignore"
SEXUAL_CATEGORY = "Graphic, Obscene & Sexual Content"
ALLOW_ACTION = "Allow"
ALLOW_WARNING_REVIEW_ACTION = (
    "Allow with sensitive-content warning and refer to human review"
)
AGE_RESTRICT_BLOCK_ACTION = "Age-restrict/block distribution"
ALLOWED_EXISTING_BOUNDARIES = {None, NORMAL_CATEGORY, UNCERTAIN_CATEGORY}
SAFE_CONTEXT_TYPES = {
    "recognized_artwork",
    "recognized_monument",
    "verified_educational_material",
}
TRUSTED_EVIDENCE_SOURCES = {
    "signed_visual_pipeline",
    "trusted_visual_classifier",
    "verified_media_ingest",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _base(status: str) -> dict[str, Any]:
    return {
        "available": True,
        "category": None,
        "severity": "None",
        "action": None,
        "confidence": 0.0,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "decision_applied": False,
        "status": status,
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
        "caption_required": False,
        "local_llm_used": False,
    }


def _clean_visual_evidence(value: Mapping[str, Any] | None) -> dict[str, Any]:
    evidence = dict(value or {})
    try:
        confidence = float(evidence.get("classification_confidence", 0.0))
        adult_confidence = float(evidence.get("adult_confidence", 0.0))
        sample_coverage = float(evidence.get("sample_coverage", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
        adult_confidence = 0.0
        sample_coverage = 0.0
    return {
        "evidence_present": bool(evidence),
        "evidence_source": str(evidence.get("evidence_source", "")).strip().lower(),
        "visual_pipeline_ready": evidence.get("visual_pipeline_ready") is True,
        "independently_validated": evidence.get("independently_validated") is True,
        "model_id": " ".join(str(evidence.get("model_id", "")).split()),
        "model_revision": " ".join(str(evidence.get("model_revision", "")).split()),
        "artifact_sha256": str(evidence.get("artifact_sha256", "")).strip().lower(),
        "verdict_sha256": str(evidence.get("verdict_sha256", "")).strip().lower(),
        "classification_confidence": confidence,
        "adult_confidence": adult_confidence,
        "sample_coverage": sample_coverage,
        "context_type": str(evidence.get("context_type", "")).strip().lower(),
        "art_culture_or_education_verified": (
            evidence.get("art_culture_or_education_verified") is True
        ),
        "non_explicit_intimacy": evidence.get("non_explicit_intimacy") is True,
        "visible_nudity": evidence.get("visible_nudity") is True,
        "visible_private_parts": evidence.get("visible_private_parts") is True,
        "explicit_sexual_activity": evidence.get("explicit_sexual_activity") is True,
        "fully_obscured": evidence.get("fully_obscured") is True,
        "no_explicit_detail_visible": (
            evidence.get("no_explicit_detail_visible") is True
        ),
        "age_ambiguous": evidence.get("age_ambiguous") is True,
        "child_risk_detected": evidence.get("child_risk_detected") is True,
        "self_report_only": evidence.get("self_report_only") is True,
        "llm_only": evidence.get("llm_only") is True,
    }


def _evidence_contract(
    evidence: Mapping[str, Any], *, content_type: str
) -> tuple[bool, list[str]]:
    required_coverage = 1.0 if str(content_type).strip().lower() == "image" else 0.90
    checks = {
        "visual_media": str(content_type).strip().lower() in {"image", "video"},
        "trusted_source": evidence["evidence_source"] in TRUSTED_EVIDENCE_SOURCES,
        "pipeline_ready": evidence["visual_pipeline_ready"],
        "independently_validated": evidence["independently_validated"],
        "model_identity": bool(evidence["model_id"] and evidence["model_revision"]),
        "artifact_hash": SHA256_PATTERN.fullmatch(evidence["artifact_sha256"])
        is not None,
        "verdict_hash": SHA256_PATTERN.fullmatch(evidence["verdict_sha256"])
        is not None,
        "classification_confidence": evidence["classification_confidence"] >= 0.95,
        "sample_coverage": evidence["sample_coverage"] >= required_coverage,
        "not_self_report_only": not evidence["self_report_only"],
        "not_llm_only": not evidence["llm_only"],
    }
    failures = [name for name, passed in checks.items() if not passed]
    return not failures, failures


def analyze_captionless_visual_boundary_v6(
    text: str,
    *,
    content_type: str,
    existing_category: str | None,
    visual_evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Route captionless visual sexual-content boundaries deterministically.

    A future vision component may supply evidence, but it cannot choose policy
    actions. Unvalidated, self-reported, or LLM-only evidence always fails closed.
    This candidate never creates Child Exploitation and never replaces another
    established category owner.
    """

    base = analyze_screen_media_llm_rag_v4(
        text,
        content_type=content_type,
        existing_category=existing_category,
        extracted_evidence={},
        publisher_metadata=None,
        visual_evidence=None,
        llm_analysis=None,
        run_local_llm=False,
    )
    if existing_category not in ALLOWED_EXISTING_BOUNDARIES:
        return {
            **base,
            "v6_status": "blocked_by_established_category_owner",
            "visual_boundary_used": False,
        }

    evidence = _clean_visual_evidence(visual_evidence)
    contract_valid, contract_failures = _evidence_contract(
        evidence, content_type=content_type
    )
    common = {
        "visual_boundary_used": contract_valid,
        "visual_evidence_contract_valid": contract_valid,
        "visual_evidence_contract_failures": contract_failures,
        "caption_required": False,
        "local_llm_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    if not evidence["evidence_present"]:
        return {
            **_base("captionless_visual_evidence_missing_review_candidate"),
            **common,
            "category": UNCERTAIN_CATEGORY,
            "severity": "Unknown",
            "action": MEDIA_REVIEW_ACTION,
            "human_review_required": True,
            "decision_applied": True,
            "v6_status": "missing_visual_evidence_fails_closed",
        }
    if not contract_valid:
        return {
            **_base("unvalidated_visual_evidence_review_candidate"),
            **common,
            "category": UNCERTAIN_CATEGORY,
            "severity": "Unknown",
            "action": MEDIA_REVIEW_ACTION,
            "human_review_required": True,
            "decision_applied": True,
            "v6_status": "visual_evidence_contract_failed",
        }
    if evidence["child_risk_detected"]:
        return {
            **_base("child_safety_boundary_review_candidate"),
            **common,
            "category": UNCERTAIN_CATEGORY,
            "severity": "Unknown",
            "action": MEDIA_REVIEW_ACTION,
            "human_review_required": True,
            "decision_applied": True,
            "v6_status": "child_safety_owner_required_no_visual_override",
        }
    if evidence["fully_obscured"] and evidence["no_explicit_detail_visible"]:
        return {
            **_base("validated_full_obscuration_allow_candidate"),
            **common,
            "category": NORMAL_CATEGORY,
            "action": ALLOW_ACTION,
            "confidence": evidence["classification_confidence"],
            "decision_applied": True,
            "v6_status": "fully_obscured_no_explicit_detail",
        }

    safe_context = bool(
        evidence["context_type"] in SAFE_CONTEXT_TYPES
        and evidence["art_culture_or_education_verified"]
    )
    if safe_context and not evidence["explicit_sexual_activity"]:
        return {
            **_base("verified_art_culture_or_education_allow_candidate"),
            **common,
            "category": NORMAL_CATEGORY,
            "action": ALLOW_ACTION,
            "confidence": evidence["classification_confidence"],
            "decision_applied": True,
            "v6_status": "verified_art_culture_or_education_allowed",
        }

    clear_adult = bool(
        not evidence["age_ambiguous"] and evidence["adult_confidence"] >= 0.95
    )
    explicit_content = bool(
        evidence["visible_nudity"]
        or evidence["visible_private_parts"]
        or evidence["explicit_sexual_activity"]
    )
    if explicit_content and clear_adult:
        return {
            **_base("explicit_adult_visual_content_block_candidate"),
            **common,
            "category": SEXUAL_CATEGORY,
            "severity": "High",
            "action": AGE_RESTRICT_BLOCK_ACTION,
            "confidence": evidence["classification_confidence"],
            "human_review_required": False,
            "decision_applied": True,
            "v6_status": "explicit_adult_content_age_restrict_or_block",
        }
    if evidence["non_explicit_intimacy"] and not explicit_content:
        return {
            **_base("non_explicit_intimacy_warning_review_candidate"),
            **common,
            "category": UNCERTAIN_CATEGORY,
            "severity": "Low",
            "action": ALLOW_WARNING_REVIEW_ACTION,
            "confidence": evidence["classification_confidence"],
            "human_review_required": True,
            "decision_applied": True,
            "v6_status": "non_explicit_intimacy_allowed_with_warning_and_review",
        }
    return {
        **_base("ambiguous_visual_boundary_review_candidate"),
        **common,
        "category": UNCERTAIN_CATEGORY,
        "severity": "Unknown",
        "action": MEDIA_REVIEW_ACTION,
        "human_review_required": True,
        "decision_applied": True,
        "v6_status": "visual_boundary_ambiguous_requires_review",
    }
