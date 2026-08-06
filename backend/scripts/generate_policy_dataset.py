import csv
import sys
from pathlib import Path


BACKEND_DIRECTORY = (
    Path(__file__)
    .resolve()
    .parents[1]
)

PROJECT_DIRECTORY = (
    BACKEND_DIRECTORY.parent
)

sys.path.insert(
    0,
    str(BACKEND_DIRECTORY),
)

from app.policy_config import (  # noqa: E402
    CATEGORY_POLICIES,
    POLICY_VERSION,
    ModerationCategory,
)


OUTPUT_PATH = (
    PROJECT_DIRECTORY
    / "datasets"
    / "policies.csv"
)

FIELD_NAMES = (
    "category",
    "default_severity",
    "default_action",
    "human_review_required",
    "moderation_conditions",
    "allow_conditions",
    "review_conditions",
    "notes",
    "policy_version",
)


def combine_values(
    values: tuple[str, ...],
) -> str:
    return " | ".join(
        value.strip()
        for value in values
        if value.strip()
    )


def build_policy_rows() -> list[
    dict[str, str]
]:
    rows: list[
        dict[str, str]
    ] = []

    for category in (
        ModerationCategory
    ):
        policy = (
            CATEGORY_POLICIES[
                category
            ]
        )

        rows.append(
            {
                "category": (
                    category.value
                ),
                "default_severity": (
                    policy.default_severity
                ),
                "default_action": (
                    policy.default_action
                ),
                "human_review_required": (
                    str(
                        policy
                        .human_review_required
                    )
                ),
                "moderation_conditions": (
                    combine_values(
                        policy
                        .moderation_conditions
                    )
                ),
                "allow_conditions": (
                    combine_values(
                        policy
                        .allow_conditions
                    )
                ),
                "review_conditions": (
                    combine_values(
                        policy
                        .review_conditions
                    )
                ),
                "notes": (
                    combine_values(
                        policy.notes
                    )
                ),
                "policy_version": (
                    POLICY_VERSION
                ),
            }
        )

    return rows


def validate_rows(
    rows: list[
        dict[str, str]
    ],
) -> None:
    expected_count = len(
        ModerationCategory
    )

    if len(rows) != expected_count:
        raise ValueError(
            "Expected "
            f"{expected_count} policies, "
            f"but created {len(rows)}."
        )

    category_names = [
        row["category"]
        for row in rows
    ]

    if (
        len(category_names)
        != len(
            set(
                category_names
            )
        )
    ):
        raise ValueError(
            "Policy categories must "
            "be unique."
        )

    for row in rows:
        if not row[
            "category"
        ].strip():
            raise ValueError(
                "A category name is missing."
            )

        if not row[
            "default_severity"
        ].strip():
            raise ValueError(
                "Default severity is missing "
                f"for {row['category']}."
            )

        if not row[
            "default_action"
        ].strip():
            raise ValueError(
                "Default action is missing "
                f"for {row['category']}."
            )

        if not row[
            "moderation_conditions"
        ].strip():
            raise ValueError(
                "Moderation conditions are "
                f"missing for {row['category']}."
            )


def write_policy_dataset(
    rows: list[
        dict[str, str]
    ],
) -> None:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=(
                FIELD_NAMES
            ),
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


def main() -> None:
    rows = (
        build_policy_rows()
    )

    validate_rows(
        rows
    )

    write_policy_dataset(
        rows
    )

    print(
        "Policy dataset generated "
        "successfully."
    )

    print(
        "Policy version: "
        f"{POLICY_VERSION}"
    )

    print(
        "Categories written: "
        f"{len(rows)}"
    )

    print(
        "Output: "
        f"{OUTPUT_PATH}"
    )

    print()

    for row in rows:
        print(
            "- "
            f"{row['category']}"
        )


if __name__ == "__main__":
    main()