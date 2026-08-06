from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock
from typing import Any

import joblib


LOGGER = logging.getLogger(__name__)


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

MODEL_PATH = (
    BACKEND_ROOT
    / "storage"
    / "models"
    / "sms_spam"
    / "sms_spam_model.joblib"
)


NORMAL_CATEGORY = "Normal/Ignore"

SPAM_CATEGORY = (
    "Spam, Scam & Phishing"
)


MODEL_LOCK = Lock()

_model_package: dict[
    str,
    Any,
] | None = None

_model_error: str | None = None


def _load_model_package() -> (
    dict[str, Any]
):
    global _model_package
    global _model_error

    if _model_package is not None:
        return _model_package

    if _model_error is not None:
        raise RuntimeError(
            _model_error
        )

    with MODEL_LOCK:
        if _model_package is not None:
            return _model_package

        if not MODEL_PATH.exists():
            _model_error = (
                "The SMS spam specialist model "
                f"does not exist: {MODEL_PATH}"
            )

            raise RuntimeError(
                _model_error
            )

        try:
            loaded_package = joblib.load(
                MODEL_PATH
            )

            required_keys = {
                "model",
                "threshold",
                "normal_label",
                "spam_label",
                "normal_category",
                "spam_category",
                "model_version",
            }

            missing_keys = (
                required_keys
                - set(
                    loaded_package.keys()
                )
            )

            if missing_keys:
                raise ValueError(
                    "The SMS spam model package "
                    "is missing: "
                    + ", ".join(
                        sorted(
                            missing_keys
                        )
                    )
                )

            _model_package = (
                loaded_package
            )

            LOGGER.info(
                "SMS spam specialist model "
                "version %s loaded.",
                _model_package[
                    "model_version"
                ],
            )

            return _model_package

        except Exception as exc:
            _model_error = (
                "The SMS spam specialist model "
                f"could not be loaded: {exc}"
            )

            LOGGER.exception(
                _model_error
            )

            raise RuntimeError(
                _model_error
            ) from exc


def _normalize_text(
    text: str,
) -> str:
    return " ".join(
        str(text).split()
    )


def _unavailable_result(
    reason: str,
) -> dict[str, Any]:
    return {
        "available": False,
        "model_version": None,
        "predicted_category": None,
        "spam_probability": 0.0,
        "normal_probability": 0.0,
        "threshold": 0.0,
        "threshold_passed": False,
        "evidence_strength": (
            "Unavailable"
        ),
        "eligible_for_automatic_action": (
            False
        ),
        "reason": reason,
    }


def _get_spam_probability(
    *,
    model: Any,
    spam_label: int,
    text: str,
) -> float:
    probabilities = (
        model.predict_proba(
            [text]
        )[0]
    )

    class_values = list(
        model.classes_
    )

    if spam_label not in class_values:
        raise RuntimeError(
            "The model does not contain "
            "the spam class."
        )

    spam_index = class_values.index(
        spam_label
    )

    return float(
        probabilities[
            spam_index
        ]
    )


def _evidence_strength(
    *,
    spam_probability: float,
    threshold: float,
) -> str:
    if spam_probability >= max(
        0.90,
        threshold,
    ):
        return "Strong"

    if spam_probability >= threshold:
        return "Moderate"

    if spam_probability >= max(
        0.35,
        threshold - 0.15,
    ):
        return "Weak"

    return "No spam support"


def analyze_sms_spam_probability(
    text: str,
) -> dict[str, Any]:
    cleaned_text = _normalize_text(
        text
    )

    if not cleaned_text:
        return _unavailable_result(
            "No text was provided to the "
            "SMS spam specialist."
        )

    try:
        package = (
            _load_model_package()
        )

        model = package["model"]

        spam_label = int(
            package["spam_label"]
        )

        threshold = float(
            package["threshold"]
        )

        spam_probability = (
            _get_spam_probability(
                model=model,
                spam_label=spam_label,
                text=cleaned_text,
            )
        )

    except Exception as exc:
        return _unavailable_result(
            str(exc)
        )

    normal_probability = max(
        0.0,
        1.0 - spam_probability,
    )

    threshold_passed = (
        spam_probability >= threshold
    )

    if threshold_passed:
        predicted_category = (
            SPAM_CATEGORY
        )

    else:
        predicted_category = (
            NORMAL_CATEGORY
        )

    evidence_strength = (
        _evidence_strength(
            spam_probability=(
                spam_probability
            ),
            threshold=threshold,
        )
    )

    return {
        "available": True,
        "model_version": str(
            package["model_version"]
        ),
        "training_source": str(
            package.get(
                "training_source",
                "",
            )
        ),
        "predicted_category": (
            predicted_category
        ),
        "spam_probability": round(
            spam_probability,
            4,
        ),
        "normal_probability": round(
            normal_probability,
            4,
        ),
        "threshold": round(
            threshold,
            4,
        ),
        "threshold_passed": (
            threshold_passed
        ),
        "evidence_strength": (
            evidence_strength
        ),

        # This specialist becomes one input to
        # the complete consensus system. It does
        # not directly enforce an action.
        "eligible_for_automatic_action": (
            False
        ),
        "reason": (
            "The SMS specialist supplies a "
            "calibrated spam probability. "
            "Context, dictionary, policy and RAG "
            "evidence must still be considered."
        ),
    }


def get_sms_spam_model_status(
    load_model: bool = False,
) -> dict[str, Any]:
    if load_model:
        try:
            _load_model_package()
        except RuntimeError:
            pass

    return {
        "available": (
            MODEL_PATH.exists()
            and _model_error is None
        ),
        "loaded": (
            _model_package is not None
        ),
        "model_path": str(
            MODEL_PATH
        ),
        "model_version": (
            str(
                _model_package[
                    "model_version"
                ]
            )
            if _model_package
            else None
        ),
        "error": _model_error,
    }