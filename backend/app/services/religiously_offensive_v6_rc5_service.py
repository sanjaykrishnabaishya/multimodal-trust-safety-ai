from __future__ import annotations

import hashlib
import json
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


REPO_ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_NAME = "religiously-offensive-v6-rc5"
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
POLICY_GATE_VERSION = "religious-policy-gate-2026.08-v1"

_LOAD_LOCK = threading.Lock()
_CLASSIFIER: Any | None = None
_ENCODER: Any | None = None
_CONFIG: dict[str, Any] | None = None


SAFE_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"news|journalist|journalism|article|report|reported|reporting|"
    r"documentary|historian|history|historical|archive|museum|catalogue|"
    r"court|legal|police|research|researcher|study|academic|scholar|"
    r"lesson|classroom|educational|workshop|seminar|"
    r"public[- ]service|safety campaign|prevention|restoration|restored|"
    r"repair|repaired|conservator|interfaith|cultural context|"
    r"good[- ]faith criticism|respectful criticism|respectfully critiques?|"
    r"condemn(?:s|ed|ing)?|oppose(?:s|d|ing)?|warn(?:s|ed|ing)? against|"
    r"does not endorse|without endorsing|as evidence|provides? context"
    r")\b",
    re.IGNORECASE,
)
NEGATED_HARM_PATTERN = re.compile(
    r"\b(?:do not|don't|never|must not|should not|shouldn't|stop|avoid|prevent)\b"
    r".{0,120}\b(?:burn|destroy|damage|desecrate|deface|smash|mock|insult|"
    r"ridicule|vandalize|vandalise|demolish|profane|humiliate)\b",
    re.IGNORECASE,
)
HARM_ADVOCACY_PATTERN = re.compile(
    r"\b(?:calls? (?:on|for)|urges?|asks? (?:people|listeners|participants|"
    r"followers|viewers|users)|encourages?|orders?|demands?|commands?|"
    r"promotes?|(?<!not )endorse(?:s|d|ing)?|praises?|celebrates?|plans?|"
    r"vows?|threatens?|"
    r"wants?|should|must|need to|let us|join us)\b",
    re.IGNORECASE,
)
FOLLOWER_REFERENCE_PATTERN = re.compile(
    r"\b(?:followers?|adherents?|devotees?|believers?|worshippers?|"
    r"congregants?|members?|families|workers|students|people|community|group)\b"
    r".{0,80}\b(?:religion|religious|faith|sect|denomination)\b|"
    r"\b(?:religion|religious|faith|sect|denomination)\b"
    r".{0,80}\b(?:followers?|adherents?|devotees?|believers?|worshippers?|"
    r"congregants?|members?|families|workers|students|people|community|group)\b",
    re.IGNORECASE,
)
FOLLOWER_HARM_PATTERN = re.compile(
    r"\b(?:inferior|parasites?|subhuman|not human|less than human|criminals?|"
    r"dangerous|exclude|expel|segregate|deny|refuse|remove|ban|boycott|"
    r"attack|harm|evict|strip|lose .*?rights?|forced? to leave|driven away|"
    r"should not exist|unfit for citizenship)\b",
    re.IGNORECASE,
)
OBJECT_OR_PLACE_PATTERN = re.compile(
    r"\b(?:holy|sacred|religious|devotional|consecrated|ceremonial|revered)\s+"
    r"(?:book|text|scripture|manuscript|scroll|emblem|symbol|icon|image|"
    r"portrait|painting|statue|sculpture|relic|object|artefact|artifact|"
    r"prayer beads|worship artefact|worship artifact|"
    r"vessel|banner|flag|monument|carving|artwork|site|sanctuary|centre|center|"
    r"hall|building)|"
    r"\b(?:temple|church|mosque|gurudwara|gurdwara|shrine|chapel|monastery|"
    r"sanctuary|prayer beads|worship artefact|worship artifact|"
    r"altar|prayer hall|prayer space|place of worship|worship building|"
    r"worship centre|worship center|religious building|religious centre|"
    r"religious center)\b",
    re.IGNORECASE,
)
FIGURE_PATTERN = re.compile(
    r"\b(?:deity|deities|god|gods|prophet|prophets|faith founder|"
    r"religious founder|religious figure|religious figurehead|spiritual leader|"
    r"religious leader|faith leader|sacred figure|divine figure|holy person|"
    r"revered teacher|religious teacher|spiritual guide)\b",
    re.IGNORECASE,
)
PHYSICAL_ATTACK_PATTERN = re.compile(
    r"\b(?:burn|burned|burning|incinerate|scorch|torch|set .*?ablaze|"
    r"set .*?fire|destroy|damage|desecrate|profane|deface|disfigure|smash|"
    r"shatter|break|crush|tear|rip|shred|cut|slash|hack|trample|stomp|kick|"
    r"drag|spit|soil|smear|coat .*?filth|throw .*?(?:fire|sewer|garbage)|"
    r"vandalize|vandalise|mutilate|dismantle|demolish|bulldoze|raze|level|"
    r"wreck|ransack|obliterate|spray .*?(?:obscene|degrading)|"
    r"paint .*?(?:obscene|degrading)|cover .*?(?:obscene|degrading))\b",
    re.IGNORECASE,
)
FIGURE_ATTACK_PATTERN = re.compile(
    r"\b(?:mock|ridicule|vilify|demean|humiliate|insult|degrade|revile|deride|"
    r"slander|lampoon|denigrate|abuse|obscene|vile|degrading|abusive|"
    r"repulsive|morphed|caricature|parody|contemptuous)\b",
    re.IGNORECASE,
)


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


def safe_or_boundary_veto(text: str) -> tuple[bool, str]:
    value = normalize_text(text)
    if NEGATED_HARM_PATTERN.search(value):
        return True, "safe_reporting_education_condemnation_or_negation"
    if SAFE_CONTEXT_PATTERN.search(value) and not HARM_ADVOCACY_PATTERN.search(value):
        return True, "safe_reporting_education_condemnation_or_negation"
    if FOLLOWER_REFERENCE_PATTERN.search(value) and FOLLOWER_HARM_PATTERN.search(value):
        return True, "protected_follower_hate_boundary"
    return False, ""


def sacred_attack_anchor(text: str) -> bool:
    value = normalize_text(text)
    object_or_place = bool(OBJECT_OR_PLACE_PATTERN.search(value))
    figure = bool(FIGURE_PATTERN.search(value))
    physical = bool(PHYSICAL_ATTACK_PATTERN.search(value))
    figure_attack = bool(FIGURE_ATTACK_PATTERN.search(value))
    return bool((object_or_place and physical) or (figure and (physical or figure_attack)))


def _verify_candidate(
    require_passing_verdict: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
    for path in (MANIFEST_PATH, MODEL_ARTIFACT, MODEL_CONFIG):
        if not path.is_file():
            raise FileNotFoundError(f"Required RC5 candidate file is missing: {path}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC5 manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("RC5 did not pass development.")
    if config.get("candidate") != "religiously-offensive-v6-rc5-development":
        raise RuntimeError("Unexpected RC5 model configuration.")
    if config.get("policy_gate_version") != POLICY_GATE_VERSION:
        raise RuntimeError("Unexpected RC5 policy-gate version.")
    if config.get("passed_development_gate") is not True:
        raise RuntimeError("The frozen RC5 policy gate did not pass development.")
    for artifact in manifest.get("artifacts", []):
        path = CANDIDATE_DIRECTORY / str(artifact["relative_path"])
        if not path.is_file():
            raise FileNotFoundError(f"Frozen RC5 artifact is missing: {path}")
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen RC5 artifact hash mismatch: {path.name}")

    verdict: dict[str, Any] | None = None
    if VERDICT_PATH.is_file():
        verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
        if verdict.get("candidate") != CANDIDATE_NAME:
            raise RuntimeError("Unexpected RC5 verdict.")
    if require_passing_verdict:
        if verdict is None:
            raise RuntimeError("RC5 has not been independently evaluated.")
        if verdict.get("passed_independent_readiness_gate") is not True:
            raise RuntimeError("RC5 failed independent validation.")
        if verdict.get("eligible_for_guarded_live_integration") is not True:
            raise RuntimeError("RC5 is not eligible for guarded integration.")
        if verdict.get("automatic_enforcement_allowed") is not False:
            raise RuntimeError("The RC5 enforcement contract is invalid.")
    return manifest, verdict, config


def _load_runtime() -> tuple[Any, Any, dict[str, Any]]:
    global _CLASSIFIER, _ENCODER, _CONFIG
    if _CLASSIFIER is not None and _ENCODER is not None and _CONFIG is not None:
        return _CLASSIFIER, _ENCODER, _CONFIG
    with _LOAD_LOCK:
        if _CLASSIFIER is None or _ENCODER is None or _CONFIG is None:
            _, _, config = _verify_candidate(require_passing_verdict=False)
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


def get_religiously_offensive_v6_rc5_status() -> dict[str, Any]:
    try:
        _, verdict, config = _verify_candidate(require_passing_verdict=False)
        passed = bool(
            verdict
            and verdict.get("passed_independent_readiness_gate") is True
            and verdict.get("eligible_for_guarded_live_integration") is True
        )
        return {
            "available": passed,
            "candidate": CANDIDATE_NAME,
            "development_gate_passed": True,
            "independently_validated": passed,
            "eligible_for_guarded_live_integration": passed,
            "automatic_enforcement_allowed": False,
            "connected_to_live_moderation": False,
            "policy_gate_version": config["policy_gate_version"],
            "permitted_active_output": "Religiously Offensive Content only",
            "follower_boundary_output_enabled": False,
            "follower_boundary_owner": "Hate Speech & Discrimination V7",
            "verdict_status": verdict.get("status", "Not independently evaluated")
            if verdict
            else "Not independently evaluated",
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


def _evaluate_candidate(
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
        "sacred_attack_anchor": False,
        "policy_veto_applied": False,
        "policy_veto_reason": "",
        "follower_boundary_output_enabled": False,
        "follower_boundary_owner": "Hate Speech & Discrimination V7",
        "input_sources": sources,
        "reason": "The RC5 religious-only policy gate was not applied.",
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
        semantic_policy = config["semantic_guard_policy"]
        semantic_signal = bool(
            religious_score
            >= float(semantic_policy["religious_probability_threshold"])
            and margin >= float(semantic_policy["minimum_religious_margin"])
        )
        anchor = sacred_attack_anchor(value)
        veto, veto_reason = safe_or_boundary_veto(value)
        base.update(
            {
                "available": True,
                "model_score": round(religious_score, 4),
                "competing_score": round(competing_score, 4),
                "religious_margin": round(margin, 4),
                "sacred_attack_anchor": anchor,
                "policy_veto_applied": veto,
                "policy_veto_reason": veto_reason,
            }
        )
        if veto:
            base.update(
                {
                    "decision": "no_religious_boundary_override",
                    "reason": (
                        "RC5 preserved the safe-context or protected-follower "
                        "boundary. The owning category specialist retains control."
                    ),
                }
            )
            return base
        if not anchor:
            base.update(
                {
                    "decision": "no_religious_boundary_override",
                    "reason": (
                        "No direct attack on a sacred object, religious figure, "
                        "or place of worship was detected."
                    ),
                }
            )
            return base
        if not semantic_signal:
            base.update(
                {
                    "decision": "no_religious_boundary_override",
                    "reason": (
                        "The content did not satisfy the frozen semantic probability "
                        "and margin guard."
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
                    "RC5 detected both a semantic religious-attack signal and a "
                    "direct sacred-target attack, with no safe-context or follower veto."
                ),
            }
        )
        return base
    except Exception as error:
        base["reason"] = f"RC5 unavailable: {type(error).__name__}: {error}"
        return base


def evaluate_religiously_offensive_v6_rc5_candidate(
    text: str,
    input_sources: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluation-only entry point. It does not authorize live integration."""
    return _evaluate_candidate(text, input_sources)


def analyze_religiously_offensive_v6_rc5(
    text: str,
    input_sources: list[str] | None = None,
) -> dict[str, Any]:
    try:
        _verify_candidate(require_passing_verdict=True)
    except Exception as error:
        return {
            "available": False,
            "candidate": CANDIDATE_NAME,
            "decision": "not_applied",
            "primary_category": "",
            "confidence": 0.0,
            "action": "",
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "follower_boundary_output_enabled": False,
            "follower_boundary_owner": "Hate Speech & Discrimination V7",
            "reason": (
                "RC5 is unavailable for live moderation: "
                f"{type(error).__name__}: {error}"
            ),
        }
    return _evaluate_candidate(text, input_sources)
