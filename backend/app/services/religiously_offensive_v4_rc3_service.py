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
CANDIDATE_NAME = "religiously-offensive-v4-rc3"
CANDIDATE_DIRECTORY = (
    REPO_ROOT / "backend" / "storage" / "candidates" / CANDIDATE_NAME
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
MODEL_DIRECTORY = CANDIDATE_DIRECTORY / "model"
MODEL_ARTIFACT = MODEL_DIRECTORY / "classifier.joblib"
MODEL_CONFIG = MODEL_DIRECTORY / "config.json"

RELIGIOUS_CATEGORY = "Religiously Offensive Content"
HATE_CATEGORY = "Hate Speech & Discrimination"
UNCERTAIN_CATEGORY = "Uncertain"
REQUIRED_ACTION = "Remove and send for human review"

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
            raise FileNotFoundError(f"Required RC3 candidate file is missing: {path}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected Religiously Offensive Content manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("RC3 did not pass development.")
    if verdict.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected Religiously Offensive Content verdict.")
    if verdict.get("passed_independent_readiness_gate") is not True:
        raise RuntimeError("RC3 failed independent validation.")
    if verdict.get("eligible_for_guarded_live_integration") is not True:
        raise RuntimeError("RC3 is not eligible for guarded integration.")
    if verdict.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The RC3 enforcement contract is invalid.")
    if config.get("candidate") != "religiously-offensive-v4-rc3-development":
        raise RuntimeError("Unexpected RC3 model configuration.")
    if config.get("religious_output_policy", {}).get("passed_development_gate") is not True:
        raise RuntimeError("The frozen RC3 policy did not pass development.")

    for artifact in manifest.get("artifacts", []):
        path = CANDIDATE_DIRECTORY / str(artifact["relative_path"])
        if not path.is_file():
            raise FileNotFoundError(f"Frozen RC3 artifact is missing: {path}")
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen RC3 artifact hash mismatch: {path.name}")
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


def get_religiously_offensive_v4_rc3_status() -> dict[str, Any]:
    try:
        _, verdict, config = _verify_candidate()
        policy = config["religious_output_policy"]
        return {
            "available": True,
            "candidate": CANDIDATE_NAME,
            "independently_validated": True,
            "eligible_for_guarded_live_integration": True,
            "automatic_enforcement_allowed": False,
            "religious_probability_threshold": policy[
                "religious_probability_threshold"
            ],
            "minimum_score_margin": policy["minimum_score_margin"],
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


def analyze_religiously_offensive_v4_rc3(
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
        "boundary_category": "",
        "model_label": "",
        "model_score": 0.0,
        "second_score": 0.0,
        "score_margin": 0.0,
        "confidence": 0.0,
        "action": "",
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "input_sources": sources,
        "reason": "The RC3 specialist was not applied.",
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
        probabilities = classifier.predict_proba(embedding)[0]
        order = np.argsort(probabilities)[::-1]
        top_index = int(order[0])
        second_index = int(order[1])
        top_label = str(classifier.classes_[top_index])
        top_score = float(probabilities[top_index])
        second_score = float(probabilities[second_index])
        margin = top_score - second_score
        policy = config["religious_output_policy"]
        threshold = float(policy["religious_probability_threshold"])
        minimum_margin = float(policy["minimum_score_margin"])
        base.update(
            {
                "available": True,
                "model_label": top_label,
                "model_score": round(top_score, 4),
                "second_score": round(second_score, 4),
                "score_margin": round(margin, 4),
            }
        )

        if top_label == "religiously_offensive":
            if top_score < threshold or margin < minimum_margin:
                base.update(
                    {
                        "decision": "uncertain_review_only",
                        "primary_category": UNCERTAIN_CATEGORY,
                        "confidence": round(min(0.69, top_score), 4),
                        "action": "Refer to human review",
                        "human_review_required": True,
                        "reason": (
                            "The religious-offense score did not satisfy the frozen "
                            "selective-output policy."
                        ),
                    }
                )
                return base
            base.update(
                {
                    "decision": "religiously_offensive_review_only",
                    "primary_category": RELIGIOUS_CATEGORY,
                    "confidence": round(min(0.90, max(0.55, top_score)), 4),
                    "action": REQUIRED_ACTION,
                    "human_review_required": True,
                    "reason": (
                        "The independently validated specialist detected a semantic "
                        "attack on a sacred object, figure, or place of worship."
                    ),
                }
            )
            return base

        if top_label == "protected_followers_hate_boundary":
            base.update(
                {
                    "decision": "protected_followers_hate_boundary",
                    "boundary_category": HATE_CATEGORY,
                    "confidence": round(min(0.90, max(0.55, top_score)), 4),
                    "human_review_required": True,
                    "reason": (
                        "The content targets people because of religion. Category "
                        "ownership remains with Hate Speech & Discrimination."
                    ),
                }
            )
            return base

        if top_label == "safe_reporting_or_criticism":
            base.update(
                {
                    "decision": "safe_reporting_education_or_criticism",
                    "reason": (
                        "Reporting, education, condemnation, restoration, or "
                        "good-faith criticism was detected."
                    ),
                }
            )
            return base

        base.update(
            {
                "decision": "no_religious_boundary_override",
                "reason": "No Religiously Offensive Content override was created.",
            }
        )
        return base
    except Exception as error:
        base["reason"] = f"RC3 unavailable: {type(error).__name__}: {error}"
        return base

