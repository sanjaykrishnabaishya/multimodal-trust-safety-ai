from __future__ import annotations

import re
from typing import Any


IDENTITY_CATEGORY = (
    "Identity Theft & Impersonation"
)

NORMAL_CATEGORY = "Normal/Ignore"


# ---------------------------------------------------------------------------
# Strong impersonation signals
# ---------------------------------------------------------------------------

EXPLICIT_IMPERSONATION_PATTERNS = {
    "explicit_impersonation": re.compile(
        r"""
        \b
        (?:
            impersonat(?:e|es|ed|ing)
            |
            pretending\s+to\s+be
            |
            pretend\s+to\s+be
            |
            posing\s+as
            |
            pose\s+as
            |
            personat(?:e|ed|ing)
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "fake_identity": re.compile(
        r"""
        \b
        (?:
            fake
            |
            false
            |
            fabricated
            |
            stolen
        )
        \s+
        (?:
            identity
            |
            profile
            |
            account
            |
            credentials
            |
            documents?
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "identity_misuse": re.compile(
        r"""
        \b
        (?:
            using
            |
            used
            |
            stole
            |
            stolen
            |
            copied
            |
            cloned
        )
        \s+
        (?:
            someone\s+else(?:'s)?
            |
            another\s+person(?:'s)?
            |
            their
            |
            his
            |
            her
        )
        \s+
        (?:
            identity
            |
            name
            |
            profile
            |
            account
            |
            photograph
            |
            photo
            |
            documents?
            |
            credentials
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "account_cloning": re.compile(
        r"""
        \b
        (?:
            cloned
            |
            copied
            |
            duplicate
            |
            fake
        )
        \s+
        (?:
            social\s+media\s+
            |
            online\s+
        )?
        (?:
            profile
            |
            account
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "impersonation_report": re.compile(
        r"""
        \b
        (?:
            someone
            |
            somebody
            |
            this\s+person
            |
            this\s+account
            |
            this\s+profile
        )
        \s+
        (?:
            is
            |
            was
            |
            has\s+been
        )
        \s+
        (?:
            impersonating
            |
            pretending\s+to\s+be
            |
            posing\s+as
            |
            using
        )
        \s+
        (?:
            me
            |
            us
            |
            my\s+company
            |
            our\s+company
            |
            my\s+organization
            |
            our\s+organization
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "identity_theft_statement": re.compile(
        r"""
        \b
        (?:
            identity\s+theft
            |
            identity\s+fraud
            |
            account\s+takeover
            |
            account\s+hijacking
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),
}


# ---------------------------------------------------------------------------
# Supporting deceptive-identity signals
# ---------------------------------------------------------------------------

IDENTITY_CLAIM_PATTERNS = {
    "official_identity_claim": re.compile(
        r"""
        \b
        (?:
            i\s+am
            |
            i'm
            |
            we\s+are
            |
            this\s+is
        )
        \s+
        (?:
            the\s+
        )?
        (?:
            official
            |
            authorized
            |
            verified
            |
            genuine
        )
        \s+
        (?:
            representative
            |
            support
            |
            agent
            |
            account
            |
            team
            |
            department
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "organization_claim": re.compile(
        r"""
        \b
        (?:
            calling
            |
            contacting\s+you
            |
            writing\s+to\s+you
            |
            messaging\s+you
        )
        \s+
        (?:
            from
            |
            on\s+behalf\s+of
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "authority_claim": re.compile(
        r"""
        \b
        (?:
            bank
            |
            police
            |
            government
            |
            tax
            |
            customs
            |
            court
            |
            technical\s+support
            |
            customer\s+support
        )
        \s+
        (?:
            officer
            |
            official
            |
            agent
            |
            representative
            |
            team
            |
            department
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),
}


DECEPTIVE_REQUEST_PATTERNS = {
    "credential_request": re.compile(
        r"""
        \b
        (?:
            send
            |
            share
            |
            provide
            |
            confirm
            |
            verify
            |
            enter
            |
            submit
        )
        \s+
        (?:
            your\s+
        )?
        (?:
            otp
            |
            password
            |
            passcode
            |
            pin
            |
            cvv
            |
            credentials
            |
            login
            |
            account\s+details
            |
            banking\s+details
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "money_request": re.compile(
        r"""
        \b
        (?:
            send
            |
            pay
            |
            transfer
            |
            deposit
        )
        \s+
        (?:
            money
            |
            funds
            |
            payment
            |
            cash
            |
            fee
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "urgent_verification": re.compile(
        r"""
        \b
        (?:
            verify\s+immediately
            |
            confirm\s+immediately
            |
            act\s+immediately
            |
            urgent\s+verification
            |
            account\s+will\s+be\s+blocked
            |
            account\s+has\s+been\s+blocked
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),
}


# ---------------------------------------------------------------------------
# Safe and exception contexts
# ---------------------------------------------------------------------------

SAFE_CONTEXT_PATTERNS = {
    "educational_context": re.compile(
        r"""
        \b
        (?:
            impersonation\s+awareness
            |
            identity\s+theft\s+awareness
            |
            fraud\s+prevention
            |
            security\s+training
            |
            educational\s+example
            |
            training\s+example
            |
            fictional\s+example
            |
            hypothetical\s+example
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "preventative_advice": re.compile(
        r"""
        \b
        (?:
            how\s+to\s+report\s+impersonation
            |
            how\s+to\s+prevent\s+identity\s+theft
            |
            protect\s+yourself\s+from\s+identity\s+theft
            |
            never\s+share\s+your\s+credentials
            |
            do\s+not\s+share\s+your\s+credentials
            |
            beware\s+of\s+fake\s+accounts
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "declared_parody": re.compile(
        r"""
        \b
        (?:
            parody\s+account
            |
            satire\s+account
            |
            fan\s+account
            |
            unofficial\s+fan\s+page
            |
            clearly\s+marked\s+parody
            |
            clearly\s+labelled\s+parody
            |
            clearly\s+labeled\s+parody
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "condemnation_context": re.compile(
        r"""
        \b
        (?:
            do\s+not\s+impersonate
            |
            never\s+impersonate
            |
            impersonation\s+is\s+illegal
            |
            identity\s+theft\s+is\s+a\s+crime
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),
}




# ---------------------------------------------------------------------------
# Refined patterns added after mismatch analysis
# ---------------------------------------------------------------------------

EXPLICIT_IMPERSONATION_PATTERNS.update(
    {
        "fake_support_identity": re.compile(
            r"""
            \b
            fake
            \s+
            (?:
                customer\s+
                |
                technical\s+
                |
                bank\s+
                |
                government\s+
            )?
            (?:
                support\s+
            )?
            (?:
                profile
                |
                account
                |
                agent
                |
                representative
                |
                officer
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    }
)


IDENTITY_CLAIM_PATTERNS.update(
    {
        "official_institution_claim": re.compile(
            r"""
            \b
            (?:
                i\s+am
                |
                i'm
                |
                we\s+are
                |
                this\s+is
            )
            \s+
            (?:
                the\s+
            )?
            (?:
                official
                |
                verified
                |
                authorized
                |
                genuine
            )
            \s+
            (?:
                bank\s+
                |
                government\s+
                |
                company\s+
                |
                customer\s+
                |
                technical\s+
            )?
            (?:
                customer\s+
                |
                technical\s+
            )?
            (?:
                support\s+
            )?
            (?:
                agent
                |
                representative
                |
                officer
                |
                team
                |
                department
                |
                account
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    }
)


DECEPTIVE_REQUEST_PATTERNS.update(
    {
        "expanded_credential_request": re.compile(
            r"""
            \b
            (?:
                ask(?:ed|ing)?\s+for
                |
                request(?:ed|ing)?
                |
                send
                |
                share
                |
                provide
                |
                confirm
                |
                verify
                |
                enter
                |
                submit
            )
            \s+
            (?:
                me\s+to\s+
            )?
            (?:
                your
                |
                my
                |
                the
            )?
            \s*
            (?:
                otp
                |
                password
                |
                passcode
                |
                pin
                |
                cvv
                |
                credentials
                |
                login
                |
                account\s+details
                |
                banking\s+details
                |
                bank\s+details
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),

        "expanded_money_request": re.compile(
            r"""
            \b
            (?:
                ask(?:ed|ing)?\s+(?:me\s+)?to\s+
                |
                request(?:ed|ing)?\s+
                |
                send\s+
                |
                pay\s+
                |
                transfer\s+
                |
                deposit\s+
            )
            (?:
                your\s+
                |
                my\s+
                |
                the\s+
                |
                a\s+
            )?
            (?:
                money
                |
                funds
                |
                payment
                |
                cash
                |
                fee
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    }
)


SAFE_CONTEXT_PATTERNS.update(
    {
        "news_documentary_reporting": re.compile(
            r"""
            \b
            (?:
                article
                |
                news\s+article
                |
                news\s+report
                |
                report
                |
                documentary
                |
                research\s+paper
                |
                academic\s+paper
                |
                study
            )
            \s+
            (?:
                reports?
                |
                describes?
                |
                discusses?
                |
                mentions?
                |
                examines?
                |
                investigates?
                |
                explains?
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),

        "historical_reporting": re.compile(
            r"""
            \b
            (?:
                documentary
                |
                article
                |
                report
                |
                study
            )
            .{0,40}
            \b
            (?:
                historical
                |
                history\s+of
                |
                investigation
                |
                research
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    }
)


def _normalize_text(text: str) -> str:
    return " ".join(
        str(text or "").split()
    )


def _find_signals(
    text: str,
    patterns: dict[str, re.Pattern[str]],
) -> list[str]:
    return [
        signal_name
        for signal_name, pattern in patterns.items()
        if pattern.search(text)
    ]


def _calculate_confidence(
    *,
    explicit_signals: list[str],
    identity_claims: list[str],
    deceptive_requests: list[str],
    safe_signals: list[str],
) -> float:
    if safe_signals:
        return 0.88

    if len(explicit_signals) >= 2:
        return 0.95

    if (
        explicit_signals
        and deceptive_requests
    ):
        return 0.92

    if explicit_signals:
        return 0.86

    if (
        identity_claims
        and deceptive_requests
    ):
        return 0.82

    if identity_claims:
        return 0.58

    return 0.91


def analyze_identity_impersonation(
    text: str,
) -> dict[str, Any]:
    cleaned_text = _normalize_text(text)

    if not cleaned_text:
        return {
            "available": True,
            "category": NORMAL_CATEGORY,
            "detected": False,
            "confidence": 0.50,
            "action": "Allow",
            "human_review_required": False,
            "policy_violation": False,
            "automatic_enforcement_allowed": False,
            "supporting_evidence_only": True,
            "validation_status": (
                "Failed independent recall target"
            ),
            "explicit_signals": [],
            "identity_claim_signals": [],
            "deceptive_request_signals": [],
            "safe_context_signals": [],
            "scam_overlap_detected": False,
            "reason": "No readable text was available.",
        }

    explicit_signals = _find_signals(
        cleaned_text,
        EXPLICIT_IMPERSONATION_PATTERNS,
    )

    identity_claims = _find_signals(
        cleaned_text,
        IDENTITY_CLAIM_PATTERNS,
    )

    deceptive_requests = _find_signals(
        cleaned_text,
        DECEPTIVE_REQUEST_PATTERNS,
    )

    safe_signals = _find_signals(
        cleaned_text,
        SAFE_CONTEXT_PATTERNS,
    )

    scam_overlap_detected = bool(
        deceptive_requests
    )

    strong_impersonation_detected = bool(
        explicit_signals
    )

    combined_deceptive_identity_detected = bool(
        identity_claims
        and deceptive_requests
    )

    detected = bool(
        strong_impersonation_detected
        or combined_deceptive_identity_detected
    )

    raw_signal_confidence = (
        _calculate_confidence(
            explicit_signals=explicit_signals,
            identity_claims=identity_claims,
            deceptive_requests=deceptive_requests,
            safe_signals=safe_signals,
        )
    )

    # The frozen independent challenge produced only
    # 20.83% recall. Text signals therefore cannot
    # receive enforcement-grade confidence.
    confidence = (
        min(raw_signal_confidence, 0.75)
        if detected
        else raw_signal_confidence
    )

    if safe_signals:
        category = NORMAL_CATEGORY
        action = "Allow"
        human_review_required = False
        detected = False

        reason = (
            "Impersonation-related terminology was "
            "detected in an educational, preventative, "
            "condemnatory, fictional, satire, fan, or "
            "clearly declared parody context."
        )

    elif detected:
        category = IDENTITY_CATEGORY
        action = "Refer to human review"
        human_review_required = True

        if scam_overlap_detected:
            reason = (
                "Impersonation or deceptive identity "
                "signals were detected together with a "
                "credential, payment, verification, or "
                "urgency request. Human review is required "
                "to verify identity ownership and determine "
                "whether phishing should remain the primary "
                "category."
            )
        else:
            reason = (
                "Identity theft, account cloning, identity "
                "misuse, or impersonation signals were "
                "detected. Human review is required to "
                "verify identity ownership, authorization, "
                "and possible parody status."
            )

    else:
        category = NORMAL_CATEGORY
        action = "Allow"
        human_review_required = False

        if identity_claims:
            reason = (
                "An identity or authority claim was "
                "detected without enough supporting "
                "evidence of impersonation or deception."
            )
        else:
            reason = (
                "No sufficiently supported identity-theft "
                "or impersonation signal was detected."
            )

    return {
        "available": True,
        "category": category,
        "detected": detected,
        "confidence": confidence,
        "raw_signal_confidence": (
            raw_signal_confidence
        ),
        "action": action,
        "human_review_required": (
            human_review_required
        ),

        # Only a human reviewer can confirm ownership,
        # authorization, deception, or parody status.
        "policy_violation": False,
        "automatic_enforcement_allowed": False,
        "supporting_evidence_only": True,
        "validation_status": (
            "Failed independent recall target"
        ),
        "independent_challenge_version": (
            "2026.08-v1"
        ),
        "independent_challenge_sha256": (
            "62da0f24c7b3a6aaee2e6940179c3f1"
            "a57d04d9b8e995f769f3ff288b05ba904"
        ),
        "independent_precision": 0.8333,
        "independent_recall": 0.2083,
        "independent_f1": 0.3333,

        "explicit_signals": explicit_signals,
        "identity_claim_signals": (
            identity_claims
        ),
        "deceptive_request_signals": (
            deceptive_requests
        ),
        "safe_context_signals": safe_signals,
        "scam_overlap_detected": (
            scam_overlap_detected
        ),
        "reason": reason,
    }