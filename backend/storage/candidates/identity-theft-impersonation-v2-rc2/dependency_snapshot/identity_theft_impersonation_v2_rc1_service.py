"""Local, review-only Identity Theft & Impersonation V2 RC1 router."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any


IDENTITY_CATEGORY = "Identity Theft & Impersonation"
NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
IDENTITY_ACTION = "Restrict account activity and send for identity review"
UNCERTAIN_ACTION = "Refer to human review"
POLICY_PATH = Path(__file__).resolve().parents[1] / "evidence" / "identity_theft_impersonation_v2_rc1_policy.json"

IDENTITY_OBJECT_TERMS = (
    "another person's identity", "someone else's identity", "victim's identity",
    "personal information", "financial information", "identity documents",
    "government id", "tax identity", "medical identity", "account credentials",
    "login credentials", "stolen credentials", "social media account",
    "online account", "customer account", "business identity", "official account",
    "personal profile", "profile photograph", "name and photograph",
)
UNAUTHORIZED_TERMS = (
    "without permission", "without consent", "without authorization",
    "not authorized", "owner did not authorize", "account holder did not approve",
    "stolen identity", "stolen credentials", "stolen identity documents",
    "fraudulently", "falsely", "deceptively", "against the victim's wishes",
)
IMPERSONATION_TERMS = (
    "impersonating another person", "impersonating the victim", "pretending to be another person",
    "posing as the victim", "posing as another person", "cloned the victim's profile",
    "cloned social media account", "duplicate profile pretending to be",
    "fake profile pretending to be", "falsely posing as a government officer",
    "falsely posing as a business representative", "falsely claims affiliation with",
    "deceptively claims to represent", "pretends to be official support",
)
MISUSE_ACT_TERMS = (
    "opens a new account", "opened a new account", "makes purchases", "made purchases",
    "applies for a loan", "applied for a loan", "files a tax return", "filed a tax return",
    "claims benefits", "claimed benefits", "obtains medical care", "obtained medical care",
    "gets a job", "got a job", "accesses the account", "accessed the account",
    "changes the account email", "changed the account email", "takes over the account",
    "took over the account", "sends messages to contacts", "sent messages to contacts",
    "solicits customers", "solicited customers", "collects payments", "collected payments",
    "requests account access", "requested account access", "contacts the victim's friends",
    "contacted the victim's friends", "publishes posts as the victim", "published posts as the victim",
)
ACTIVE_CASE_TERMS = (
    "this account", "this profile", "this user", "this message", "this caller",
    "this listing", "this applicant", "this transaction", "evidence indicates",
    "verified victim report", "documented account record", "current account",
    "currently", "victim reports", "account provider confirms",
)
AUTHORIZED_TERMS = (
    "documented authorization", "written authorization", "owner-approved representative",
    "account holder approved", "authorized agent", "authorized representative",
    "platform-verified official account", "verified through the platform",
    "identity proofing completed", "consent is documented", "official organization account",
)
SAFE_CONTEXT_TERMS = (
    "identity theft awareness", "impersonation awareness", "fraud prevention",
    "security training", "news report", "documentary", "academic research",
    "historical account", "fictional story", "fictional scene", "role-play exercise",
    "victim recovery guide", "how to report identity theft", "consumer warning",
    "clearly labelled parody", "clearly labeled parody", "satire account",
    "unofficial fan page", "fan account",
)
EXPLICIT_SAFE_BOUNDARY_TERMS = (
    "contains no real credentials", "does not contact real victims",
    "does not claim official affiliation", "no transaction is attempted",
    "no active account is described", "clearly discloses it is unofficial",
    "links to the official reporting service", "fictional and not real",
)
UNCERTAINTY_TERMS = (
    "identity is unclear", "identity cannot be verified", "authorization is unclear",
    "authorization cannot be verified", "consent is unknown", "account ownership is disputed",
    "account provenance is unknown", "account authenticity is unclear",
    "deceptive intent is unclear", "intent cannot be established", "victim report is unverified",
    "relationship is unknown", "identity evidence is incomplete",
)
INCOMPLETE_EVIDENCE_TERMS = (
    "media could not be decoded", "unsupported media format", "metadata is incomplete",
    "only a profile photograph is available", "only a screenshot is available",
    "source account is unavailable", "evidence is incomplete",
)
WEAK_ONLY_TERMS = (
    "same name", "similar name", "same profile photograph", "similar profile photograph",
    "looks like", "sounds like", "resembles", "contains a company logo",
    "uses a brand name", "claims to be official", "self-reported identity",
    "unverified account badge", "similar username", "matching display name",
)
ORDINARY_BENIGN_TERMS = (
    "identity settings", "account profile settings", "digital identity guidelines",
    "authentication documentation", "password manager", "official staff directory",
    "company biography", "public speaker profile", "customer account settings",
)
ESTABLISHED_OWNERS = {
    "Religiously Offensive Content", "Hate Speech & Discrimination",
    "Terrorism & Extremism", "Violent Content", "Dangerous Content",
    "Graphic, Obscene & Sexual Content", "Sexual Harassment",
    "Cyberbullying & Harassment", "Publishing Private Information",
    "Illegal Activities", "Misinformation & Fake News", "Spam, Scam & Phishing",
    "Intellectual Property Infringement", "Malicious Programs", "Abusive Words",
    "Child Exploitation", "Invasion of Privacy",
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
    return payload.get("component") == IDENTITY_CATEGORY


def analyze_identity_theft_impersonation_v2_rc1(text: str, input_sources: list[str]) -> dict[str, Any]:
    normalized = _normalize(text)
    identity_object = _any(normalized, IDENTITY_OBJECT_TERMS)
    unauthorized = _any(normalized, UNAUTHORIZED_TERMS)
    impersonation = _any(normalized, IMPERSONATION_TERMS)
    misuse_act = _any(normalized, MISUSE_ACT_TERMS)
    active_case = _any(normalized, ACTIVE_CASE_TERMS)
    authorized = _any(normalized, AUTHORIZED_TERMS)
    safe_context = _any(normalized, SAFE_CONTEXT_TERMS)
    explicit_safe_boundary = _any(normalized, EXPLICIT_SAFE_BOUNDARY_TERMS)
    uncertainty = _any(normalized, UNCERTAINTY_TERMS)
    incomplete = _any(normalized, INCOMPLETE_EVIDENCE_TERMS)
    weak_only = _any(normalized, WEAK_ONLY_TERMS)
    benign = _any(normalized, ORDINARY_BENIGN_TERMS)
    plausible_identity_risk = (identity_object and (unauthorized or misuse_act)) or impersonation

    result: dict[str, Any] = {
        "available": _policy_available(),
        "version": "identity-theft-impersonation-v2-rc1",
        "fusion_status": "no_identity_boundary_override",
        "proposed_category": "", "proposed_action": "", "proposed_severity": "",
        "confidence": 0.0, "human_review_required": False,
        "identity_object_signal": identity_object, "unauthorized_signal": unauthorized,
        "impersonation_signal": impersonation, "misuse_act_signal": misuse_act,
        "active_case": active_case, "authorized_context": authorized,
        "safe_context": safe_context, "uncertainty_signal": uncertainty,
        "incomplete_evidence": incomplete, "weak_evidence_only": weak_only,
        "real_identity_documents_stored": False, "raw_credentials_stored": False,
        "complete_personal_identifiers_stored": False, "face_recognition_used": False,
        "voice_identity_matching_used": False, "biometric_embeddings_stored": False,
        "identity_inferred_from_appearance": False, "identity_verified": False,
        "authorization_verified": False, "deceptive_intent_determined": False,
        "external_provider_used": False, "external_transmission_allowed": False,
        "automatic_account_suspension_allowed": False,
        "automatic_enforcement_allowed": False, "warnings": [],
    }
    if not result["available"]:
        result["fusion_status"] = "policy_evidence_unavailable"
        return result
    if not normalized:
        result["fusion_status"] = "empty_input_no_override"
        return result
    if benign and not plausible_identity_risk:
        result["fusion_status"] = "ordinary_identity_context_no_override"
        return result
    if authorized and not unauthorized:
        result["fusion_status"] = "documented_authorization_no_override"
        return result
    if safe_context and explicit_safe_boundary and not misuse_act:
        result["fusion_status"] = "safe_reporting_parody_or_education_no_override"
        return result
    if weak_only and not misuse_act and not unauthorized:
        result["fusion_status"] = "weak_name_face_logo_or_claim_no_override"
        return result
    if plausible_identity_risk and (uncertainty or incomplete or (authorized and unauthorized)):
        result.update({
            "fusion_status": "identity_authorization_or_evidence_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY, "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High", "confidence": 0.76,
            "human_review_required": True,
        })
        return result
    if identity_object and unauthorized and misuse_act and active_case:
        result.update({
            "fusion_status": "identity_theft_review_candidate",
            "proposed_category": IDENTITY_CATEGORY, "proposed_action": IDENTITY_ACTION,
            "proposed_severity": "High", "confidence": 0.95,
            "human_review_required": True,
        })
        return result
    if impersonation and misuse_act and active_case:
        result.update({
            "fusion_status": "deceptive_impersonation_review_candidate",
            "proposed_category": IDENTITY_CATEGORY, "proposed_action": IDENTITY_ACTION,
            "proposed_severity": "High", "confidence": 0.94,
            "human_review_required": True,
        })
        return result
    if plausible_identity_risk and active_case:
        result.update({
            "fusion_status": "possible_identity_misuse_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY, "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High", "confidence": 0.68,
            "human_review_required": True,
        })
    return result


def apply_identity_theft_impersonation_v2_rc1_fusion(
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
    if category == IDENTITY_CATEGORY:
        updated["fusion_status"] = "identity_owner_already_applied"
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
    if proposal == IDENTITY_CATEGORY:
        updated["reason"] = (
            "Local evidence pairs unauthorized identity use or deceptive impersonation "
            "with a current account, access, transaction, communication, or victim-impact act. "
            "An identity reviewer must verify identity, authorization, and intent."
        )
        updated["matched_signals"].append("identity_theft_impersonation_v2_rc1:review_only")
    else:
        updated["reason"] = (
            "Identity, authorization, consent, account provenance, authenticity, intent, or "
            "evidence completeness is unresolved; no identity was inferred from appearance."
        )
        updated["matched_signals"].append("identity_theft_impersonation_v2_rc1:uncertain_review")
    return updated


def get_identity_theft_impersonation_v2_rc1_status() -> dict[str, Any]:
    return {
        "version": "identity-theft-impersonation-v2-rc1",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [IDENTITY_CATEGORY, UNCERTAIN_CATEGORY],
        "required_identity_action": IDENTITY_ACTION, "human_review_required": True,
        "real_identity_documents_stored": False, "raw_credentials_stored": False,
        "complete_personal_identifiers_stored": False,
        "face_or_voice_recognition_allowed": False, "biometric_embeddings_allowed": False,
        "appearance_based_identity_inference_allowed": False,
        "external_provider_used": False, "external_transmission_allowed": False,
        "automatic_account_suspension_allowed": False,
        "automatic_enforcement_allowed": False,
    }
