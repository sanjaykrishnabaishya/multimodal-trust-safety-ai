from __future__ import annotations

import hashlib
import json
import threading
import unicodedata
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


REPO_ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_NAME = "religiously-offensive-v5-rc4"
CANDIDATE_DIRECTORY = (
    REPO_ROOT / "backend" / "storage" / "candidates" / CANDIDATE_NAME
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
MODEL_ARTIFACT = CANDIDATE_DIRECTORY / "model" / "classifier.joblib"
MODEL_CONFIG = CANDIDATE_DIRECTORY / "model" / "config.json"

RELIGIOUS_CATEGORY = "Religiously Offensive Content"
REQUIRED_ACTION = "Remove and send for human review"
RELIGIOUS_LABEL = "religiously_offensive"

_LOAD_LOCK = threading.Lock()
_CLASSIFIER: Any | None = None
_ENCODER: Any | None = None
_CONFIG: dict[str, Any] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", str(text or "")).casefold().split()
    )


def _verify_candidate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path in (MANIFEST_PATH, VERDICT_PATH, MODEL_ARTIFACT, MODEL_CONFIG):
        if not path.is_file():
            raise FileNotFoundError(f"Required RC4 candidate file is missing: {path}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC4 manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("RC4 did not pass development.")
    if verdict.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC4 verdict.")
    if verdict.get("passed_independent_readiness_gate") is not True:
        raise RuntimeError("RC4 failed independent validation.")
    if verdict.get("eligible_for_guarded_live_integration") is not True:
        raise RuntimeError("RC4 is not eligible for guarded integration.")
    if verdict.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The RC4 enforcement contract is invalid.")
    if config.get("candidate") != "religiously-offensive-v5-rc4-development":
        raise RuntimeError("Unexpected RC4 model configuration.")
    policy = config.get("religious_only_guard_policy", {})
    if policy.get("passed_development_gate") is not True:
        raise RuntimeError("The frozen RC4 guard did not pass development.")
    for artifact in manifest.get("artifacts", []):
        path = CANDIDATE_DIRECTORY / str(artifact["relative_path"])
        if not path.is_file():
            raise FileNotFoundError(f"Frozen RC4 artifact is missing: {path}")
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen RC4 artifact hash mismatch: {path.name}")
    return manifest, verdict, config


def _load_runtime() -> tuple[Any, Any, dict[str, Any]]:
    global _CLASSIFIER, _ENCODER, _CONFIG
    if _CLASSIFIER is not None and _ENCODER is not None and _CONFIG is not None:
        return _CLASSIFIER, _ENCODER, _CONFIG
    with _LOAD_LOCK:
        if _CLASSIFIER is None or _ENCODER is None or _CONFIG is None:
            _, _, config = _verify_candidate()
            classifier = joblib.load(MODEL_ARTIFACT)
            encoder = SentenceTransformer(
                str(config["embedding_model"]),
                revision=str(config["embedding_model_revision"]),
                device="cpu",
            )
            _CLASSIFIER = classifier
            _ENCODER = encoder
            _CONFIG = config
    return _CLASSIFIER, _ENCODER, _CONFIG


def get_religiously_offensive_v5_rc4_status() -> dict[str, Any]:
    try:
        _, verdict, config = _verify_candidate()
        policy = config["religious_only_guard_policy"]
        return {
            "available": True,
            "candidate": CANDIDATE_NAME,
            "independently_validated": True,
            "eligible_for_guarded_live_integration": True,
            "automatic_enforcement_allowed": False,
            "permitted_active_output": "Religiously Offensive Content only",
            "follower_boundary_output_enabled": False,
            "follower_boundary_owner": "Hate Speech & Discrimination V7",
            "religious_probability_threshold": policy[
                "religious_probability_threshold"
            ],
            "minimum_religious_margin": policy["minimum_religious_margin"],
            "verdict_status": verdict["status"],
        }
    except Exception as error:
        return {
            "available": False,
            "candidate": CANDIDATE_NAME,
            "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "automatic_enforcement_allowed": False,
            "error": f"{type(error).__name__}: {error}",
        }


def analyze_religiously_offensive_v5_rc4(
    text: str,
    input_sources: list[str] | None = None,
) -> dict[str, Any]:
    value = normalize_text(text)
    sources = list(input_sources or ["text"])
    base: dict[str, Any] = {
        "available": False,
        "candidate": CANDIDATE_NAME,
        "decision": "not_applied",
        "primary_category": "",
        "model_score": 0.0,
        "competing_score": 0.0,
        "religious_margin": 0.0,
        "confidence": 0.0,
        "action": "",
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "follower_boundary_output_enabled": False,
        "follower_boundary_owner": "Hate Speech & Discrimination V7",
        "input_sources": sources,
        "reason": "The RC4 religious-only guard was not applied.",
    }
    if not value:
        base["reason"] = "Empty text was not analyzed."
        return base
    if set(sources) == {"visual_description"}:
        base["reason"] = (
            "The text specialist is not validated for visual-description-only evidence."
        )
        return base

    try:
        classifier, encoder, config = _load_runtime()
        embedding = encoder.encode(
            [value],
            batch_size=1,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        scores = classifier.predict_proba(embedding)[0]
        classes = np.asarray(classifier.classes_)
        religious_index = int(np.where(classes == RELIGIOUS_LABEL)[0][0])
        religious_score = float(scores[religious_index])
        competing_score = float(np.max(np.delete(scores, religious_index)))
        margin = religious_score - competing_score
        policy = config["religious_only_guard_policy"]
        threshold = float(policy["religious_probability_threshold"])
        minimum_margin = float(policy["minimum_religious_margin"])
        applied = religious_score >= threshold and margin >= minimum_margin
        base.update(
            {
                "available": True,
                "model_score": round(religious_score, 4),
                "competing_score": round(competing_score, 4),
                "religious_margin": round(margin, 4),
            }
        )
        if not applied:
            base.update(
                {
                    "decision": "no_religious_boundary_override",
                    "reason": (
                        "The content did not satisfy the frozen religious-only "
                        "probability and margin guard. Other category specialists retain ownership."
                    ),
                }
            )
            return base
        base.update(
            {
                "decision": "religiously_offensive_review_only",
                "primary_category": RELIGIOUS_CATEGORY,
                "confidence": round(min(0.90, max(0.55, religious_score)), 4),
                "action": REQUIRED_ACTION,
                "human_review_required": True,
                "reason": (
                    "The independently validated religious-only guard detected a "
                    "semantic attack on a sacred object, figure, or place of worship."
                ),
            }
        )
        return base
    except Exception as error:
        base["reason"] = f"RC4 unavailable: {type(error).__name__}: {error}"
        return base

