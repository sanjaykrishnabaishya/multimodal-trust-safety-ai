from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE_DIRECTORY = (
    BACKEND
    / "storage"
    / "candidates"
    / "captionless-visual-evidence-v7-rc1"
)
CANDIDATE_MANIFEST = CANDIDATE_DIRECTORY / "manifest.json"
FROZEN_SERVICE = (
    CANDIDATE_DIRECTORY
    / "source_snapshot"
    / "captionless_visual_evidence_v7_service.py"
)
DEVELOPMENT_SEED_MANIFEST = (
    CANDIDATE_DIRECTORY / "development_evidence" / "seed_manifest.json"
)
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
EXPECTED_BOUNDARY = "explicit_adult_sexual_content"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_file(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise RuntimeError("Frozen artifact escapes the candidate directory.")
    return resolved


def verify_frozen_artifacts(candidate: dict[str, Any]) -> None:
    for artifact in candidate.get("artifacts", []):
        path = canonical_file(
            CANDIDATE_DIRECTORY / str(artifact["relative_path"]),
            CANDIDATE_DIRECTORY,
        )
        if not path.is_file():
            raise FileNotFoundError("A frozen candidate artifact is missing.")
        if path.stat().st_size != int(artifact["size_bytes"]):
            raise RuntimeError("A frozen candidate artifact size changed.")
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError("A frozen candidate artifact hash changed.")


def model_cache_directory(model_id: str) -> Path:
    return (
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / ("models--" + model_id.replace("/", "--"))
    )


def resolve_cached_safetensors(model_id: str, revision: str) -> Path:
    snapshot = model_cache_directory(model_id) / "snapshots" / revision
    direct = snapshot / "model.safetensors"
    if direct.is_file():
        return direct
    candidates = sorted(snapshot.rglob("*.safetensors")) if snapshot.is_dir() else []
    named = [path for path in candidates if path.name == "model.safetensors"]
    if len(named) == 1:
        return named[0]
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError("Pinned cached model weights are unavailable.")


def verify_model_weights(candidate: dict[str, Any]) -> None:
    for model in candidate.get("cached_model_weight_evidence", []):
        path = resolve_cached_safetensors(
            str(model["model_id"]), str(model["revision"])
        )
        if path.stat().st_size != int(model["weights_size_bytes"]):
            raise RuntimeError("Cached model weight size changed.")
        if sha256_file(path) != str(model["weights_sha256"]):
            raise RuntimeError("Cached model weight hash changed.")


def load_frozen_service() -> ModuleType:
    module_name = "frozen_captionless_visual_evidence_v7_rc1_private_diagnostic"
    spec = importlib.util.spec_from_file_location(module_name, FROZEN_SERVICE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the frozen service snapshot.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, action="append", required=True)
    args = parser.parse_args()

    for required in (
        CANDIDATE_MANIFEST,
        FROZEN_SERVICE,
        DEVELOPMENT_SEED_MANIFEST,
    ):
        if not required.is_file():
            raise FileNotFoundError("A required frozen diagnostic input is missing.")
    candidate = read_json(CANDIDATE_MANIFEST)
    seed = read_json(DEVELOPMENT_SEED_MANIFEST)
    if candidate.get("candidate") != "captionless-visual-evidence-v7-rc1":
        raise RuntimeError("Unexpected frozen candidate identifier.")
    verify_frozen_artifacts(candidate)
    verify_model_weights(candidate)

    paths = [path.expanduser().resolve() for path in args.path]
    if len(paths) != len(set(paths)):
        raise RuntimeError("Duplicate diagnostic paths are not allowed.")
    missing = sum(not path.is_file() for path in paths)
    if missing:
        raise FileNotFoundError("One or more private diagnostic files are missing.")
    development_hashes = {
        str(record["content_sha256"]).lower() for record in seed.get("records", [])
    }
    exact_development_overlap = sum(
        sha256_file(path) in development_hashes for path in paths
    )

    frozen = load_frozen_service()
    locked_config = frozen.VisualEvidenceV7Config(**candidate["locked_configuration"])
    analyzer = frozen.CaptionlessVisualEvidenceV7(
        config=locked_config,
        local_files_only=True,
    )
    predicted_counts: Counter[str] = Counter()
    supported_records = 0
    unsupported_format_records = 0
    processing_errors = 0
    authority_failures = 0
    explicit_agreements = 0
    for path in paths:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            unsupported_format_records += 1
            continue
        supported_records += 1
        try:
            result = analyzer.analyze_path(path)
            predicted = str(result.get("candidate_boundary", "uncertain"))
            predicted_counts[predicted] += 1
            if predicted == EXPECTED_BOUNDARY:
                explicit_agreements += 1
            if result.get("moderation_action") is not None or result.get(
                "automatic_enforcement_allowed"
            ) is not False:
                authority_failures += 1
        except Exception:
            processing_errors += 1
            predicted_counts["processing_error"] += 1

    agreement = explicit_agreements / supported_records if supported_records else 0.0
    print("CAPTIONLESS VISUAL V7 RC1 PRIVATE USER-EXAMPLE DIAGNOSTIC")
    print("=" * 60)
    print(f"Candidate: {candidate['candidate']}")
    print(f"Files supplied: {len(paths)}")
    print(f"Supported-format records: {supported_records}")
    print(f"Unsupported-format records: {unsupported_format_records}")
    print(f"Processing errors: {processing_errors}")
    print(f"Exact development overlap: {exact_development_overlap}")
    print(f"User-labelled explicit agreement: {100 * agreement:.2f}%")
    print(f"Explicit predictions: {predicted_counts[EXPECTED_BOUNDARY]}")
    print(f"Uncertain predictions: {predicted_counts['uncertain']}")
    print(
        "Other-boundary predictions: "
        + str(
            sum(
                count
                for label, count in predicted_counts.items()
                if label
                not in {EXPECTED_BOUNDARY, "uncertain", "processing_error"}
            )
        )
    )
    print(f"Unsafe authority failures: {authority_failures}")
    print("Raw media copied or stored: False")
    print("Embeddings or individual predictions stored: False")
    print("Individual filenames or scores printed: False")
    print("Training or calibration allowed: False")
    print("Independent holdout membership allowed: False")
    print("Frozen RC1 modified: False")
    print("Automatic enforcement allowed: False")
    print("This is private diagnostic agreement, not accuracy evidence.")


if __name__ == "__main__":
    main()
