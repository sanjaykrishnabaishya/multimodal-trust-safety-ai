from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.captionless_visual_evidence_v7_service import (
    CLIP_MODEL_ID,
    CLIP_MODEL_REVISION,
    FREEPIK_MODEL_ID,
    FREEPIK_MODEL_REVISION,
    VisualEvidenceV7Config,
    model_licence_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "captionless-visual-evidence-v7-rc1"
CANDIDATE_PARENT = BACKEND / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE
SERVICE_PATH = (
    BACKEND / "app" / "services" / "captionless_visual_evidence_v7_service.py"
)
EVALUATOR_PATH = (
    BACKEND / "scripts" / "evaluate_captionless_visual_evidence_v7_development.py"
)
FREEZE_PATH = Path(__file__).resolve()
SEED_MANIFEST_PATH = (
    ROOT
    / "datasets"
    / "development"
    / "captionless_visual_boundary_v6"
    / "seed_manifest.json"
)
DEVELOPMENT_REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_evidence_v7_development_v2"
    / "report.json"
)
EXPECTED_SEED_CONTENT_HASH = (
    "fd844632a0e7edd5158d10d502e1aee187f75de7c98852f17aa7b86e2ba509dc"
)
FORBIDDEN_PRE_FREEZE_PATHS = (
    ROOT
    / "datasets"
    / "evaluation"
    / "captionless_visual_evidence_v7_rc1_independent",
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_evidence_v7_rc1_independent",
)

INDEPENDENT_GATE = {
    "minimum_records": 60,
    "minimum_records_per_boundary": 20,
    "minimum_exact_accuracy": 0.90,
    "minimum_macro_f1": 0.88,
    "minimum_explicit_precision": 0.95,
    "minimum_explicit_recall": 0.90,
    "minimum_non_explicit_intimacy_precision": 0.85,
    "minimum_non_explicit_intimacy_recall": 0.85,
    "minimum_art_culture_precision": 0.95,
    "minimum_art_culture_recall": 0.90,
    "minimum_group_accuracy": 0.85,
    "maximum_processing_errors": 0,
    "maximum_unsafe_authority_failures": 0,
    "require_zero_development_content_overlap": True,
    "require_frozen_source_hashes": True,
    "require_pinned_model_revisions": True,
    "require_cached_model_weight_hashes": True,
    "require_no_raw_media_storage": True,
    "require_no_embedding_storage": True,
    "require_no_free_form_model_output": True,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required freeze input is missing: {path}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def copy_artifact(
    source: Path, destination: Path, relative_path: str
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "relative_path": relative_path,
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def model_cache_directory(model_id: str) -> Path:
    folder = "models--" + model_id.replace("/", "--")
    return Path.home() / ".cache" / "huggingface" / "hub" / folder


def resolve_cached_safetensors(model_id: str, revision: str) -> Path:
    snapshot = model_cache_directory(model_id) / "snapshots" / revision
    direct = snapshot / "model.safetensors"
    if direct.is_file():
        return direct
    if snapshot.is_dir():
        candidates = sorted(snapshot.rglob("*.safetensors"))
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            named = [path for path in candidates if path.name == "model.safetensors"]
            if len(named) == 1:
                return named[0]
    raise FileNotFoundError(
        f"Pinned Safetensors weights are not cached for {model_id}@{revision}. "
        "Run the V7 V2 development evaluator first."
    )


def validate_development_evidence() -> tuple[dict[str, Any], dict[str, Any]]:
    report = read_json(DEVELOPMENT_REPORT_PATH)
    seed_manifest = read_json(SEED_MANIFEST_PATH)
    failures: list[str] = []
    if report.get("candidate") != "captionless-visual-evidence-v7-development-v2":
        failures.append("Unexpected development candidate identifier.")
    if report.get("passed_development_gate") is not True:
        failures.append("The V7 V2 development gate did not pass.")
    if int(report.get("records", 0)) != 8:
        failures.append("The locked development report must contain eight records.")
    if float(report.get("accuracy_percent", 0.0)) != 100.0:
        failures.append("Development accuracy is not 100%.")
    if float(report.get("minimum_group_accuracy_percent", 0.0)) != 100.0:
        failures.append("Minimum development group accuracy is not 100%.")
    for key in ("processing_errors", "unsafe_authority_failures"):
        if int(report.get(key, -1)) != 0:
            failures.append(f"Development contract is nonzero: {key}")
    required_false = (
        "user_media_used_for_training",
        "raw_media_stored",
        "embeddings_stored",
        "local_llm_used",
        "moderation_actions_emitted",
        "independently_validated",
        "automatic_enforcement_allowed",
        "connected_to_live_moderation",
        "training_data_provenance_complete",
        "legal_approval_claimed",
        "production_eligible",
    )
    for key in required_false:
        if report.get(key) is not False:
            failures.append(f"Unsafe or unexpected development contract: {key}")
    reported_revisions = report.get("resolved_model_revisions", {})
    required_revisions = {
        FREEPIK_MODEL_ID: FREEPIK_MODEL_REVISION,
        CLIP_MODEL_ID: CLIP_MODEL_REVISION,
    }
    if reported_revisions != required_revisions:
        failures.append("Resolved model revisions do not match the locked revisions.")
    licence = report.get("model_licence_manifest", {})
    if licence != model_licence_manifest():
        failures.append("The recorded model licence manifest changed.")
    if seed_manifest.get("content_hash_sha256") != EXPECTED_SEED_CONTENT_HASH:
        failures.append("The V6 seed content hash changed.")
    if seed_manifest.get("record_count") != 8:
        failures.append("The V6 seed manifest record count changed.")
    for key in ("training_allowed", "raw_media_copied", "redistribution_allowed"):
        if seed_manifest.get(key) is not False:
            failures.append(f"Unsafe seed-manifest contract: {key}")
    if failures:
        raise RuntimeError(
            "Captionless Visual Evidence V7 RC1 freeze validation failed:\n- "
            + "\n- ".join(failures)
        )
    return report, seed_manifest


def main() -> None:
    for path in (
        SERVICE_PATH,
        EVALUATOR_PATH,
        FREEZE_PATH,
        SEED_MANIFEST_PATH,
        DEVELOPMENT_REPORT_PATH,
    ):
        require_file(path)
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "A frozen Captionless Visual Evidence V7 RC1 candidate already "
            f"exists and will not be overwritten: {CANDIDATE_DIRECTORY}"
        )
    preexisting = [str(path) for path in FORBIDDEN_PRE_FREEZE_PATHS if path.exists()]
    if preexisting:
        raise RuntimeError(
            "Independent material exists before freeze:\n- "
            + "\n- ".join(preexisting)
        )

    report, seed_manifest = validate_development_evidence()
    cached_models: list[dict[str, Any]] = []
    for model_id, revision in (
        (FREEPIK_MODEL_ID, FREEPIK_MODEL_REVISION),
        (CLIP_MODEL_ID, CLIP_MODEL_REVISION),
    ):
        weights = resolve_cached_safetensors(model_id, revision)
        cached_models.append(
            {
                "model_id": model_id,
                "revision": revision,
                "weights_filename": weights.name,
                "weights_size_bytes": weights.stat().st_size,
                "weights_sha256": sha256_file(weights),
                "weights_copied_into_candidate": False,
                "cache_location_stored_in_manifest": False,
            }
        )

    config = VisualEvidenceV7Config()
    locked_configuration = {
        name: getattr(config, name)
        for name in config.__dataclass_fields__
    }
    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="captionless-visual-evidence-v7-rc1-freeze-",
        dir=CANDIDATE_PARENT,
    ) as temporary_name:
        temporary = Path(temporary_name)
        artifacts = [
            copy_artifact(
                SERVICE_PATH,
                temporary / "source_snapshot" / SERVICE_PATH.name,
                f"source_snapshot/{SERVICE_PATH.name}",
            ),
            copy_artifact(
                EVALUATOR_PATH,
                temporary / "source_snapshot" / EVALUATOR_PATH.name,
                f"source_snapshot/{EVALUATOR_PATH.name}",
            ),
            copy_artifact(
                FREEZE_PATH,
                temporary / "source_snapshot" / FREEZE_PATH.name,
                f"source_snapshot/{FREEZE_PATH.name}",
            ),
            copy_artifact(
                SEED_MANIFEST_PATH,
                temporary / "development_evidence" / "seed_manifest.json",
                "development_evidence/seed_manifest.json",
            ),
            copy_artifact(
                DEVELOPMENT_REPORT_PATH,
                temporary / "development_evidence" / "report.json",
                "development_evidence/report.json",
            ),
        ]
        manifest = {
            "candidate": CANDIDATE,
            "component": "Captionless visual sexual-content evidence",
            "candidate_type": "evaluation-only fixed-model evidence generator",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {
                "records": report["records"],
                "accuracy_percent": report["accuracy_percent"],
                "minimum_group_accuracy_percent": report[
                    "minimum_group_accuracy_percent"
                ],
                "abstentions": report["abstentions"],
                "processing_errors": report["processing_errors"],
                "unsafe_authority_failures": report[
                    "unsafe_authority_failures"
                ],
            },
            "development_seed_content_sha256": seed_manifest[
                "content_hash_sha256"
            ],
            "v1_numeric_scores_used_for_v2_calibration": True,
            "raw_media_read_for_v2_calibration": False,
            "locked_configuration": locked_configuration,
            "model_licence_manifest": model_licence_manifest(),
            "cached_model_weight_evidence": cached_models,
            "model_weights_copied_into_candidate": False,
            "training_data_imported": False,
            "user_media_used_for_training": False,
            "raw_media_stored": False,
            "embeddings_stored": False,
            "free_form_model_output_used": False,
            "local_llm_used": False,
            "child_age_inference_enabled": False,
            "art_provenance_verification_enabled": False,
            "adult_age_verification_enabled": False,
            "moderation_action_authority_enabled": False,
            "automatic_allow_enabled": False,
            "automatic_enforcement_allowed": False,
            "training_data_provenance_complete": False,
            "legal_approval_claimed": False,
            "production_eligible": False,
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc1": False,
            "independent_pass_can_enable_live_integration": False,
            "independent_pass_can_enable_automatic_enforcement": False,
            "independently_validated": False,
            "eligible_for_guarded_policy_evaluation": False,
            "connected_to_live_moderation": False,
            "evaluation_reporting_contract": {
                "store_raw_holdout_media": False,
                "store_embeddings": False,
                "store_free_form_model_output": False,
                "store_individual_predictions": False,
                "print_individual_predictions": False,
                "report_aggregate_metrics_only": True,
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(CANDIDATE_DIRECTORY)

    print("CAPTIONLESS VISUAL EVIDENCE V7 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Pinned model revisions locked: True")
    print("Cached Safetensors weight hashes locked: True")
    print("Model weights copied into candidate: False")
    print("V1 numeric development scores used for V2 calibration: True")
    print("Raw media read for V2 calibration: False")
    print("User media used for training: False")
    print("Raw media or embeddings stored: False")
    print("Child or adult age verification enabled: False")
    print("Moderation action authority enabled: False")
    print("Training-data provenance complete: False")
    print("Legal approval claimed: False")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC1 is frozen for one evaluation-only independent challenge.")


if __name__ == "__main__":
    main()
