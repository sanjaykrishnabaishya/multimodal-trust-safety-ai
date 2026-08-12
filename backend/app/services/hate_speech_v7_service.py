from __future__ import annotations

import hashlib
import json
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


REPO_ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_DIRECTORY = (
    REPO_ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "hate-speech-v7-rc1"
)
MODEL_DIRECTORY = CANDIDATE_DIRECTORY / "model"
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
CALIBRATION_PATH = MODEL_DIRECTORY / "calibration.json"

CANDIDATE_NAME = "hate-speech-v7-rc1"
NORMAL_CATEGORY = "Normal/Ignore"
ABUSIVE_CATEGORY = "Abusive Words"
HATE_CATEGORY = "Hate Speech & Discrimination"
UNCERTAIN_CATEGORY = "Uncertain"
HATE_LABEL = "hate_speech"

PROTECTED_REFERENCE_PATTERN = re.compile(
    r"\b(?:"
    r"religion|religious|caste|race|racial|ethnicity|ethnic|nationality|"
    r"muslims?|hindus?|christians?|jews?|jewish|sikhs?|buddhists?|jains?|"
    r"dalits?|adivasis?|tribal(?:s|\s+people)?|scheduled\s+castes?|"
    r"black\s+people|white\s+people|asians?|arabs?|africans?|"
    r"indians?|pakistanis?|bangladeshis?|nepalis?|sri\s+lankans?|"
    r"immigrants?|refugees?|foreigners?|"
    r"women|men|female|male|gender|transgender|trans\s+people|"
    r"gay|gays|lesbians?|bisexuals?|queer\s+people|sexual\s+orientation|"
    r"disabled|disability|autistic|autism|deaf|blind|mental\s+illness|"
    r"protected\s+(?:person|people|group|class|community)|"
    r"minority|minorities"
    r")\b",
    re.IGNORECASE,
)

REPORTING_OR_COUNTERSPEECH_PATTERN = re.compile(
    r"\b(?:"
    r"article\s+(?:reports?|reported)|news\s+(?:reports?|reported)|"
    r"documentary\s+(?:shows?|examines?|discusses?)|"
    r"study\s+(?:examines?|reports?|discusses?)|"
    r"lesson\s+(?:about|on)|workshop\s+(?:about|on)|"
    r"quoted?\s+(?:the\s+)?(?:hateful|racist|discriminatory)|"
    r"example\s+of\s+(?:hate|hateful|racist|discriminatory)|"
    r"condemn(?:s|ed|ing)?\s+(?:hate|hatred|racism|discrimination|"
    r"antisemitism|islamophobia|casteism|homophobia|transphobia)|"
    r"oppose(?:s|d|ing)?\s+(?:hate|hatred|racism|discrimination|"
    r"antisemitism|islamophobia|casteism|homophobia|transphobia)|"
    r"do\s+not\s+(?:hate|attack|exclude|harm|discriminate\s+against)|"
    r"never\s+(?:hate|attack|exclude|harm|discriminate\s+against)|"
    r"reported\s+(?:a|the|an)?\s*(?:hate\s+crime|hateful\s+comment|"
    r"racist\s+comment|discriminatory\s+statement)"
    r")\b",
    re.IGNORECASE,
)

_LOAD_LOCK = threading.Lock()
_MODEL: Any | None = None
_TOKENIZER: Any | None = None
_MANIFEST: dict[str, Any] | None = None
_VERDICT: dict[str, Any] | None = None
_POLICY: dict[str, Any] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"\s+", " ", value).strip()


def _verify_candidate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path in (MANIFEST_PATH, VERDICT_PATH, CALIBRATION_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required Hate Speech RC1 file is missing: {path}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))

    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected Hate Speech RC1 manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("Hate Speech RC1 did not pass development.")
    if verdict.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected Hate Speech RC1 verdict.")
    if verdict.get("passed_independent_readiness_gate") is not True:
        raise RuntimeError("Hate Speech RC1 failed its independent gate.")
    if verdict.get("eligible_for_guarded_live_integration") is not True:
        raise RuntimeError("Hate Speech RC1 is not eligible for guarded integration.")
    if verdict.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The Hate Speech RC1 enforcement contract is invalid.")
    if calibration.get("passed_development_gate") is not True:
        raise RuntimeError("The frozen Hate Speech calibration is invalid.")

    for artifact in manifest.get("artifacts", []):
        relative = Path(str(artifact.get("relative_path", "")))
        path = CANDIDATE_DIRECTORY / relative
        if not path.is_file():
            raise FileNotFoundError(f"Frozen Hate Speech artifact is missing: {relative}")
        if sha256_file(path) != str(artifact.get("sha256", "")):
            raise RuntimeError(f"Frozen Hate Speech artifact hash mismatch: {relative}")

    policy = dict(calibration.get("hate_output_policy", {}))
    if policy.get("enabled") is not True:
        raise RuntimeError("The frozen Hate Speech selective policy is disabled.")
    return manifest, verdict, policy


def _load_runtime() -> tuple[Any, Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    global _MODEL, _TOKENIZER, _MANIFEST, _VERDICT, _POLICY
    if all(
        item is not None
        for item in (_MODEL, _TOKENIZER, _MANIFEST, _VERDICT, _POLICY)
    ):
        return _MODEL, _TOKENIZER, _MANIFEST, _VERDICT, _POLICY  # type: ignore[return-value]

    with _LOAD_LOCK:
        if not all(
            item is not None
            for item in (_MODEL, _TOKENIZER, _MANIFEST, _VERDICT, _POLICY)
        ):
            manifest, verdict, policy = _verify_candidate()
            tokenizer = AutoTokenizer.from_pretrained(
                MODEL_DIRECTORY,
                local_files_only=True,
            )
            model = AutoModelForSequenceClassification.from_pretrained(
                MODEL_DIRECTORY,
                local_files_only=True,
                use_safetensors=True,
            )
            model.to("cpu")
            model.eval()
            labels = {
                int(index): str(label)
                for index, label in model.config.id2label.items()
            }
            if HATE_LABEL not in labels.values():
                raise RuntimeError("The frozen model does not expose hate_speech.")
            _MODEL = model
            _TOKENIZER = tokenizer
            _MANIFEST = manifest
            _VERDICT = verdict
            _POLICY = policy

    return _MODEL, _TOKENIZER, _MANIFEST, _VERDICT, _POLICY  # type: ignore[return-value]


def get_hate_speech_v7_status() -> dict[str, Any]:
    try:
        _, verdict, policy = _verify_candidate()
        return {
            "available": True,
            "candidate": CANDIDATE_NAME,
            "independently_validated": True,
            "eligible_for_guarded_live_integration": True,
            "automatic_enforcement_allowed": False,
            "probability_threshold": float(policy["probability_threshold"]),
            "minimum_margin": float(policy["minimum_margin"]),
            "verdict_status": str(verdict["status"]),
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


def analyze_hate_speech_v7(
    text: str,
    input_sources: list[str] | None = None,
) -> dict[str, Any]:
    value = str(text or "").strip()
    sources = list(input_sources or ["text"])
    base: dict[str, Any] = {
        "available": False,
        "candidate": CANDIDATE_NAME,
        "decision": "not_applied",
        "primary_category": "",
        "model_score": 0.0,
        "second_score": 0.0,
        "score_margin": 0.0,
        "threshold": 1.0,
        "minimum_margin": 1.0,
        "protected_reference_detected": False,
        "reporting_or_counterspeech_detected": False,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "reason": "The Hate Speech RC1 specialist was not applied.",
        "input_sources": sources,
    }
    if not value:
        base["reason"] = "Empty text was not analyzed."
        return base
    if set(sources) == {"visual_description"}:
        base["reason"] = "The English text specialist cannot analyze visual-only evidence."
        return base

    normalized = normalize_text(value)
    protected_reference = bool(PROTECTED_REFERENCE_PATTERN.search(normalized))
    reporting_or_counterspeech = bool(
        REPORTING_OR_COUNTERSPEECH_PATTERN.search(normalized)
    )
    base["protected_reference_detected"] = protected_reference
    base["reporting_or_counterspeech_detected"] = reporting_or_counterspeech

    if reporting_or_counterspeech:
        base.update(
            {
                "available": True,
                "decision": "safe_context_no_override",
                "reason": (
                    "Reporting, education, counterspeech, or condemnation context "
                    "was detected. RC1 cannot create a Hate Speech override."
                ),
            }
        )
        return base

    try:
        model, tokenizer, _, _, policy = _load_runtime()
        encoded = tokenizer(
            [value],
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        with torch.inference_mode():
            probabilities = torch.softmax(model(**encoded).logits, dim=-1)[0]
        labels = {
            int(index): str(label)
            for index, label in model.config.id2label.items()
        }
        hate_index = next(index for index, label in labels.items() if label == HATE_LABEL)
        hate_score = float(probabilities[hate_index].item())
        other_scores = [
            float(probabilities[index].item())
            for index in labels
            if index != hate_index
        ]
        second_score = max(other_scores) if other_scores else 0.0
        margin = hate_score - second_score
        threshold = float(policy["probability_threshold"])
        minimum_margin = float(policy["minimum_margin"])
        accepted = hate_score >= threshold and margin >= minimum_margin

        base.update(
            {
                "available": True,
                "model_score": round(hate_score, 4),
                "second_score": round(second_score, 4),
                "score_margin": round(margin, 4),
                "threshold": threshold,
                "minimum_margin": minimum_margin,
            }
        )
        if not accepted:
            base.update(
                {
                    "decision": "below_selective_threshold_no_override",
                    "reason": (
                        "The Hate Speech score did not meet the independently "
                        "evaluated selective policy. No category was changed."
                    ),
                }
            )
            return base

        base.update(
            {
                "decision": "accepted_review_only",
                "primary_category": HATE_CATEGORY,
                "human_review_required": True,
                "reason": (
                    "The independently evaluated English RC1 specialist found "
                    "high-confidence hate-speech evidence. The result is review-only."
                ),
            }
        )
        return base
    except Exception as error:
        base["reason"] = "Hate Speech RC1 failed safely and made no moderation change."
        base["error"] = f"{type(error).__name__}: {error}"
        return base


def apply_hate_speech_v7_fusion(
    *,
    category: str,
    severity: str,
    action: str,
    confidence: float,
    human_review_required: bool,
    reason: str,
    matched_signals: list[str],
    analysis: dict[str, Any],
    safe_context_confirmed: bool = False,
) -> dict[str, Any]:
    result = {
        "category": category,
        "severity": severity,
        "action": action,
        "confidence": confidence,
        "human_review_required": human_review_required,
        "reason": reason,
        "matched_signals": list(matched_signals),
        "decision_applied": False,
        "fusion_status": "not_applied",
    }
    if not analysis.get("available", False):
        result["fusion_status"] = "unavailable"
        return result
    if safe_context_confirmed or analysis.get("reporting_or_counterspeech_detected"):
        result["fusion_status"] = "blocked_by_safe_context"
        return result
    if analysis.get("decision") != "accepted_review_only":
        result["fusion_status"] = str(analysis.get("decision", "not_applied"))
        return result

    protected_reference = bool(analysis.get("protected_reference_detected", False))
    if category == ABUSIVE_CATEGORY and not protected_reference:
        result["fusion_status"] = "abusive_words_retained_without_protected_target"
        return result
    if category not in {NORMAL_CATEGORY, ABUSIVE_CATEGORY, HATE_CATEGORY}:
        result["fusion_status"] = "blocked_by_category_isolation"
        return result

    score = float(analysis.get("model_score", 0.0))
    signal = "hate_speech_v7:accepted_review_only"
    result.update(
        {
            "category": HATE_CATEGORY,
            "severity": "High",
            "action": "Refer to human review",
            "confidence": round(max(0.50, min(score, 0.95)), 2),
            "human_review_required": True,
            "reason": str(analysis.get("reason", "Hate Speech evidence requires review.")),
            "matched_signals": list(dict.fromkeys(matched_signals + [signal])),
            "decision_applied": True,
            "fusion_status": "hate_speech_review_only_applied",
        }
    )
    return result
