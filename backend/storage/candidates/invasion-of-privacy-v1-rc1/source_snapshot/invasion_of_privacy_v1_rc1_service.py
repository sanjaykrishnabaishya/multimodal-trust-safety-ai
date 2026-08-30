"""Consent-aware, local-only Invasion of Privacy V1 RC1 policy."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any


PRIVACY_CATEGORY = "Invasion of Privacy"
NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
PRIVACY_ACTION = "Restrict and send for human review"
UNCERTAIN_ACTION = "Refer to human review"
POLICY_PATH = Path(__file__).resolve().parents[1] / "evidence" / "invasion_of_privacy_v1_rc1_policy.json"

NONCONSENSUAL_TERMS = (
    "without consent", "without permission", "against their wishes",
    "despite refusing consent", "permission was never given",
    "did not agree", "unaware of the recording", "without authorization",
)
PRIVATE_SPACE_TERMS = (
    "private home", "private room", "bedroom", "bathroom", "changing room",
    "dressing room", "hotel room", "private office", "private conversation",
    "inside the home", "behind a closed door",
)
CAPTURE_TERMS = (
    "secretly recorded", "secretly records", "hidden camera", "concealed camera",
    "covert camera", "recorded through a window", "filmed through a window",
    "covert microphone", "secret audio recording", "records private conversation",
    "eavesdrops", "wiretaps a private conversation",
)
TRACKING_TERMS = (
    "tracks live location", "hidden location tracker", "concealed gps tracker",
    "follows every movement", "persistent physical stalking", "stalks the person",
    "monitors daily movements", "tracks a private vehicle", "location surveillance",
)
SHARING_TERMS = (
    "shares a private photo", "shares an intimate photo", "publishes a private video",
    "distributes an intimate video", "uploads a private recording",
    "leaks a private recording", "forwards private media", "threatens to publish private media",
    "intimate video", "private recording",
)
ACTIVE_CASE_TERMS = (
    "this account", "this user", "this upload", "this recording", "this post",
    "credible allegation", "credible report", "evidence indicates", "victim reports",
    "is currently", "is distributing", "is tracking", "is recording",
)
CONSENTED_TERMS = (
    "explicit written consent", "all participants consented", "permission was documented",
    "owner authorized", "user-owned recording", "consented recording",
    "agreed to recording and distribution", "authorized production",
)
PUBLIC_OR_DISCLOSED_TERMS = (
    "ordinary public event", "public performance", "public press conference",
    "disclosed security camera", "clearly posted surveillance notice",
    "doorbell camera on the owner's property", "public street scene",
    "broadcast interview with consent", "official public livestream",
)
SAFE_CONTEXT_TERMS = (
    "privacy awareness", "consent education", "safety training", "prevention campaign",
    "academic research", "policy analysis", "news report", "documentary discussion",
    "fictional story", "fictional scene", "law-enforcement guidance",
    "victim support guide", "how to report a privacy violation",
)
EXPLICIT_SAFE_BOUNDARY_TERMS = (
    "contains no victim media", "contains no live surveillance", "does not identify a real person",
    "does not facilitate tracking", "quoted only for analysis", "no active case is described",
    "no private recording is attached", "fictional and not real",
)
UNCERTAINTY_TERMS = (
    "consent is unclear", "consent cannot be verified", "permission is unknown",
    "ownership is unresolved", "location may be private", "location is unclear",
    "provenance is unknown", "relationship is unknown", "recording purpose is unclear",
    "authorization cannot be established",
)
INCOMPLETE_EVIDENCE_TERMS = (
    "media could not be decoded", "unsupported media format", "metadata is incomplete",
    "only a thumbnail is available", "visual evidence is incomplete",
)
ORDINARY_BENIGN_TERMS = (
    "package tracking", "fitness tracking", "camera settings", "private variable",
    "browser privacy settings", "photo backup", "calendar reminder", "traffic camera data",
)
ESTABLISHED_OWNERS = {
    "Religiously Offensive Content", "Hate Speech & Discrimination",
    "Terrorism & Extremism", "Violent Content", "Dangerous Content",
    "Graphic, Obscene & Sexual Content", "Sexual Harassment",
    "Cyberbullying & Harassment", "Publishing Private Information",
    "Identity Theft & Impersonation", "Illegal Activities",
    "Misinformation & Fake News", "Spam, Scam & Phishing",
    "Intellectual Property Infringement", "Malicious Programs",
    "Abusive Words", "Child Exploitation",
}


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _policy_available() -> bool:
    try:
        payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("component") == PRIVACY_CATEGORY


def analyze_invasion_of_privacy_v1_rc1(text: str, input_sources: list[str]) -> dict[str, Any]:
    normalized = _normalize(text)
    nonconsensual = _any(normalized, NONCONSENSUAL_TERMS)
    private_space = _any(normalized, PRIVATE_SPACE_TERMS)
    capture = _any(normalized, CAPTURE_TERMS)
    tracking = _any(normalized, TRACKING_TERMS)
    sharing = _any(normalized, SHARING_TERMS)
    active_case = _any(normalized, ACTIVE_CASE_TERMS)
    consented = _any(normalized, CONSENTED_TERMS)
    public_or_disclosed = _any(normalized, PUBLIC_OR_DISCLOSED_TERMS)
    safe_context = _any(normalized, SAFE_CONTEXT_TERMS)
    explicit_safe_boundary = _any(normalized, EXPLICIT_SAFE_BOUNDARY_TERMS)
    uncertainty = _any(normalized, UNCERTAINTY_TERMS)
    incomplete = _any(normalized, INCOMPLETE_EVIDENCE_TERMS)
    benign = _any(normalized, ORDINARY_BENIGN_TERMS)
    intrusion_act = capture or tracking or sharing
    privacy_context = nonconsensual or private_space

    result: dict[str, Any] = {
        "available": _policy_available(),
        "version": "invasion-of-privacy-v1-rc1",
        "fusion_status": "no_privacy_boundary_override",
        "proposed_category": "", "proposed_action": "", "proposed_severity": "",
        "confidence": 0.0, "human_review_required": False,
        "nonconsensual_signal": nonconsensual, "private_space_signal": private_space,
        "capture_signal": capture, "tracking_signal": tracking, "sharing_signal": sharing,
        "active_case": active_case, "consented_context": consented,
        "public_or_disclosed_context": public_or_disclosed,
        "safe_context": safe_context, "uncertainty_signal": uncertainty,
        "incomplete_evidence": incomplete,
        "real_victim_media_stored": False, "private_identifiers_stored": False,
        "face_recognition_used": False, "identity_inference_from_appearance_allowed": False,
        "consent_inference_from_appearance_allowed": False,
        "private_location_inference_from_appearance_allowed": False,
        "external_provider_used": False, "external_transmission_allowed": False,
        "automatic_enforcement_allowed": False, "warnings": [],
    }
    if not result["available"]:
        result["fusion_status"] = "policy_evidence_unavailable"
        return result
    if not normalized:
        result["fusion_status"] = "empty_input_no_override"
        return result
    if benign and not intrusion_act and not nonconsensual:
        result["fusion_status"] = "ordinary_benign_context_no_override"
        return result
    if consented and not nonconsensual:
        result["fusion_status"] = "documented_consent_no_override"
        return result
    if public_or_disclosed and not nonconsensual and not tracking:
        result["fusion_status"] = "public_or_disclosed_context_no_override"
        return result
    if safe_context and (explicit_safe_boundary or (not active_case and not nonconsensual)):
        result["fusion_status"] = "safe_reporting_education_no_override"
        return result
    if (uncertainty or incomplete) and intrusion_act:
        result.update({
            "fusion_status": "privacy_consent_or_evidence_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY,
            "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High", "confidence": 0.76,
            "human_review_required": True,
        })
        return result
    if intrusion_act and privacy_context:
        result.update({
            "fusion_status": "invasion_of_privacy_review_candidate",
            "proposed_category": PRIVACY_CATEGORY,
            "proposed_action": PRIVACY_ACTION,
            "proposed_severity": "High", "confidence": 0.94,
            "human_review_required": True,
        })
        return result
    if active_case and intrusion_act:
        result.update({
            "fusion_status": "possible_privacy_intrusion_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY,
            "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High", "confidence": 0.68,
            "human_review_required": True,
        })
    return result


def apply_invasion_of_privacy_v1_rc1_fusion(
    *, category: str, severity: str, action: str, confidence: float,
    human_review_required: bool, reason: str, matched_signals: list[str],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    updated = {
        "category": category, "severity": severity, "action": action,
        "confidence": confidence, "human_review_required": human_review_required,
        "reason": reason, "matched_signals": list(matched_signals),
        "decision_applied": False,
        "fusion_status": str(analysis.get("fusion_status", "unavailable")),
        "automatic_enforcement_allowed": False,
    }
    proposal = str(analysis.get("proposed_category", ""))
    if not proposal:
        return updated
    if category == PRIVACY_CATEGORY:
        updated["fusion_status"] = "privacy_owner_already_applied"
        updated["human_review_required"] = True
        return updated
    if category in ESTABLISHED_OWNERS:
        updated["fusion_status"] = "blocked_by_established_category_owner"
        return updated
    if category not in {NORMAL_CATEGORY, UNCERTAIN_CATEGORY}:
        updated["fusion_status"] = "blocked_by_unknown_category_owner"
        return updated
    if category == UNCERTAIN_CATEGORY and proposal == UNCERTAIN_CATEGORY:
        updated["fusion_status"] = "uncertain_owner_already_applied"
        updated["human_review_required"] = True
        return updated
    updated.update({
        "category": proposal,
        "severity": str(analysis.get("proposed_severity", "High")),
        "action": str(analysis.get("proposed_action", UNCERTAIN_ACTION)),
        "confidence": min(0.98, max(confidence, float(analysis.get("confidence", 0.0)))),
        "human_review_required": True, "decision_applied": True,
        "fusion_status": str(analysis.get("fusion_status")),
    })
    if proposal == PRIVACY_CATEGORY:
        updated["reason"] = (
            "Local evidence found a non-consensual capture, surveillance, tracking, "
            "eavesdropping, or private-media sharing act in a privacy-sensitive context."
        )
        updated["matched_signals"].append("invasion_of_privacy_v1_rc1:review_only")
    else:
        updated["reason"] = (
            "Consent, ownership, location, provenance, or evidence completeness is unresolved; "
            "no identity, consent, or private location was inferred from appearance."
        )
        updated["matched_signals"].append("invasion_of_privacy_v1_rc1:uncertain_review")
    return updated


def get_invasion_of_privacy_v1_rc1_status() -> dict[str, Any]:
    return {
        "version": "invasion-of-privacy-v1-rc1",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [PRIVACY_CATEGORY, UNCERTAIN_CATEGORY],
        "required_privacy_action": PRIVACY_ACTION,
        "human_review_required": True,
        "real_victim_media_stored": False, "private_identifiers_stored": False,
        "face_recognition_used": False,
        "appearance_based_consent_or_location_inference_allowed": False,
        "external_provider_used": False, "external_transmission_allowed": False,
        "automatic_enforcement_allowed": False,
    }
