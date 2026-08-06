from app.services.fusion_service import (
    fuse_moderation_decision,
)

from app.services.identity_impersonation_service import (
    analyze_identity_impersonation,
)


IDENTITY_CATEGORY = (
    "Identity Theft & Impersonation"
)

SPAM_CATEGORY = (
    "Spam, Scam & Phishing"
)

NORMAL_CATEGORY = "Normal/Ignore"


def test_identity_signal_is_sent_for_review():
    result = fuse_moderation_decision(
        text=(
            "Someone is impersonating me "
            "using a cloned account."
        ),
        source_context="unknown",
        input_sources=["text"],
    )

    assert (
        result["category"]
        == IDENTITY_CATEGORY
    )

    assert result["confidence"] <= 0.75

    assert (
        result["action"]
        == "Refer to human review"
    )

    assert (
        result["human_review_required"]
        is True
    )

    assert (
        result[
            "identity_impersonation_detector_used"
        ]
        is True
    )


def test_phishing_remains_primary_category():
    result = fuse_moderation_decision(
        text=(
            "I am the official bank support "
            "agent. Send your OTP immediately."
        ),
        source_context="unknown",
        input_sources=["text"],
    )

    assert (
        result["category"]
        == SPAM_CATEGORY
    )

    assert (
        result["human_review_required"]
        is True
    )

    assert (
        result[
            "identity_impersonation_detector_used"
        ]
        is True
    )


def test_declared_parody_is_allowed():
    result = fuse_moderation_decision(
        text=(
            "This is a clearly marked "
            "parody account."
        ),
        source_context="unknown",
        input_sources=["text"],
    )

    assert (
        result["category"]
        == NORMAL_CATEGORY
    )

    assert result["action"] == "Allow"

    assert (
        result["human_review_required"]
        is False
    )

    assert (
        result[
            "identity_impersonation_detector_used"
        ]
        is False
    )


def test_ordinary_content_is_allowed():
    result = fuse_moderation_decision(
        text=(
            "Microsoft opened a new "
            "office in London."
        ),
        source_context="unknown",
        input_sources=["text"],
    )

    assert (
        result["category"]
        == NORMAL_CATEGORY
    )

    assert result["action"] == "Allow"

    assert (
        result[
            "identity_impersonation_detector_used"
        ]
        is False
    )


def test_identity_detector_cannot_enforce():
    result = analyze_identity_impersonation(
        "Someone is impersonating me "
        "using a cloned account."
    )

    assert (
        result["category"]
        == IDENTITY_CATEGORY
    )

    assert result["confidence"] <= 0.75

    assert (
        result["raw_signal_confidence"]
        >= result["confidence"]
    )

    assert (
        result["automatic_enforcement_allowed"]
        is False
    )

    assert (
        result["supporting_evidence_only"]
        is True
    )

    assert (
        result["policy_violation"]
        is False
    )

    assert (
        result["validation_status"]
        == "Failed independent recall target"
    )

    assert (
        result["human_review_required"]
        is True
    )