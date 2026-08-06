from __future__ import annotations

from pathlib import Path


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

FUSION_SERVICE_PATH = (
    BACKEND_DIRECTORY
    / "app"
    / "services"
    / "fusion_service.py"
)


PRIVATE_DECISION_BLOCK = """    private_information_detected = bool(
        private_information_analysis.get(
            "pii_detected",
            False,
        )
    )

    if private_information_detected:
        private_category = str(
            private_information_analysis.get(
                "category",
                "Publishing Private Information",
            )
        )

        private_confidence = float(
            private_information_analysis.get(
                "confidence",
                0.70,
            )
        )

        private_reason = str(
            private_information_analysis.get(
                "reason",
                (
                    "Actionable private information "
                    "was detected."
                ),
            )
        )

        private_signal = (
            "private_information:"
            + ",".join(
                private_information_analysis.get(
                    "information_types",
                    [],
                )
            )
        )

        matched_signals.append(
            private_signal
        )

        if category == NORMAL_CATEGORY:
            category = private_category
            severity = "High"
            action = "Refer to human review"

            confidence = max(
                confidence,
                private_confidence,
            )

            human_review_required = True
            reason = private_reason

        else:
            human_review_required = True

            reason = (
                f"{reason} Actionable private "
                "information was also detected. "
                "Human review is required before "
                "any final enforcement decision."
            )
"""


def main() -> None:
    if not FUSION_SERVICE_PATH.exists():
        raise FileNotFoundError(
            f"File not found: {FUSION_SERVICE_PATH}"
        )

    source = FUSION_SERVICE_PATH.read_text(
        encoding="utf-8"
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

    # Remove the decision block if it was incorrectly
    # inserted into apply_sms_spam_specialist.
    if PRIVATE_DECISION_BLOCK in before_fuse:
        before_fuse = before_fuse.replace(
            PRIVATE_DECISION_BLOCK,
            "",
            1,
        )

    # Remove any duplicate decision block from the
    # correct function before reinserting it once.
    while PRIVATE_DECISION_BLOCK in fuse_section:
        fuse_section = fuse_section.replace(
            PRIVATE_DECISION_BLOCK,
            "",
            1,
        )

    visual_only_marker = """    visual_only = (
"""

    if visual_only_marker not in fuse_section:
        raise RuntimeError(
            "Could not find the visual-only block "
            "inside fuse_moderation_decision."
        )

    fuse_section = fuse_section.replace(
        visual_only_marker,
        (
            PRIVATE_DECISION_BLOCK
            + "\n"
            + visual_only_marker
        ),
        1,
    )

    repaired_source = (
        before_fuse
        + fuse_section
    )

    compile(
        repaired_source,
        str(FUSION_SERVICE_PATH),
        "exec",
    )

    FUSION_SERVICE_PATH.write_text(
        repaired_source,
        encoding="utf-8",
    )

    print(
        "Private-information fusion block "
        "moved to the correct function."
    )
    print(
        f"Updated: {FUSION_SERVICE_PATH}"
    )


if __name__ == "__main__":
    main()