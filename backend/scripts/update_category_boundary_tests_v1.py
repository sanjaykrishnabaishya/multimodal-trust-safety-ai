from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


CONSTANT_ANCHOR = 'VIOLENT_CATEGORY = "Violent Content"\n'
CONSTANT_REPLACEMENT = (
    CONSTANT_ANCHOR
    + 'CYBERBULLYING_CATEGORY = "Cyberbullying & Harassment"\n'
)

FUNCTION_START = "def test_review_case_workflow(\n"
FUNCTION_END = "\n\ndef test_unknown_review_case_returns_404(\n"

GRAPHIC_TEST = '''def test_graphic_harm_remains_violent_content(
    client,
):
    response = client.post(
        "/moderation/text",
        json={
            "text": (
                "The image clearly shows a "
                "decapitated body."
            ),
            "source_context": "unknown",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["category"] == VIOLENT_CATEGORY
    assert result["human_review_required"] is True


'''


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    target = root / "backend" / "tests" / "test_api.py"
    source = target.read_text(encoding="utf-8")

    if "def test_graphic_harm_remains_violent_content(" in source:
        print("Category-boundary tests are already updated.")
        return

    if source.count(CONSTANT_ANCHOR) != 1:
        raise RuntimeError("Could not find the Violent Content test constant once.")

    start = source.find(FUNCTION_START)
    end = source.find(FUNCTION_END)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("Could not isolate test_review_case_workflow.")

    function = source[start:end]
    expected_violent_references = function.count("VIOLENT_CATEGORY")
    if expected_violent_references != 3:
        raise RuntimeError(
            "Expected three outdated Violent Content references in the review "
            f"workflow test, found {expected_violent_references}."
        )

    function = function.replace(
        "VIOLENT_CATEGORY",
        "CYBERBULLYING_CATEGORY",
    )
    function = function.replace(
        '"Block and escalate"',
        '"Limit, flag, and send for human review"',
    )

    updated = source.replace(
        CONSTANT_ANCHOR,
        CONSTANT_REPLACEMENT,
        1,
    )

    updated_start = updated.find(FUNCTION_START)
    updated_end = updated.find(FUNCTION_END)
    updated = (
        updated[:updated_start]
        + function
        + "\n\n"
        + GRAPHIC_TEST
        + updated[updated_end + 2 :]
    )

    ast.parse(updated)

    backup = target.with_name(
        target.name
        + ".before_category_boundary_tests_v1_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    shutil.copy2(target, backup)
    target.write_text(updated, encoding="utf-8")

    print("Category-boundary tests updated successfully.")
    print(f"Updated: {target}")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
