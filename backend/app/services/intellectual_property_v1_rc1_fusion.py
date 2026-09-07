"""Readiness-gated live fusion for frozen Intellectual Property V1 RC1."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.intellectual_property_v1_rc1_service import (
    analyze_intellectual_property_v1_rc1,
    apply_intellectual_property_v1_rc1_fusion as apply_candidate,
)

BACKEND = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = BACKEND / "storage" / "candidates" / "intellectual-property-v1-rc1"
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
LIVE_ARTIFACTS = {
    "source_snapshot/intellectual_property_v1_rc1_service.py": BACKEND / "app" / "services" / "intellectual_property_v1_rc1_service.py",
    "policy_snapshot/intellectual_property_v1_rc1_policy.json": BACKEND / "app" / "evidence" / "intellectual_property_v1_rc1_policy.json",
}
TEXT_SOURCES = {"text", "extracted_text", "ocr_text", "audio_transcript", "visual_description"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def get_intellectual_property_v1_rc1_readiness() -> dict[str, Any]:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
        artifacts = {str(item["relative_path"]): str(item["sha256"])
                     for item in manifest["artifacts"]}
        hashes_verified = all(
            live_path.is_file() and (CANDIDATE_DIRECTORY / relative).is_file()
            and artifacts.get(relative) == _sha256(live_path)
            and artifacts.get(relative) == _sha256(CANDIDATE_DIRECTORY / relative)
            for relative, live_path in LIVE_ARTIFACTS.items()
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {
            "ready": False,
            "reason": f"Candidate evidence unavailable: {type(error).__name__}",
            "automatic_enforcement_allowed": False,
        }
    checks = {
        "candidate_identity": manifest.get("candidate") == "intellectual-property-v1-rc1",
        "development_gate": manifest.get("development_gate_passed") is True,
        "independent_gate": verdict.get("passed_synthetic_independent_readiness_gate") is True,
        "guarded_integration_eligible": verdict.get("eligible_for_guarded_live_integration") is True,
        "frozen_live_hashes_verified": hashes_verified,
        "automatic_enforcement_disabled": (
            manifest.get("automatic_enforcement_allowed") is False
            and verdict.get("automatic_enforcement_allowed") is False),
        "automatic_takedown_disabled": (
            manifest.get("automatic_takedown_allowed") is False
            and verdict.get("automatic_takedown_allowed") is False),
        "raw_material_not_stored": (
            manifest.get("raw_copyrighted_works_used") is False
            and manifest.get("pirated_material_used") is False
            and verdict.get("raw_challenge_text_stored") is False),
        "private_claimant_data_not_used": (
            manifest.get("private_claimant_data_used") is False
            and verdict.get("private_claimant_data_used") is False),
        "external_provider_disabled": (
            manifest.get("external_provider_used") is False
            and manifest.get("external_transmission_allowed") is False
            and verdict.get("external_provider_used") is False),
        "legal_authority_disabled": (
            manifest.get("ownership_or_licence_inference_allowed") is False
            and manifest.get("legal_determination_allowed") is False),
    }
    ready = all(checks.values())
    return {
        "ready": ready, "checks": checks,
        "reason": ("Frozen RC1 passed its synthetic independent gate."
                   if ready else "Frozen RC1 readiness contract is incomplete."),
        "synthetic_evidence_only": True, "external_real_world_accuracy": False,
        "automatic_takedown_allowed": False, "automatic_enforcement_allowed": False,
    }


def analyze_intellectual_property_v1_rc1_for_fusion(
    text: str, input_sources: list[str],
) -> dict[str, Any]:
    readiness = get_intellectual_property_v1_rc1_readiness()
    if not readiness.get("ready"):
        return {
            "available": False, "version": "intellectual-property-v1-rc1",
            "fusion_status": "candidate_not_ready", "proposed_category": "",
            "confidence": 0.0, "human_review_required": False,
            "raw_copyrighted_works_stored": False, "external_provider_used": False,
            "automatic_takedown_allowed": False, "automatic_enforcement_allowed": False,
            "readiness": readiness, "warnings": [],
        }
    if not TEXT_SOURCES.intersection(input_sources):
        return {
            "available": True, "version": "intellectual-property-v1-rc1",
            "fusion_status": "unsupported_input_no_override", "proposed_category": "",
            "confidence": 0.0, "human_review_required": False,
            "raw_copyrighted_works_stored": False, "external_provider_used": False,
            "automatic_takedown_allowed": False, "automatic_enforcement_allowed": False,
            "readiness": readiness,
            "warnings": ["Intellectual-property evidence could not be evaluated from this input source."],
        }
    analysis = analyze_intellectual_property_v1_rc1(text, input_sources)
    analysis["readiness"] = readiness
    return analysis


def apply_intellectual_property_v1_rc1_guarded_fusion(
    *, category: str, severity: str, action: str, confidence: float,
    human_review_required: bool, reason: str, matched_signals: list[str],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    if not analysis.get("available") or not analysis.get("readiness", {}).get("ready"):
        return {
            "category": category, "severity": severity, "action": action,
            "confidence": confidence, "human_review_required": human_review_required,
            "reason": reason, "matched_signals": list(matched_signals),
            "decision_applied": False,
            "fusion_status": str(analysis.get("fusion_status", "candidate_not_ready")),
            "automatic_enforcement_allowed": False,
        }
    return apply_candidate(
        category=category, severity=severity, action=action, confidence=confidence,
        human_review_required=human_review_required, reason=reason,
        matched_signals=matched_signals, analysis=analysis,
    )
