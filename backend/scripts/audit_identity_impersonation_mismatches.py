from __future__ import annotations

from collections import Counter

from app.services.identity_impersonation_service import (
    IDENTITY_CATEGORY,
    NORMAL_CATEGORY,
    analyze_identity_impersonation,
)

from scripts.benchmark_identity_impersonation import (
    NAMES,
    ORGANIZATIONS,
    NEGATIVE_TEMPLATES,
    POSITIVE_TEMPLATES,
)


def _format_template(
    template: str,
    index: int,
) -> str:
    return template.format(
        name=NAMES[
            index % len(NAMES)
        ],
        organization=ORGANIZATIONS[
            index % len(ORGANIZATIONS)
        ],
    )


def main() -> None:
    false_negative_templates: Counter[str] = (
        Counter()
    )

    false_positive_templates: Counter[str] = (
        Counter()
    )

    print(
        "Auditing identity-impersonation "
        "benchmark mismatches..."
    )

    for index, template in enumerate(
        POSITIVE_TEMPLATES
    ):
        text = _format_template(
            template,
            index,
        )

        result = analyze_identity_impersonation(
            text
        )

        if (
            result.get("category")
            != IDENTITY_CATEGORY
        ):
            false_negative_templates[
                template
            ] += 1

    for index, template in enumerate(
        NEGATIVE_TEMPLATES
    ):
        text = _format_template(
            template,
            index,
        )

        result = analyze_identity_impersonation(
            text
        )

        if (
            result.get("category")
            != NORMAL_CATEGORY
        ):
            false_positive_templates[
                template
            ] += 1

    print()
    print(
        "FALSE-NEGATIVE TEMPLATES"
    )
    print("=" * 60)

    if false_negative_templates:
        for number, template in enumerate(
            false_negative_templates,
            start=1,
        ):
            text = _format_template(
                template,
                number - 1,
            )

            result = (
                analyze_identity_impersonation(
                    text
                )
            )

            print(
                f"{number}. {template}"
            )

            print(
                "   Predicted category: "
                f"{result.get('category')}"
            )

            print(
                "   Confidence: "
                f"{result.get('confidence')}"
            )

            print(
                "   Explicit signals: "
                f"{result.get('explicit_signals')}"
            )

            print(
                "   Identity claims: "
                f"{result.get('identity_claim_signals')}"
            )

            print(
                "   Deceptive requests: "
                f"{result.get('deceptive_request_signals')}"
            )

            print()
    else:
        print("None")

    print()
    print(
        "FALSE-POSITIVE TEMPLATES"
    )
    print("=" * 60)

    if false_positive_templates:
        for number, template in enumerate(
            false_positive_templates,
            start=1,
        ):
            text = _format_template(
                template,
                number - 1,
            )

            result = (
                analyze_identity_impersonation(
                    text
                )
            )

            print(
                f"{number}. {template}"
            )

            print(
                "   Predicted category: "
                f"{result.get('category')}"
            )

            print(
                "   Confidence: "
                f"{result.get('confidence')}"
            )

            print(
                "   Explicit signals: "
                f"{result.get('explicit_signals')}"
            )

            print(
                "   Safe signals: "
                f"{result.get('safe_context_signals')}"
            )

            print()
    else:
        print("None")

    print()
    print(
        "UNIQUE MISMATCH SUMMARY"
    )
    print("=" * 60)

    print(
        "Unique false-negative templates: "
        f"{len(false_negative_templates)}"
    )

    print(
        "Unique false-positive templates: "
        f"{len(false_positive_templates)}"
    )


if __name__ == "__main__":
    main()