"""Non-executing Malicious Programs V1 RC1 policy specialist."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any


MALICIOUS_CATEGORY = "Malicious Programs"
NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
MALICIOUS_ACTION = "Block and send for security review"
UNCERTAIN_ACTION = "Refer to human review"
POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "evidence"
    / "malicious_programs_v1_rc1_policy.json"
)

MALICIOUS_OBJECT_TERMS = (
    "malware",
    "ransomware",
    "computer virus",
    "trojan program",
    "remote access trojan",
    "spyware",
    "keylogger",
    "credential-stealing program",
    "credential stealer",
    "information stealer",
    "malicious payload",
    "botnet agent",
    "rootkit",
    "destructive wiper",
    "malicious backdoor",
)
SUSPICIOUS_ARTIFACT_TERMS = (
    "unknown executable attachment",
    "suspicious executable attachment",
    "unverified binary attachment",
    "password-protected archive",
    "encrypted archive attachment",
    "obfuscated script attachment",
    "untrusted macro-enabled document",
)
OPERATIONAL_INTENT_TERMS = (
    "distributes the",
    "offers the program for download",
    "provides access to the",
    "sends the binary",
    "installs the",
    "deploys the",
    "launches the",
    "executes the",
    "runs the payload",
    "loads the program on victim devices",
    "promotes installation of the",
    "delivers the program to targets",
)
HARMFUL_CAPABILITY_TERMS = (
    "steals login credentials",
    "captures passwords",
    "encrypts files for ransom",
    "destroys stored files",
    "wipes device data",
    "disables security tools",
    "evades endpoint detection",
    "persists after restart",
    "exfiltrates private data",
    "opens unauthorized remote control",
    "joins devices to a botnet",
    "contacts command-and-control infrastructure",
    "compromises user accounts",
)
ACTIVE_CASE_TERMS = (
    "this upload",
    "this attachment",
    "this account",
    "this post",
    "this download",
    "currently distributes",
    "currently deploys",
    "currently installs",
    "evidence indicates",
    "the incident contains",
)
DEFENSIVE_CONTEXT_TERMS = (
    "defensive malware analysis",
    "incident response report",
    "security awareness training",
    "malware prevention guide",
    "authorized security research",
    "authorized penetration test",
    "academic cybersecurity course",
    "sandbox analysis report",
    "threat intelligence summary",
    "detection engineering",
    "forensic investigation",
    "security patch validation",
)
SAFE_BOUNDARY_TERMS = (
    "contains no executable payload",
    "contains no downloadable program",
    "does not provide operational access",
    "indicators are redacted",
    "credentials are synthetic",
    "infrastructure addresses are redacted",
    "uses an inert text-only example",
    "describes prevention only",
    "no live target is involved",
)
BENIGN_SOFTWARE_TERMS = (
    "legitimate remote administration tool",
    "approved backup encryption",
    "antivirus update",
    "operating system update",
    "package manager installation",
    "device management agent",
    "accessibility automation script",
    "ordinary browser extension",
    "software deployment by administrators",
    "test fixture with no executable content",
)
UNCERTAINTY_TERMS = (
    "purpose is unknown",
    "intent cannot be established",
    "capability is unclear",
    "attachment cannot be inspected safely",
    "archive contents are unavailable",
    "file type is unsupported",
    "provenance is unknown",
    "authorization cannot be verified",
    "the evidence is incomplete",
)
SAFE_REPORTING_TERMS = (
    "news report",
    "historical account",
    "fictional story",
    "policy discussion",
    "court report",
    "public safety warning",
)
ESTABLISHED_OWNERS = {
    "Religiously Offensive Content",
    "Hate Speech & Discrimination",
    "Terrorism & Extremism",
    "Violent Content",
    "Dangerous Content",
    "Graphic, Obscene & Sexual Content",
    "Sexual Harassment",
    "Cyberbullying & Harassment",
    "Invasion of Privacy",
    "Illegal Activities",
    "Publishing Private Information",
    "Identity Theft & Impersonation",
    "Misinformation & Fake News",
    "Spam, Scam & Phishing",
    "Intellectual Property Infringement",
    "Abusive Words",
    "Child Exploitation",
}


def _normalize(text: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", text).casefold().split()
    )


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _policy_available() -> bool:
    try:
        payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("component") == MALICIOUS_CATEGORY
        and payload.get("code_execution_allowed") is False
        and payload.get("payload_storage_allowed") is False
    )


def analyze_malicious_programs_v1_rc1(
    text: str,
    input_sources: list[str],
) -> dict[str, Any]:
    """Analyze inert text evidence without opening, executing, or unpacking files."""

    normalized = _normalize(text)
    malicious_object = _contains_any(
        normalized,
        MALICIOUS_OBJECT_TERMS,
    )
    suspicious_artifact = _contains_any(
        normalized,
        SUSPICIOUS_ARTIFACT_TERMS,
    )
    operational_intent = _contains_any(
        normalized,
        OPERATIONAL_INTENT_TERMS,
    )
    harmful_capability = _contains_any(
        normalized,
        HARMFUL_CAPABILITY_TERMS,
    )
    active_case = _contains_any(normalized, ACTIVE_CASE_TERMS)
    defensive_context = _contains_any(
        normalized,
        DEFENSIVE_CONTEXT_TERMS,
    )
    safe_boundary = _contains_any(
        normalized,
        SAFE_BOUNDARY_TERMS,
    )
    benign_software = _contains_any(
        normalized,
        BENIGN_SOFTWARE_TERMS,
    )
    uncertainty = _contains_any(normalized, UNCERTAINTY_TERMS)
    safe_reporting = _contains_any(
        normalized,
        SAFE_REPORTING_TERMS,
    )

    result: dict[str, Any] = {
        "available": _policy_available(),
        "version": "malicious-programs-v1-rc1",
        "fusion_status": "no_malicious_program_boundary_override",
        "proposed_category": "",
        "proposed_action": "",
        "proposed_severity": "",
        "confidence": 0.0,
        "human_review_required": False,
        "malicious_object_signal": malicious_object,
        "suspicious_artifact_signal": suspicious_artifact,
        "operational_intent_signal": operational_intent,
        "harmful_capability_signal": harmful_capability,
        "active_case_signal": active_case,
        "defensive_context": defensive_context,
        "safe_boundary": safe_boundary,
        "benign_software_context": benign_software,
        "uncertainty_signal": uncertainty,
        "safe_reporting_context": safe_reporting,
        "input_sources": list(input_sources),
        "code_executed": False,
        "archive_unpacked": False,
        "payload_stored": False,
        "credentials_stored": False,
        "live_infrastructure_stored": False,
        "external_provider_used": False,
        "external_transmission_allowed": False,
        "automatic_enforcement_allowed": False,
        "warnings": [],
    }
    if not result["available"]:
        result["fusion_status"] = "policy_evidence_unavailable"
        return result
    if not normalized:
        result["fusion_status"] = "empty_input_no_override"
        return result
    if benign_software and not operational_intent and not harmful_capability:
        result["fusion_status"] = "benign_software_context_no_override"
        return result
    if defensive_context and safe_boundary and not operational_intent:
        result["fusion_status"] = "defensive_security_context_no_override"
        return result
    if safe_reporting and safe_boundary and not active_case:
        result["fusion_status"] = "safe_reporting_context_no_override"
        return result
    if uncertainty and (malicious_object or suspicious_artifact):
        result.update(
            {
                "fusion_status": "malicious_capability_uncertain_review",
                "proposed_category": UNCERTAIN_CATEGORY,
                "proposed_action": UNCERTAIN_ACTION,
                "proposed_severity": "High",
                "confidence": 0.76,
                "human_review_required": True,
            }
        )
        return result
    if malicious_object and (
        operational_intent
        or (harmful_capability and active_case)
    ):
        result.update(
            {
                "fusion_status": "malicious_program_security_review_candidate",
                "proposed_category": MALICIOUS_CATEGORY,
                "proposed_action": MALICIOUS_ACTION,
                "proposed_severity": "Critical",
                "confidence": 0.95,
                "human_review_required": True,
            }
        )
        return result
    if suspicious_artifact and active_case:
        result.update(
            {
                "fusion_status": "suspicious_artifact_uncertain_review",
                "proposed_category": UNCERTAIN_CATEGORY,
                "proposed_action": UNCERTAIN_ACTION,
                "proposed_severity": "High",
                "confidence": 0.72,
                "human_review_required": True,
            }
        )
    return result


def apply_malicious_programs_v1_rc1_fusion(
    *,
    category: str,
    severity: str,
    action: str,
    confidence: float,
    human_review_required: bool,
    reason: str,
    matched_signals: list[str],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    updated = {
        "category": category,
        "severity": severity,
        "action": action,
        "confidence": confidence,
        "human_review_required": human_review_required,
        "reason": reason,
        "matched_signals": list(matched_signals),
        "decision_applied": False,
        "fusion_status": str(
            analysis.get("fusion_status", "unavailable")
        ),
        "automatic_enforcement_allowed": False,
    }
    proposal = str(analysis.get("proposed_category", ""))
    if not proposal:
        return updated
    if category == MALICIOUS_CATEGORY:
        updated["fusion_status"] = "malicious_program_owner_already_applied"
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

    updated.update(
        {
            "category": proposal,
            "severity": str(
                analysis.get("proposed_severity", "High")
            ),
            "action": str(
                analysis.get("proposed_action", UNCERTAIN_ACTION)
            ),
            "confidence": min(
                0.98,
                max(
                    confidence,
                    float(analysis.get("confidence", 0.0)),
                ),
            ),
            "human_review_required": True,
            "decision_applied": True,
            "fusion_status": str(analysis.get("fusion_status")),
        }
    )
    if proposal == MALICIOUS_CATEGORY:
        updated["reason"] = (
            "Local inert evidence found a malicious-software signal "
            "paired with operational distribution, deployment, or "
            "harmful capability evidence. No code was executed."
        )
        updated["matched_signals"].append(
            "malicious_programs_v1_rc1:security_review_only"
        )
    else:
        updated["reason"] = (
            "The attachment, intent, provenance, or capability is "
            "unresolved. It was not executed or unpacked and requires "
            "specialist security review."
        )
        updated["matched_signals"].append(
            "malicious_programs_v1_rc1:uncertain_security_review"
        )
    return updated


def get_malicious_programs_v1_rc1_status() -> dict[str, Any]:
    return {
        "version": "malicious-programs-v1-rc1",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [MALICIOUS_CATEGORY, UNCERTAIN_CATEGORY],
        "required_malicious_action": MALICIOUS_ACTION,
        "human_review_required": True,
        "code_execution_allowed": False,
        "archive_unpacking_allowed": False,
        "payload_storage_allowed": False,
        "credentials_storage_allowed": False,
        "live_infrastructure_storage_allowed": False,
        "external_provider_used": False,
        "external_transmission_allowed": False,
        "automatic_enforcement_allowed": False,
    }
