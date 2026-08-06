from __future__ import annotations

import logging
from threading import Lock
from typing import Any

import torch
from transformers import pipeline

from app.policy_config import (
    ModerationCategory,
)


LOGGER = logging.getLogger(__name__)


MODEL_NAME = (
    "MoritzLaurer/"
    "multilingual-MiniLMv2-L6-mnli-xnli"
)

POLICY_VERSION = "2026.08"

MAX_INPUT_CHARACTERS = 6000

MODEL_LOCK = Lock()

_classifier: Any | None = None
_model_error: str | None = None


UNCERTAIN_CATEGORY = "Uncertain"

NO_AUTOMATIC_ACTION = (
    "No automated enforcement"
)


CATEGORY_LABELS: dict[str, str] = {
    (
        ModerationCategory
        .RELIGIOUSLY_OFFENSIVE
        .value
    ): (
        "an attack on a religion, religious "
        "symbol, deity, prophet, leader, place, "
        "or religious follower"
    ),

    (
        ModerationCategory
        .HATE_SPEECH
        .value
    ): (
        "hate speech or discrimination against "
        "a protected person or group"
    ),

    (
        ModerationCategory
        .TERRORISM
        .value
    ): (
        "support, praise, recruitment, propaganda, "
        "or assistance for terrorism or violent "
        "extremism"
    ),

    (
        ModerationCategory
        .VIOLENT_CONTENT
        .value
    ): (
        "graphic violence, a violent threat, "
        "physical injury, torture, killing, "
        "blood, or bodily harm"
    ),

    (
        ModerationCategory
        .DANGEROUS_CONTENT
        .value
    ): (
        "a dangerous activity, dangerous stunt, "
        "self-harm act, or instruction likely "
        "to cause injury or property damage"
    ),

    (
        ModerationCategory
        .GRAPHIC_SEXUAL_CONTENT
        .value
    ): (
        "explicit nudity, pornography, sexual "
        "activity, sexual violence, or graphic "
        "sexual material"
    ),

    (
        ModerationCategory
        .SEXUAL_HARASSMENT
        .value
    ): (
        "unwanted sexual requests, sexual "
        "pressure, sexual remarks, or unwelcome "
        "sexual conduct directed at a person"
    ),

    (
        ModerationCategory
        .CYBERBULLYING
        .value
    ): (
        "bullying, humiliation, intimidation, "
        "repeated harassment, or coordinated "
        "abuse directed at a person"
    ),

    (
        ModerationCategory
        .INVASION_OF_PRIVACY
        .value
    ): (
        "recording, exposing, or distributing "
        "another person's private or intimate "
        "activity without consent"
    ),

    (
        ModerationCategory
        .ILLEGAL_ACTIVITIES
        .value
    ): (
        "selling, promoting, instructing, or "
        "facilitating an illegal activity or "
        "illegal transaction"
    ),

    (
        ModerationCategory
        .PRIVATE_INFORMATION
        .value
    ): (
        "publishing another person's private "
        "identity, contact, financial, location, "
        "account, or authentication information"
    ),

    (
        ModerationCategory
        .IDENTITY_THEFT
        .value
    ): (
        "identity theft, fraudulent impersonation, "
        "or misuse of another person's identity, "
        "account, credentials, or likeness"
    ),

    (
        ModerationCategory
        .MISINFORMATION
        .value
    ): (
        "a materially false, fabricated, "
        "manipulated, or misleading factual "
        "claim presented as true"
    ),

    (
        ModerationCategory
        .SPAM_SCAM_PHISHING
        .value
    ): (
        "spam, a scam, phishing, a deceptive "
        "offer, or an attempt to obtain money, "
        "passwords, OTPs, or banking information"
    ),

    (
        ModerationCategory
        .INTELLECTUAL_PROPERTY
        .value
    ): (
        "unauthorized copying, distribution, "
        "sale, or misuse of copyrighted or "
        "trademarked material"
    ),

    (
        ModerationCategory
        .MALICIOUS_PROGRAMS
        .value
    ): (
        "malware or harmful instructions intended "
        "to compromise a device, application, "
        "account, or network"
    ),

    (
        ModerationCategory
        .ABUSIVE_WORDS
        .value
    ): (
        "insults, swear words, abusive expressions, "
        "or denigrating language directed at "
        "a person"
    ),

    (
        ModerationCategory
        .CHILD_EXPLOITATION
        .value
    ): (
        "sexual exploitation, grooming, "
        "solicitation, sexualization, abuse, "
        "harm, or endangerment of a child"
    ),

    (
        ModerationCategory
        .NORMAL_IGNORE
        .value
    ): (
        "safe, ordinary, benign, educational, "
        "personal, or lawful content"
    ),
}


LABEL_TO_CATEGORY = {
    label: category
    for category, label
    in CATEGORY_LABELS.items()
}

CANDIDATE_LABELS = list(
    CATEGORY_LABELS.values()
)


HIGH_RISK_CATEGORIES = {
    (
        ModerationCategory
        .CHILD_EXPLOITATION
        .value
    ),
    (
        ModerationCategory
        .TERRORISM
        .value
    ),
    (
        ModerationCategory
        .VIOLENT_CONTENT
        .value
    ),
    (
        ModerationCategory
        .GRAPHIC_SEXUAL_CONTENT
        .value
    ),
    (
        ModerationCategory
        .PRIVATE_INFORMATION
        .value
    ),
    (
        ModerationCategory
        .MALICIOUS_PROGRAMS
        .value
    ),
}


def _select_device() -> int:
    if torch.cuda.is_available():
        return 0

    return -1


def _device_name() -> str:
    if torch.cuda.is_available():
        return torch.cuda.get_device_name(0)

    return "CPU"


def _load_classifier() -> Any:
    global _classifier
    global _model_error

    if _classifier is not None:
        return _classifier

    if _model_error is not None:
        raise RuntimeError(
            _model_error
        )

    with MODEL_LOCK:
        if _classifier is not None:
            return _classifier

        try:
            LOGGER.info(
                "Loading local AI model %s",
                MODEL_NAME,
            )

            _classifier = pipeline(
                task=(
                    "zero-shot-classification"
                ),
                model=MODEL_NAME,
                device=_select_device(),
            )

            LOGGER.info(
                "Local AI model loaded on %s",
                _device_name(),
            )

            return _classifier

        except Exception as exc:
            _model_error = (
                "The local AI model could not "
                f"be loaded: {exc}"
            )

            LOGGER.exception(
                _model_error
            )

            raise RuntimeError(
                _model_error
            ) from exc


def _clean_text(
    text: str,
) -> str:
    cleaned_text = " ".join(
        str(text).split()
    )

    return cleaned_text[
        :MAX_INPUT_CHARACTERS
    ]


def _build_unavailable_result(
    reason: str,
) -> dict[str, Any]:
    return {
        "available": False,
        "model_name": MODEL_NAME,
        "device": _device_name(),
        "category": UNCERTAIN_CATEGORY,
        "predicted_category": None,
        "raw_model_score": 0.0,
        "second_category": None,
        "second_score": 0.0,
        "score_margin": 0.0,
        "evidence_strength": "Unavailable",
        "eligible_for_automatic_action": False,
        "action": NO_AUTOMATIC_ACTION,
        "requires_consensus": True,
        "reason": reason,
        "ranked_predictions": [],
    }


def _determine_evidence_strength(
    *,
    top_score: float,
    score_margin: float,
) -> str:
    if (
        top_score >= 0.75
        and score_margin >= 0.20
    ):
        return "Strong"

    if (
        top_score >= 0.50
        and score_margin >= 0.12
    ):
        return "Moderate"

    return "Weak"


def classify_with_local_ai(
    text: str,
    top_k: int = 5,
) -> dict[str, Any]:
    cleaned_text = _clean_text(
        text
    )

    if not cleaned_text:
        return _build_unavailable_result(
            "No text was available for local "
            "AI classification."
        )

    try:
        classifier = _load_classifier()

        model_result = classifier(
            cleaned_text,
            candidate_labels=(
                CANDIDATE_LABELS
            ),
            multi_label=False,
            hypothesis_template=(
                "This content contains {}."
            ),
        )

    except Exception as exc:
        return _build_unavailable_result(
            str(exc)
        )

    labels = model_result.get(
        "labels",
        [],
    )

    scores = model_result.get(
        "scores",
        [],
    )

    ranked_predictions: list[
        dict[str, Any]
    ] = []

    for label, score in zip(
        labels,
        scores,
    ):
        category = (
            LABEL_TO_CATEGORY.get(
                str(label)
            )
        )

        if category is None:
            continue

        ranked_predictions.append(
            {
                "category": category,
                "raw_model_score": round(
                    float(score),
                    4,
                ),
            }
        )

    if not ranked_predictions:
        return _build_unavailable_result(
            "The local model returned no "
            "usable predictions."
        )

    top_prediction = (
        ranked_predictions[0]
    )

    if len(ranked_predictions) > 1:
        second_prediction = (
            ranked_predictions[1]
        )
    else:
        second_prediction = {
            "category": None,
            "raw_model_score": 0.0,
        }

    predicted_category = str(
        top_prediction["category"]
    )

    top_score = float(
        top_prediction[
            "raw_model_score"
        ]
    )

    second_score = float(
        second_prediction[
            "raw_model_score"
        ]
    )

    score_margin = max(
        0.0,
        top_score - second_score,
    )

    evidence_strength = (
        _determine_evidence_strength(
            top_score=top_score,
            score_margin=score_margin,
        )
    )

    high_risk_prediction = (
        predicted_category
        in HIGH_RISK_CATEGORIES
    )

    # Important:
    # This model is only one evidence source.
    # It is never allowed to produce a final
    # category or enforcement action alone.
    return {
        "available": True,
        "model_name": MODEL_NAME,
        "device": _device_name(),

        # This is the safe standalone decision.
        "category": UNCERTAIN_CATEGORY,
        "action": NO_AUTOMATIC_ACTION,

        # This is internal supporting evidence.
        "predicted_category": (
            predicted_category
        ),
        "raw_model_score": round(
            top_score,
            4,
        ),
        "second_category": (
            second_prediction[
                "category"
            ]
        ),
        "second_score": round(
            second_score,
            4,
        ),
        "score_margin": round(
            score_margin,
            4,
        ),
        "evidence_strength": (
            evidence_strength
        ),
        "high_risk_prediction": (
            high_risk_prediction
        ),

        # A local AI prediction can never trigger
        # an automatic action without independent
        # policy or RAG agreement.
        "eligible_for_automatic_action": False,
        "requires_consensus": True,

        "reason": (
            "The local AI prediction is supporting "
            "evidence only. It cannot select a "
            "moderation action without agreement "
            "from independent policy, dictionary, "
            "or RAG evidence."
        ),
        "ranked_predictions": (
            ranked_predictions[
                :max(1, top_k)
            ]
        ),
    }


def get_local_ai_status(
    load_model: bool = False,
) -> dict[str, Any]:
    if load_model:
        try:
            _load_classifier()
        except RuntimeError:
            pass

    return {
        "model_name": MODEL_NAME,
        "loaded": (
            _classifier is not None
        ),
        "available": (
            _model_error is None
        ),
        "device": _device_name(),
        "cuda_available": (
            torch.cuda.is_available()
        ),
        "category_count": len(
            CATEGORY_LABELS
        ),
        "policy_version": (
            POLICY_VERSION
        ),
        "standalone_enforcement_enabled": (
            False
        ),
        "error": _model_error,
    }