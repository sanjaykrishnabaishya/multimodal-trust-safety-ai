"""Readiness-gated live fusion for frozen Malicious Programs V2 RC2."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.malicious_programs_v2_rc2_service import (
    analyze_malicious_programs_v2_rc2,
    apply_malicious_programs_v2_rc2_fusion as apply_candidate,
)


BACKEND = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    BACKEND
    / "storage"
    / "candidates"
    / "malicious-programs-v2-rc2"
)
RC1_DIRECTORY = (
    BACKEND
    / "storage"
    / "candidates"
    / "malicious-programs-v1-rc1"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = (
    CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
)
LIVE_ARTIFACTS = {
    "source_snapshot/malicious_programs_v2_rc2_service.py": (
        BACKEND
        / "app"
        / "services"
        / "malicious_programs_v2_rc2_service.py"
    ),
    "policy_snapshot/malicious_programs_v2_rc2_policy.json": (
        BACKEND
        / "app"
        / "evidence"
        / "malicious_programs_v2_rc2_policy.json"
    ),
}
TEXT_SOURCES = {
    "text",
    "extracted_text",
    "ocr_text",
    "audio_transcript",
    "visual_description",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def get_malicious_programs_v2_rc2_readiness() -> dict[str, Any]:
    try:
        manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )
        verdict = json.loads(
            VERDICT_PATH.read_text(encoding="utf-8")
        )
        artifacts = {
            str(item["relative_path"]): str(item["sha256"])
            for item in manifest.get("artifacts", [])
        }
        live_hashes = all(
            live_path.is_file()
            and (CANDIDATE_DIRECTORY / relative_path).is_file()
            and artifacts.get(relative_path) == _sha256(live_path)
            and artifacts.get(relative_path)
            == _sha256(CANDIDATE_DIRECTORY / relative_path)
            for relative_path, live_path in LIVE_ARTIFACTS.items()
        )
        dependency = manifest["dependencies"][
            "malicious-programs-v1-rc1"
        ]
        rc1_live_service = (
            BACKEND
            / "app"
            / "services"
            / "malicious_programs_v1_rc1_service.py"
        )
        rc1_snapshot = (
            RC1_DIRECTORY
            / "source_snapshot"
            / "malicious_programs_v1_rc1_service.py"
        )
        dependency_hashes = all(
            (
                (
                    dependency["manifest_sha256"]
                    == _sha256(RC1_DIRECTORY / "manifest.json")
                ),
                (
                    dependency["verdict_sha256"]
                    == _sha256(
                        RC1_DIRECTORY
                        / "independent_evaluation_verdict.json"
                    )
                ),
                (
                    dependency["service_snapshot_sha256"]
                    == _sha256(rc1_snapshot)
                    == _sha256(rc1_live_service)
                ),
            )
        )
    except (
        OSError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        return {
            "ready": False,
            "reason": (
                "Candidate evidence unavailable: "
                f"{type(error).__name__}"
            ),
            "automatic_enforcement_allowed": False,
        }
    checks = {
        "candidate_identity": (
            manifest.get("candidate") == "malicious-programs-v2-rc2"
        ),
        "development_gate": (
            manifest.get("development_gate_passed") is True
        ),
        "independent_gate": (
            verdict.get(
                "passed_synthetic_independent_readiness_gate"
            )
            is True
        ),
        "guarded_integration_eligible": (
            verdict.get("eligible_for_guarded_live_integration")
            is True
        ),
        "frozen_live_hashes_verified": live_hashes,
        "frozen_dependency_hashes_verified": dependency_hashes,
        "automatic_enforcement_disabled": (
            manifest.get("automatic_enforcement_allowed") is False
            and verdict.get("automatic_enforcement_allowed") is False
        ),
        "non_execution_contract": (
            manifest.get("code_execution_allowed") is False
            and manifest.get("archive_unpacking_allowed") is False
            and verdict.get("code_executed") is False
            and verdict.get("archives_unpacked") is False
        ),
        "payload_storage_disabled": (
            manifest.get("payload_storage_allowed") is False
            and manifest.get("credentials_storage_allowed") is False
            and manifest.get("live_infrastructure_storage_allowed")
            is False
            and verdict.get("payloads_stored") is False
            and verdict.get("credentials_stored") is False
            and verdict.get("live_infrastructure_stored") is False
        ),
        "external_provider_disabled": (
            manifest.get("external_provider_used") is False
            and manifest.get("external_transmission_allowed") is False
            and verdict.get("external_provider_used") is False
        ),
        "earlier_holdout_not_used": (
            manifest.get("rc1_holdout_cases_or_predictions_used")
            is False
            and verdict.get("earlier_holdout_files_read") is False
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


def analyze_malicious_programs_v2_rc2_for_fusion(
    text: str,
    input_sources: list[str],
) -> dict[str, Any]:
    readiness = get_malicious_programs_v2_rc2_readiness()
    if not readiness.get("ready"):
        return {
            "available": False,
            "version": "malicious-programs-v2-rc2",
            "fusion_status": "candidate_not_ready",
            "proposed_category": "",
            "confidence": 0.0,
            "human_review_required": False,
            "code_executed": False,
            "archive_unpacked": False,
            "payload_stored": False,
            "external_provider_used": False,
            "automatic_enforcement_allowed": False,
            "readiness": readiness,
            "warnings": [],
        }
    if not TEXT_SOURCES.intersection(input_sources):
        return {
            "available": True,
            "version": "malicious-programs-v2-rc2",
            "fusion_status": "unsupported_input_no_override",
            "proposed_category": "",
            "confidence": 0.0,
            "human_review_required": False,
            "code_executed": False,
            "archive_unpacked": False,
            "payload_stored": False,
            "external_provider_used": False,
            "automatic_enforcement_allowed": False,
            "readiness": readiness,
            "warnings": [
                "Malicious-program evidence could not be evaluated from "
                "this inert input source."
            ],
        }
    analysis = analyze_malicious_programs_v2_rc2(
        text,
        input_sources,
    )
    analysis["readiness"] = readiness
    return analysis


def apply_malicious_programs_v2_rc2_guarded_fusion(
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
    if (
        not analysis.get("available")
        or not analysis.get("readiness", {}).get("ready")
    ):
        return {
            "category": category,
            "severity": severity,
            "action": action,
            "confidence": confidence,
            "human_review_required": human_review_required,
            "reason": reason,
            "matched_signals": list(matched_signals),
            "decision_applied": False,
            "fusion_status": str(
                analysis.get("fusion_status", "candidate_not_ready")
            ),
            "automatic_enforcement_allowed": False,
        }
    return apply_candidate(
        category=category,
        severity=severity,
        action=action,
        confidence=confidence,
        human_review_required=human_review_required,
        reason=reason,
        matched_signals=matched_signals,
        analysis=analysis,
    )
