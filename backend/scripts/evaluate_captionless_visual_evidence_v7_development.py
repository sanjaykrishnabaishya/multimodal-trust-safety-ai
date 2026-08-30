from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.captionless_visual_evidence_v7_service import (
    CANDIDATE_LABELS,
    CaptionlessVisualEvidenceV7,
    model_licence_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
SEED_MANIFEST = (
    ROOT
    / "datasets"
    / "development"
    / "captionless_visual_boundary_v6"
    / "seed_manifest.json"
)
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_evidence_v7_development_v2"
    / "report.json"
)
DOWNLOADS = Path.home() / "Downloads"
EXPECTED_SEED_HASH = "fd844632a0e7edd5158d10d502e1aee187f75de7c98852f17aa7b86e2ba509dc"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def percentage(numerator: int, denominator: int) -> float:
    return 100.0 * numerator / denominator if denominator else 0.0


def validate_manifest() -> dict[str, Any]:
    if not SEED_MANIFEST.is_file():
        raise FileNotFoundError(
            "Run scripts.import_captionless_visual_boundary_v6_seeds first."
        )
    manifest = json.loads(SEED_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("content_hash_sha256") != EXPECTED_SEED_HASH:
        raise RuntimeError("The V6 seed manifest content hash does not match.")
    if manifest.get("record_count") != 8:
        raise RuntimeError("The V6 seed manifest must contain exactly eight records.")
    if manifest.get("training_allowed") is not False:
        raise RuntimeError("The seed manifest must remain evaluation-only.")
    return manifest


def main() -> None:
    manifest = validate_manifest()
    licence = model_licence_manifest()
    if licence["permission_request_required"]:
        raise RuntimeError("A selected model requires permission; evaluation stopped.")
    if not licence["all_declared_licenses_permissive"]:
        raise RuntimeError("A selected model lacks a permissive declared licence.")

    print("CAPTIONLESS VISUAL EVIDENCE V7 DEVELOPMENT V2")
    print("=" * 60)
    print("Loading two pinned, local visual models...")
    print("No raw media, embeddings, or free-form output will be stored.")
    print("The user-supplied files remain evaluation-only and are not training data.\n")

    analyzer = CaptionlessVisualEvidenceV7()
    evaluations: list[dict[str, Any]] = []
    processing_errors = 0
    for record in manifest["records"]:
        record_id = str(record["record_id"])
        expected = str(record["boundary"])
        path = DOWNLOADS / str(record["filename"])
        try:
            if not path.is_file():
                raise FileNotFoundError(f"Required evaluation seed is missing: {path}")
            if sha256_file(path) != record["content_sha256"]:
                raise RuntimeError("The evaluation seed hash changed after import.")
            result = analyzer.analyze_path(path)
            predicted = str(result["candidate_boundary"])
            correct = predicted == expected
            evaluations.append(
                {
                    "record_id": record_id,
                    "expected_boundary": expected,
                    "predicted_boundary": predicted,
                    "correct": correct,
                    "candidate_confidence": result["candidate_confidence"],
                    "reason": result["reason"],
                    "clip_group_scores": result["clip_group_scores"],
                    "nsfw_level_scores": result["nsfw_level_scores"],
                    "frame_consensus": result["frame_consensus"],
                    "frames_evaluated": result["frames_evaluated"],
                    "per_frame_label_counts": result[
                        "per_frame_label_counts"
                    ],
                    "sexual_risk_score": result["sexual_risk_score"],
                    "policy_revision": result["policy_revision"],
                    "moderation_action": result["moderation_action"],
                    "automatic_enforcement_allowed": result[
                        "automatic_enforcement_allowed"
                    ],
                }
            )
            print(
                f"{record_id}: {'PASS' if correct else 'FAIL'} | "
                f"expected: {expected} | predicted: {predicted} | "
                f"confidence: {result['candidate_confidence']:.4f}"
            )
        except Exception as exc:
            processing_errors += 1
            evaluations.append(
                {
                    "record_id": record_id,
                    "expected_boundary": expected,
                    "predicted_boundary": "processing_error",
                    "correct": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            print(f"{record_id}: ERROR | {type(exc).__name__}: {exc}")

    correct = sum(bool(item["correct"]) for item in evaluations)
    abstentions = sum(item["predicted_boundary"] == "uncertain" for item in evaluations)
    group_results: dict[str, dict[str, Any]] = {}
    for boundary in sorted({str(item["boundary"]) for item in manifest["records"]}):
        members = [
            item
            for item in evaluations
            if item["expected_boundary"] == boundary
        ]
        group_correct = sum(bool(item["correct"]) for item in members)
        group_results[boundary] = {
            "records": len(members),
            "correct": group_correct,
            "accuracy_percent": round(percentage(group_correct, len(members)), 2),
        }
    minimum_group_accuracy = min(
        (group["accuracy_percent"] for group in group_results.values()), default=0.0
    )
    unsafe_authority_failures = sum(
        1
        for item in evaluations
        if item.get("moderation_action") is not None
        or item.get("automatic_enforcement_allowed") is not False
    )
    # Eight user examples are a smoke-sized development set. A pass requires
    # strong agreement but is never called independent or production evidence.
    gate_checks = {
        "seed_manifest_locked": True,
        "overall_accuracy": correct >= 7,
        "minimum_group_accuracy": minimum_group_accuracy >= 66.67,
        "processing_contract": processing_errors == 0,
        "no_moderation_authority": unsafe_authority_failures == 0,
        "declared_licenses_permissive": licence[
            "all_declared_licenses_permissive"
        ],
        "permission_not_required": not licence["permission_request_required"],
        "raw_media_not_stored": True,
    }
    passed = all(gate_checks.values())
    report = {
        "candidate": "captionless-visual-evidence-v7-development-v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(evaluations),
        "correct": correct,
        "accuracy_percent": round(percentage(correct, len(evaluations)), 2),
        "abstentions": abstentions,
        "minimum_group_accuracy_percent": minimum_group_accuracy,
        "processing_errors": processing_errors,
        "unsafe_authority_failures": unsafe_authority_failures,
        "group_results": group_results,
        "gate_checks": gate_checks,
        "passed_development_gate": passed,
        "model_licence_manifest": licence,
        "resolved_model_revisions": dict(analyzer.resolved_revisions),
        "evaluations": evaluations,
        "seed_manifest_content_sha256": EXPECTED_SEED_HASH,
        "training_records": 0,
        "user_media_used_for_training": False,
        "raw_media_stored": False,
        "embeddings_stored": False,
        "local_llm_used": False,
        "moderation_actions_emitted": False,
        "independently_validated": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "training_data_provenance_complete": False,
        "legal_approval_claimed": False,
        "production_eligible": False,
        "v1_development_signal_used": (
            "explicit boundary undercalled because medium and high risk "
            "probabilities were not combined"
        ),
        "v1_numeric_scores_used_for_development": True,
        "raw_media_read_for_v2_calibration": False,
    }
    write_json(REPORT_PATH, report)

    print("\nCAPTIONLESS VISUAL EVIDENCE V7 DEVELOPMENT RESULTS V2")
    print("=" * 60)
    print(f"Records: {len(evaluations)}")
    print(f"Accuracy: {report['accuracy_percent']:.2f}%")
    print(f"Abstentions: {abstentions}")
    print(f"Minimum group accuracy: {minimum_group_accuracy:.2f}%")
    print(f"Processing errors: {processing_errors}")
    print(f"Unsafe authority failures: {unsafe_authority_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for boundary, group in group_results.items():
        print(
            f"{boundary}: {group['correct']}/{group['records']} "
            f"({group['accuracy_percent']:.2f}%)"
        )
    print(f"\nPassed development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print("Declared model licences: MIT and MIT")
    print("Permission or gated access required: False")
    print("Training-data provenance complete: False")
    print("User media used for training: False")
    print("Raw media or embeddings stored: False")
    print("Moderation actions emitted: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("V1 numeric development scores used for calibration: True")
    print("Raw media read for V2 calibration: False")
    print("This is eight-example visual execution evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
