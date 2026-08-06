from __future__ import annotations

from pathlib import Path


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

FUSION_SERVICE_PATH = (
    BACKEND_DIRECTORY
    / "app"
    / "services"
    / "fusion_service.py"
)


IDENTITY_IMPORT = """from app.services.identity_impersonation_service import (
    analyze_identity_impersonation,
)
"""


IDENTITY_ANALYSIS_BLOCK = """
    identity_impersonation_analysis = (
        analyze_identity_impersonation(
            text
        )
    )
"""


IDENTITY_DECISION_BLOCK = """
    identity_impersonation_detected = bool(
        identity_impersonation_analysis.get(
            "detected",
            False,
        )
    )

    if identity_impersonation_detected:
        identity_category = str(
            identity_impersonation_analysis.get(
                "category",
                (
                    "Identity Theft & "
                    "Impersonation"
                ),
            )
        )

        identity_confidence = min(
            0.75,
            float(
                identity_impersonation_analysis.get(
                    "confidence",
                    0.60,
                )
            ),
        )

        identity_signal = (
            "identity_impersonation:"
            + ",".join(
                identity_impersonation_analysis.get(
                    "explicit_signals",
                    [],
                )
                + identity_impersonation_analysis.get(
                    "identity_claim_signals",
                    [],
                )
            )
        )

        matched_signals.append(
            identity_signal
        )

        identity_overlaps_with_scam = bool(
            identity_impersonation_analysis.get(
                "scam_overlap_detected",
                False,
            )
        )

        if category == NORMAL_CATEGORY:
            category = identity_category
            severity = "High"
            action = "Refer to human review"
            confidence = identity_confidence
            human_review_required = True

            reason = (
                "Text signals suggest possible "
                "identity theft or impersonation. "
                "The text-only specialist failed "
                "its independent recall target, so "
                "this is supporting evidence only. "
                "Human review must verify identity "
                "ownership, authorization, deception, "
                "and parody status."
            )

        elif (
            category == SPAM_CATEGORY
            and identity_overlaps_with_scam
        ):
            human_review_required = True

            reason = (
                f"{reason} Possible impersonation "
                "signals were also detected, but "
                "Spam, Scam & Phishing remains the "
                "primary category because the content "
                "requests credentials, money, payment, "
                "or verification."
            )

        else:
            human_review_required = True

            reason = (
                f"{reason} Supporting identity-"
                "impersonation signals were also "
                "detected. Human review is required."
            )
"""


IDENTITY_RETURN_FIELDS = """        "identity_impersonation_detector_used": (
            identity_impersonation_detected
        ),
        "identity_impersonation": (
            identity_impersonation_analysis
        ),
"""


def _insert_after(
    source: str,
    marker: str,
    insertion: str,
    identifier: str,
) -> str:
    if identifier in source:
        return source

    if marker not in source:
        raise RuntimeError(
            f"Could not find insertion marker "
            f"for {identifier}."
        )

    return source.replace(
        marker,
        marker + "\n" + insertion,
        1,
    )


def main() -> None:
    if not FUSION_SERVICE_PATH.exists():
        raise FileNotFoundError(
            f"File not found: "
            f"{FUSION_SERVICE_PATH}"
        )

    source = FUSION_SERVICE_PATH.read_text(
        encoding="utf-8"
    )

    original_source = source

    private_import_marker = """from app.services.private_information_service import (
    analyze_private_information,
)
"""

    source = _insert_after(
        source=source,
        marker=private_import_marker,
        insertion=IDENTITY_IMPORT,
        identifier=(
            "analyze_identity_impersonation"
        ),
    )

    fuse_marker = (
        "def fuse_moderation_decision("
    )

    if fuse_marker not in source:
        raise RuntimeError(
            "Could not find "
            "fuse_moderation_decision."
        )

    fuse_position = source.index(
        fuse_marker
    )

    before_fuse = source[:fuse_position]
    fuse_section = source[fuse_position:]

    baseline_marker = """    baseline = moderate_text(
        text=text,
        source_context=source_context,
    )
"""

    if (
        "identity_impersonation_analysis ="
        not in fuse_section
    ):
        if baseline_marker not in fuse_section:
            raise RuntimeError(
                "Could not find the baseline "
                "analysis marker."
            )

        fuse_section = fuse_section.replace(
            baseline_marker,
            (
                baseline_marker
                + "\n"
                + IDENTITY_ANALYSIS_BLOCK
            ),
            1,
        )

    visual_marker = """    visual_only = (
"""

    if (
        "identity_impersonation_detected ="
        not in fuse_section
    ):
        if visual_marker not in fuse_section:
            raise RuntimeError(
                "Could not find the visual-only "
                "marker inside the fusion function."
            )

        fuse_section = fuse_section.replace(
            visual_marker,
            (
                IDENTITY_DECISION_BLOCK
                + "\n"
                + visual_marker
            ),
            1,
        )

    private_decision_source = """            + (
                ["private_information_detector"]
                if private_information_detected
                else []
            )
"""

    identity_decision_source = """            + (
                ["private_information_detector"]
                if private_information_detected
                else []
            )
            + (
                ["identity_impersonation_detector"]
                if identity_impersonation_detected
                else []
            )
"""

    if (
        '"identity_impersonation_detector"'
        not in fuse_section
    ):
        if private_decision_source not in fuse_section:
            raise RuntimeError(
                "Could not find the private-"
                "information decision-source block."
            )

        fuse_section = fuse_section.replace(
            private_decision_source,
            identity_decision_source,
            1,
        )

    private_return_marker = """        "private_information_detector_used": (
"""

    if (
        '"identity_impersonation_detector_used"'
        not in fuse_section
    ):
        if private_return_marker not in fuse_section:
            raise RuntimeError(
                "Could not find the private-"
                "information return fields."
            )

        fuse_section = fuse_section.replace(
            private_return_marker,
            (
                IDENTITY_RETURN_FIELDS
                + private_return_marker
            ),
            1,
        )

    updated_source = (
        before_fuse
        + fuse_section
    )

    if updated_source == original_source:
        print(
            "Identity-impersonation fusion "
            "integration is already installed."
        )
        return

    compile(
        updated_source,
        str(FUSION_SERVICE_PATH),
        "exec",
    )

    FUSION_SERVICE_PATH.write_text(
        updated_source,
        encoding="utf-8",
    )

    print(
        "Identity-impersonation supporting "
        "evidence integrated successfully."
    )
    print(
        f"Updated: {FUSION_SERVICE_PATH}"
    )


if __name__ == "__main__":
    main()