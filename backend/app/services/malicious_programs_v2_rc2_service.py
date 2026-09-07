"""RC2 word-order recovery over the frozen non-executing RC1 policy."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.services.malicious_programs_v1_rc1_service import (
    MALICIOUS_ACTION,
    MALICIOUS_CATEGORY,
    UNCERTAIN_CATEGORY,
    analyze_malicious_programs_v1_rc1,
    apply_malicious_programs_v1_rc1_fusion,
)


POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "evidence"
    / "malicious_programs_v2_rc2_policy.json"
)
ACTION_PATTERN = re.compile(
    r"\b(?:distribut(?:e|es|ed|ing)|deliver(?:s|ed|ing)?|"
    r"deploy(?:s|ed|ing)?|install(?:s|ed|ing)?|"
    r"execut(?:e|es|ed|ing)|launch(?:es|ed|ing)?|"
    r"load(?:s|ed|ing)?|run(?:s|ning)?|sent|send(?:s|ing)?|"
    r"offer(?:s|ed|ing)?|publish(?:es|ed|ing)?|"
    r"upload(?:s|ed|ing)?|host(?:s|ed|ing)?)\b"
)


def _normalize(text: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", text).casefold().split()
    )


def _policy_available() -> bool:
    try:
        payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("component") == MALICIOUS_CATEGORY
        and payload.get("rc1_holdout_cases_or_predictions_used") is False
        and payload.get("code_execution_allowed") is False
        and payload.get("payload_storage_allowed") is False
    )


def analyze_malicious_programs_v2_rc2(
    text: str,
    input_sources: list[str],
) -> dict[str, Any]:
    """Apply bounded action/object recovery without inspecting any payload."""

    analysis = analyze_malicious_programs_v1_rc1(
        text,
        input_sources,
    )
    normalized = _normalize(text)
    broad_action = ACTION_PATTERN.search(normalized) is not None
    analysis.update(
        {
            "available": (
                bool(analysis.get("available"))
                and _policy_available()
            ),
            "version": "malicious-programs-v2-rc2",
            "broad_operational_action_signal": broad_action,
            "rc1_fusion_status": str(
                analysis.get("fusion_status", "")
            ),
            "rc1_aggregate_signal_used": True,
            "rc1_holdout_cases_read": False,
            "rc1_individual_predictions_read": False,
            "rc1_mismatches_read": False,
            "code_executed": False,
            "archive_unpacked": False,
            "payload_stored": False,
            "credentials_stored": False,
            "live_infrastructure_stored": False,
            "external_provider_used": False,
            "external_transmission_allowed": False,
            "automatic_enforcement_allowed": False,
        }
    )
    if not analysis["available"]:
        analysis["fusion_status"] = "rc2_policy_evidence_unavailable"
        analysis["proposed_category"] = ""
        return analysis
    if analysis.get("proposed_category"):
        return analysis
    if (
        analysis.get("defensive_context")
        or analysis.get("safe_reporting_context")
        or analysis.get("benign_software_context")
        or analysis.get("uncertainty_signal")
    ):
        return analysis
    if analysis.get("malicious_object_signal") and broad_action:
        analysis.update(
            {
                "fusion_status": (
                    "rc2_word_order_malicious_security_review_candidate"
                ),
                "proposed_category": MALICIOUS_CATEGORY,
                "proposed_action": MALICIOUS_ACTION,
                "proposed_severity": "Critical",
                "confidence": 0.93,
                "human_review_required": True,
            }
        )
    return analysis


def apply_malicious_programs_v2_rc2_fusion(
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
    decision = apply_malicious_programs_v1_rc1_fusion(
        category=category,
        severity=severity,
        action=action,
        confidence=confidence,
        human_review_required=human_review_required,
        reason=reason,
        matched_signals=matched_signals,
        analysis=analysis,
    )
    if (
        decision.get("decision_applied")
        and analysis.get("fusion_status")
        == "rc2_word_order_malicious_security_review_candidate"
    ):
        decision["reason"] = (
            "Local inert evidence found a malicious-program object and "
            "a bounded operational action in either word order. No "
            "file, archive, or code was opened or executed."
        )
        decision["matched_signals"] = [
            signal
            for signal in decision["matched_signals"]
            if signal
            != "malicious_programs_v1_rc1:security_review_only"
        ]
        decision["matched_signals"].append(
            "malicious_programs_v2_rc2:word_order_recovery"
        )
    return decision


def get_malicious_programs_v2_rc2_status() -> dict[str, Any]:
    return {
        "version": "malicious-programs-v2-rc2",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [MALICIOUS_CATEGORY, UNCERTAIN_CATEGORY],
        "required_malicious_action": MALICIOUS_ACTION,
        "human_review_required": True,
        "rc1_aggregate_signal_used": True,
        "rc1_holdout_cases_or_predictions_used": False,
        "code_execution_allowed": False,
        "archive_unpacking_allowed": False,
        "payload_storage_allowed": False,
        "credentials_storage_allowed": False,
        "live_infrastructure_storage_allowed": False,
        "external_provider_used": False,
        "external_transmission_allowed": False,
        "automatic_enforcement_allowed": False,
    }
