from __future__ import annotations

from pathlib import Path


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    BACKEND_DIRECTORY
    / "app"
    / "services"
    / "identity_impersonation_service.py"
)


OLD_CONFIDENCE_BLOCK = """    confidence = _calculate_confidence(
        explicit_signals=explicit_signals,
        identity_claims=identity_claims,
        deceptive_requests=deceptive_requests,
        safe_signals=safe_signals,
    )
"""


NEW_CONFIDENCE_BLOCK = """    raw_signal_confidence = (
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
"""


OLD_RETURN_START = """    return {
        "available": True,
        "category": category,
        "detected": detected,
        "confidence": confidence,
        "action": action,
"""


NEW_RETURN_START = """    return {
        "available": True,
        "category": category,
        "detected": detected,
        "confidence": confidence,
        "raw_signal_confidence": (
            raw_signal_confidence
        ),
        "action": action,
"""


OLD_POLICY_SECTION = """        # Only a human reviewer can confirm ownership,
        # authorization, deception, or parody status.
        "policy_violation": False,

        "explicit_signals": explicit_signals,
"""


NEW_POLICY_SECTION = """        # Only a human reviewer can confirm ownership,
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
"""


EMPTY_RETURN_MARKER = """            "policy_violation": False,
            "explicit_signals": [],
"""


EMPTY_RETURN_REPLACEMENT = """            "policy_violation": False,
            "automatic_enforcement_allowed": False,
            "supporting_evidence_only": True,
            "validation_status": (
                "Failed independent recall target"
            ),
            "explicit_signals": [],
"""


def _replace_once(
    source: str,
    old: str,
    new: str,
    description: str,
) -> str:
    if new in source:
        return source

    if old not in source:
        raise RuntimeError(
            f"Could not find {description}. "
            "No file was changed."
        )

    return source.replace(
        old,
        new,
        1,
    )


def main() -> None:
    if not SERVICE_PATH.exists():
        raise FileNotFoundError(
            f"File not found: {SERVICE_PATH}"
        )

    source = SERVICE_PATH.read_text(
        encoding="utf-8"
    )

    source = _replace_once(
        source,
        OLD_CONFIDENCE_BLOCK,
        NEW_CONFIDENCE_BLOCK,
        "the confidence calculation",
    )

    source = _replace_once(
        source,
        OLD_RETURN_START,
        NEW_RETURN_START,
        "the main result fields",
    )

    source = _replace_once(
        source,
        OLD_POLICY_SECTION,
        NEW_POLICY_SECTION,
        "the policy-safety fields",
    )

    source = _replace_once(
        source,
        EMPTY_RETURN_MARKER,
        EMPTY_RETURN_REPLACEMENT,
        "the empty-text result fields",
    )

    compile(
        source,
        str(SERVICE_PATH),
        "exec",
    )

    SERVICE_PATH.write_text(
        source,
        encoding="utf-8",
    )

    print(
        "Identity-impersonation detector is now "
        "restricted to supporting evidence."
    )
    print(
        f"Updated: {SERVICE_PATH}"
    )


if __name__ == "__main__":
    main()