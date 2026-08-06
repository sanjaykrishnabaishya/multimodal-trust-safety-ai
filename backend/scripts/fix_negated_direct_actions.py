from __future__ import annotations

from pathlib import Path


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

MODERATION_SERVICE_PATH = (
    BACKEND_DIRECTORY
    / "app"
    / "services"
    / "moderation_service.py"
)


OLD_FUNCTION = """def has_direct_action(
    normalized_text: str,
) -> bool:
    return bool(
        find_phrases(
            normalized_text,
            DIRECT_HARM_OR_ACTION_PATTERNS,
        )
    )
"""


NEW_FUNCTION = r'''def has_direct_action(
    normalized_text: str,
) -> bool:
    direct_actions_that_remain_harmful = {
        "do not tell",
        "don't tell",
        "keep this secret",
    }

    negation_before_action_pattern = re.compile(
        r"""
        (?:
            \bnever
            |
            \bnot
            |
            \bdo\s+not
            |
            \bdon't
            |
            \bdoes\s+not
            |
            \bis\s+not
            |
            \bisn't
            |
            \bshould\s+not
            |
            \bmust\s+not
            |
            \bavoid
            |
            \bprevent
            |
            \bpreventing
            |
            \bwarn(?:ing|ed)?\s+(?:people\s+)?not\s+to
        )
        (?:\s+\w+){0,2}
        \s*$
        """,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    for action_phrase in (
        DIRECT_HARM_OR_ACTION_PATTERNS
    ):
        normalized_action = normalize_text(
            action_phrase
        )

        if not normalized_action:
            continue

        escaped_action = re.escape(
            normalized_action
        )

        left_boundary = (
            r"(?<!\w)"
            if normalized_action[0].isalnum()
            else ""
        )

        right_boundary = (
            r"(?!\w)"
            if normalized_action[-1].isalnum()
            else ""
        )

        matches = re.finditer(
            left_boundary
            + escaped_action
            + right_boundary,
            normalized_text,
            flags=re.UNICODE,
        )

        for match in matches:
            if (
                normalized_action
                in direct_actions_that_remain_harmful
            ):
                return True

            preceding_text = normalized_text[
                max(0, match.start() - 80):
                match.start()
            ]

            action_is_negated = bool(
                negation_before_action_pattern.search(
                    preceding_text
                )
            )

            if action_is_negated:
                continue

            return True

    return False
'''


def main() -> None:
    if not MODERATION_SERVICE_PATH.exists():
        raise FileNotFoundError(
            f"File not found: "
            f"{MODERATION_SERVICE_PATH}"
        )

    source = MODERATION_SERVICE_PATH.read_text(
        encoding="utf-8"
    )

    if NEW_FUNCTION in source:
        print(
            "Negated direct-action fix is "
            "already installed."
        )
        return

    if OLD_FUNCTION not in source:
        raise RuntimeError(
            "The expected has_direct_action "
            "function was not found. No file "
            "was changed."
        )

    updated_source = source.replace(
        OLD_FUNCTION,
        NEW_FUNCTION,
        1,
    )

    compile(
        updated_source,
        str(MODERATION_SERVICE_PATH),
        "exec",
    )

    MODERATION_SERVICE_PATH.write_text(
        updated_source,
        encoding="utf-8",
    )

    print(
        "Negated direct-action handling "
        "updated successfully."
    )
    print(
        f"Updated: {MODERATION_SERVICE_PATH}"
    )


if __name__ == "__main__":
    main()