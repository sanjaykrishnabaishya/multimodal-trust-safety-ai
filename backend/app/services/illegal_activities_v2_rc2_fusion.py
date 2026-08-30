"""Readiness-gated live fusion for frozen Illegal Activities V2 RC2."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.illegal_activities_v2_rc2_service import (
    analyze_illegal_activities_v2_rc2,
    apply_illegal_activities_v2_rc2_fusion as apply_candidate_fusion,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    BACKEND_ROOT / "storage" / "candidates" / "illegal-activities-v2-rc2"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
LIVE_HASH_PATHS = {
    "source_snapshot/illegal_activities_v2_rc2_service.py": (
        BACKEND_ROOT / "app" / "services" / "illegal_activities_v2_rc2_service.py"
    ),
    "source_snapshot/openrouter_advisory_service.py": (
        BACKEND_ROOT / "app" / "services" / "openrouter_advisory_service.py"
    ),
    "policy_snapshot/illegal_activities_v2_rc2_policy.json": (
        BACKEND_ROOT / "app" / "evidence" / "illegal_activities_v2_rc2_policy.json"
    ),
}
TEXTUAL_INPUT_SOURCES = {
    "text",
    "extracted_text",
    "ocr_text",
    "audio_transcript",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def get_illegal_activities_v2_rc2_readiness() -> dict[str, Any]:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
        artifacts = {
            str(item["relative_path"]): str(item["sha256"])
            for item in manifest.get("artifacts", [])
        }
        hashes_verified = all(
            path.is_file()
            and artifacts.get(relative_path) == _sha256(path)
            and (CANDIDATE_DIRECTORY / relative_path).is_file()
            and artifacts.get(relative_path)
            == _sha256(CANDIDATE_DIRECTORY / relative_path)
            for relative_path, path in LIVE_HASH_PATHS.items()
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        return {
            "ready": False,
            "reason": f"Candidate evidence unavailable: {type(error).__name__}",
            "automatic_enforcement_allowed": False,
        }

    checks = {
        "candidate_identity": manifest.get("candidate") == "illegal-activities-v2-rc2",
        "development_gate": manifest.get("development_gate_passed") is True,
        "independent_gate": verdict.get("passed_synthetic_independent_readiness_gate") is True,
        "guarded_integration_eligible": verdict.get("eligible_for_guarded_live_integration") is True,
        "frozen_live_hashes_verified": hashes_verified,
        "automatic_enforcement_disabled": (
            manifest.get("automatic_enforcement_allowed") is False
            and verdict.get("automatic_enforcement_allowed") is False
        ),
        "raw_holdout_not_stored": verdict.get("raw_challenge_text_stored") is False,
        "individual_predictions_not_stored": verdict.get("individual_predictions_stored") is False,
        "external_advisory_has_no_authority": (
            manifest.get("external_advisory_has_category_authority") is False
            and manifest.get("external_advisory_has_enforcement_authority") is False
        ),
    }
    ready = all(checks.values())
    return {
        "ready": ready,
        "checks": checks,
        "reason": (
            "Frozen RC2 passed its synthetic independent gate."
            if ready
            else "Frozen RC2 readiness contract is incomplete."
        ),
        "synthetic_evidence_only": True,
        "external_real_world_accuracy": False,
        "automatic_enforcement_allowed": False,
    }


def analyze_illegal_activities_v2_rc2_for_fusion(
    text: str,
    input_sources: list[str],
) -> dict[str, Any]:
    readiness = get_illegal_activities_v2_rc2_readiness()
    if not readiness.get("ready"):
        return {
            "available": False,
            "version": "illegal-activities-v2-rc2",
            "fusion_status": "candidate_not_ready",
            "proposed_category": "",
            "confidence": 0.0,
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "openrouter": {"used": False, "status": "candidate_not_ready"},
            "readiness": readiness,
            "warnings": [],
        }
    if not TEXTUAL_INPUT_SOURCES.intersection(input_sources):
        return {
            "available": True,
            "version": "illegal-activities-v2-rc2",
            "fusion_status": "non_textual_input_no_override",
            "proposed_category": "",
            "confidence": 0.0,
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "openrouter": {"used": False, "status": "non_textual_input"},
            "readiness": readiness,
            "warnings": [],
        }
    analysis = analyze_illegal_activities_v2_rc2(
        text,
        input_sources,
        use_openrouter=input_sources == ["text"],
    )
    analysis["readiness"] = readiness
    return analysis


def apply_illegal_activities_v2_rc2_guarded_fusion(
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
    if not analysis.get("available") or not analysis.get("readiness", {}).get("ready"):
        return {
            "category": category,
            "severity": severity,
            "action": action,
            "confidence": confidence,
            "human_review_required": human_review_required,
            "reason": reason,
            "matched_signals": list(matched_signals),
            "decision_applied": False,
            "fusion_status": str(analysis.get("fusion_status", "candidate_not_ready")),
            "automatic_enforcement_allowed": False,
        }
    return apply_candidate_fusion(
        category=category,
        severity=severity,
        action=action,
        confidence=confidence,
        human_review_required=human_review_required,
        reason=reason,
        matched_signals=matched_signals,
        analysis=analysis,
    )
