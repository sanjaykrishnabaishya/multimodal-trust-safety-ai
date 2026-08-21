from __future__ import annotations

import re
from typing import Any, Mapping


NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
SEXUAL_CATEGORY = "Graphic, Obscene & Sexual Content"

ALLOW_ACTION = "Allow"
REVIEW_ACTION = "Refer to human review"
WARNING_REVIEW_ACTION = (
    "Allow with sensitive-content warning and refer to human review"
)
AGE_RESTRICT_BLOCK_ACTION = "Age-restrict/block distribution"

ART_CONTEXT_TYPES = {
    "verified_artwork",
    "verified_monument",
    "verified_cultural_object",
    "verified_educational_material",
}
SCREEN_MEDIA_TYPES = {"film", "movie", "television_series", "tv_series"}
TRUSTED_PROVENANCE_SOURCES = {
    "museum_catalog",
    "cultural_institution_catalog",
    "trusted_educational_repository",
    "verified_publisher_metadata",
    "verified_catalog_metadata",
}
TRUSTED_VISUAL_SOURCES = {
    "signed_visual_pipeline",
    "trusted_visual_classifier",
    "verified_media_ingest",
}
ALLOWED_EXISTING_BOUNDARIES = {
    None,
    NORMAL_CATEGORY,
    UNCERTAIN_CATEGORY,
    SEXUAL_CATEGORY,
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
        "decision_applied": False,
        "status": status,
        "policy_revision": "captionless-visual-v8-rc2-development",
        "art_auto_allow_policy_eligible": False,
        "screen_media_auto_allow_forbidden": True,
        "automatic_allow_enabled": False,
        "automatic_enforcement_allowed": False,
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
        "local_llm_authority_used": False,
        "age_inferred_from_pixels": False,
    }


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _hash_is_valid(value: Any) -> bool:
    return SHA256_PATTERN.fullmatch(str(value or "").strip().lower()) is not None


def _clean_visual(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(value or {})
    return {
        "present": bool(source),
        "evidence_source": str(source.get("evidence_source", "")).strip().lower(),
        "pipeline_ready": source.get("pipeline_ready") is True,
        "candidate_frozen": source.get("candidate_frozen") is True,
        "independent_verdict_passed": (
            source.get("independent_verdict_passed") is True
        ),
        "model_id": " ".join(str(source.get("model_id", "")).split()),
        "model_revision": " ".join(str(source.get("model_revision", "")).split()),
        "artifact_sha256": str(source.get("artifact_sha256", "")).strip().lower(),
        "verdict_sha256": str(source.get("verdict_sha256", "")).strip().lower(),
        "candidate_boundary": str(source.get("candidate_boundary", "uncertain"))
        .strip()
        .lower(),
        "candidate_confidence": _number(source.get("candidate_confidence")),
        "sample_coverage": _number(source.get("sample_coverage")),
        "decode_status": str(source.get("decode_status", "missing"))
        .strip()
        .lower(),
        "visible_nudity": source.get("visible_nudity") is True,
        "visible_private_parts": source.get("visible_private_parts") is True,
        "explicit_sexual_activity": source.get("explicit_sexual_activity") is True,
        "non_explicit_intimacy": source.get("non_explicit_intimacy") is True,
        "fully_obscured": source.get("fully_obscured") is True,
        "no_explicit_detail_visible": (
            source.get("no_explicit_detail_visible") is True
        ),
        "adult_status_verified": source.get("adult_status_verified") is True,
        "age_ambiguous": source.get("age_ambiguous") is not False,
        "child_risk_detected": source.get("child_risk_detected") is True,
        "self_report_only": source.get("self_report_only") is True,
        "llm_only": source.get("llm_only") is True,
    }


def _clean_provenance(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(value or {})
    return {
        "present": bool(source),
        "evidence_source": str(source.get("evidence_source", "")).strip().lower(),
        "context_type": str(source.get("context_type", "")).strip().lower(),
        "work_identity_verified": source.get("work_identity_verified") is True,
        "independently_verified": source.get("independently_verified") is True,
        "record_id": " ".join(str(source.get("record_id", "")).split()),
        "record_sha256": str(source.get("record_sha256", "")).strip().lower(),
        "media_sha256": str(source.get("media_sha256", "")).strip().lower(),
        "signed_evidence": source.get("signed_evidence") is True,
        "self_report_only": source.get("self_report_only") is True,
        "llm_only": source.get("llm_only") is True,
    }


def _visual_contract(
    evidence: Mapping[str, Any], *, content_type: str
) -> tuple[bool, list[str]]:
    normalized_type = str(content_type).strip().lower()
    minimum_coverage = 1.0 if normalized_type == "image" else 0.90
    checks = {
        "visual_media": normalized_type in {"image", "video"},
        "trusted_visual_source": (
            evidence["evidence_source"] in TRUSTED_VISUAL_SOURCES
        ),
        "pipeline_ready": evidence["pipeline_ready"],
        "candidate_frozen": evidence["candidate_frozen"],
        "independent_verdict_passed": evidence["independent_verdict_passed"],
        "model_identity": bool(evidence["model_id"] and evidence["model_revision"]),
        "artifact_hash": _hash_is_valid(evidence["artifact_sha256"]),
        "verdict_hash": _hash_is_valid(evidence["verdict_sha256"]),
        "complete_decode": evidence["decode_status"] == "complete",
        "sample_coverage": evidence["sample_coverage"] >= minimum_coverage,
        "confidence": evidence["candidate_confidence"] >= 0.85,
        "not_self_report_only": not evidence["self_report_only"],
        "not_llm_only": not evidence["llm_only"],
    }
    failures = [name for name, passed in checks.items() if not passed]
    return not failures, failures


def _provenance_contract(
    evidence: Mapping[str, Any], *, permitted_types: set[str]
) -> tuple[bool, list[str]]:
    checks = {
        "trusted_provenance_source": (
            evidence["evidence_source"] in TRUSTED_PROVENANCE_SOURCES
        ),
        "permitted_context_type": evidence["context_type"] in permitted_types,
        "work_identity_verified": evidence["work_identity_verified"],
        "independently_verified": evidence["independently_verified"],
        "record_id": bool(evidence["record_id"]),
        "record_hash": _hash_is_valid(evidence["record_sha256"]),
        "media_hash": _hash_is_valid(evidence["media_sha256"]),
        "signed_evidence": evidence["signed_evidence"],
        "not_self_report_only": not evidence["self_report_only"],
        "not_llm_only": not evidence["llm_only"],
    }
    failures = [name for name, passed in checks.items() if not passed]
    return not failures, failures


def _review(
    status: str,
    *,
    confidence: float = 0.0,
    warning: bool = False,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **_base(status),
        "category": UNCERTAIN_CATEGORY,
        "severity": "Low" if warning else "Unknown",
        "action": WARNING_REVIEW_ACTION if warning else REVIEW_ACTION,
        "confidence": confidence,
        "human_review_required": True,
        "decision_applied": True,
        "evidence": dict(evidence or {}),
    }


def analyze_captionless_visual_policy_v8_rc2(
    *,
    content_type: str,
    existing_category: str | None,
    visual_evidence: Mapping[str, Any] | None,
    provenance_evidence: Mapping[str, Any] | None,
    llm_analysis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the RC2 art-versus-screen-media boundary.

    The LLM may provide a review concern but has no authority to verify art,
    identify a film, infer age, or create Allow.  Automatic enforcement remains
    disabled until this policy and its visual evidence source pass independent
    evaluation and guarded fusion testing.
    """

    if existing_category not in ALLOWED_EXISTING_BOUNDARIES:
        return {
            **_base("blocked_by_established_category_owner"),
            "category": existing_category,
            "preserved_category": existing_category,
        }

    visual = _clean_visual(visual_evidence)
    provenance = _clean_provenance(provenance_evidence)
    llm = dict(llm_analysis or {})
    llm_concern = llm.get("review_concern") is True

    visual_valid, visual_failures = _visual_contract(
        visual, content_type=content_type
    )
    art_valid, art_failures = _provenance_contract(
        provenance, permitted_types=ART_CONTEXT_TYPES
    )
    screen_valid, screen_failures = _provenance_contract(
        provenance, permitted_types=SCREEN_MEDIA_TYPES
    )
    common_evidence = {
        "visual_contract_valid": visual_valid,
        "visual_contract_failures": visual_failures,
        "art_provenance_valid": art_valid,
        "art_provenance_failures": art_failures,
        "screen_provenance_valid": screen_valid,
        "screen_provenance_failures": screen_failures,
        "context_type": provenance["context_type"],
        "candidate_boundary": visual["candidate_boundary"],
        "decode_status": visual["decode_status"],
        "sample_coverage": visual["sample_coverage"],
        "llm_concern_present": llm_concern,
    }

    if visual["child_risk_detected"] or visual["age_ambiguous"]:
        return _review(
            "child_or_age_safety_boundary_requires_review",
            confidence=visual["candidate_confidence"],
            evidence=common_evidence,
        )

    if not visual_valid:
        return _review(
            "visual_evidence_incomplete_or_unvalidated",
            confidence=visual["candidate_confidence"],
            evidence=common_evidence,
        )

    is_explicit = bool(
        visual["candidate_boundary"] == "explicit_adult_sexual_content"
        or visual["visible_private_parts"]
        or visual["explicit_sexual_activity"]
    )
    is_intimacy = bool(
        visual["candidate_boundary"] == "non_explicit_intimacy"
        or visual["non_explicit_intimacy"]
    )

    # Screen-work identity may alter review routing, but never creates Allow.
    if screen_valid:
        if is_explicit and visual["adult_status_verified"]:
            return {
                **_base("verified_screen_media_explicit_adult_restricted"),
                "category": SEXUAL_CATEGORY,
                "severity": "High",
                "action": AGE_RESTRICT_BLOCK_ACTION,
                "confidence": visual["candidate_confidence"],
                "decision_applied": True,
                "evidence": common_evidence,
            }
        if is_intimacy and not is_explicit:
            return _review(
                "verified_screen_media_non_explicit_intimacy_review",
                confidence=visual["candidate_confidence"],
                warning=True,
                evidence=common_evidence,
            )
        if visual["fully_obscured"] and visual["no_explicit_detail_visible"]:
            return {
                **_base("verified_screen_media_obscured_no_policy_override"),
                "evidence": common_evidence,
            }
        if (
            visual["candidate_boundary"] == "safe_or_other"
            and not visual["visible_nudity"]
        ):
            return {
                **_base("verified_screen_media_safe_scene_no_policy_override"),
                "evidence": common_evidence,
            }
        return _review(
            "verified_screen_media_uncertain_scene_review",
            confidence=visual["candidate_confidence"],
            evidence=common_evidence,
        )

    # Verified art/culture/education can earn the only RC2 Allow route.  Nude
    # anatomy is not itself disqualifying, but activity and child risk are.
    art_candidate = visual["candidate_boundary"] in {
        "verified_art_culture_or_education",
        "safe_or_other",
    }
    if art_valid and art_candidate and not visual["explicit_sexual_activity"]:
        return {
            **_base("verified_art_culture_or_education_allow_candidate"),
            "category": NORMAL_CATEGORY,
            "action": ALLOW_ACTION,
            "confidence": visual["candidate_confidence"],
            "decision_applied": True,
            "art_auto_allow_policy_eligible": True,
            "evidence": common_evidence,
        }

    if is_explicit and visual["adult_status_verified"]:
        return {
            **_base("explicit_adult_visual_content_restricted"),
            "category": SEXUAL_CATEGORY,
            "severity": "High",
            "action": AGE_RESTRICT_BLOCK_ACTION,
            "confidence": visual["candidate_confidence"],
            "decision_applied": True,
            "evidence": common_evidence,
        }
    if is_intimacy and not is_explicit:
        return _review(
            "non_explicit_intimacy_warning_review",
            confidence=visual["candidate_confidence"],
            warning=True,
            evidence=common_evidence,
        )
    if llm_concern:
        return _review(
            "llm_concern_can_only_escalate_to_review",
            confidence=visual["candidate_confidence"],
            evidence=common_evidence,
        )
    return _review(
        "unverified_or_ambiguous_visual_context_review",
        confidence=visual["candidate_confidence"],
        evidence=common_evidence,
    )
