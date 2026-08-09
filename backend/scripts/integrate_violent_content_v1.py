from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


IMPORT_ANCHOR = "from app.services.fact_check_fusion_service import ("
IMPORT_BLOCK = """from app.services.violent_content_service import (
    analyze_violent_content,
)
"""

ANALYSIS_ANCHOR = "    identity_impersonation_analysis = (\n"
ANALYSIS_BLOCK = """    violent_content_analysis = analyze_violent_content(text)

"""

DECISION_ANCHOR = "    fact_check_result: dict[str, Any]\n"
DECISION_BLOCK = '''    violent_content_detected = bool(
        violent_content_analysis.get("detected", False)
    )
    violent_content_safe_override = bool(
        violent_content_analysis.get("safe_override_allowed", False)
    )
    violent_content_decision_applied = False

    if violent_content_safe_override and category == "Violent Content":
        category = NORMAL_CATEGORY
        severity = "None"
        action = "Allow"
        confidence = max(0.78, min(confidence, 0.90))
        human_review_required = False
        reason = str(violent_content_analysis.get("reason", reason))
        matched_signals.append(
            "violent_content_specialist:safe_context_override"
        )
        violent_content_decision_applied = True

    if violent_content_detected:
        violence_category = str(
            violent_content_analysis.get("category", "Violent Content")
        )
        violence_signal = (
            "violent_content_specialist:"
            + str(violent_content_analysis.get("decision_type", "detected"))
        )
        matched_signals.append(violence_signal)

        if category in {NORMAL_CATEGORY, violence_category}:
            category = violence_category
            severity = str(violent_content_analysis.get("severity", "High"))
            action = str(
                violent_content_analysis.get("action", "Refer to human review")
            )
            confidence = max(
                confidence,
                float(violent_content_analysis.get("confidence", 0.75)),
            )
            human_review_required = bool(
                violent_content_analysis.get("human_review_required", True)
            )
            reason = str(violent_content_analysis.get("reason", reason))
            violent_content_decision_applied = True
        else:
            human_review_required = True
            reason = (
                f"{reason} The violence specialist also found supporting "
                "evidence, but it did not replace the existing primary category."
            )

'''

SOURCE_ANCHOR = '''            + (
                ["fact_check_rc2"]
                if fact_check_analysis_used
                else []
            )
'''
SOURCE_REPLACEMENT = SOURCE_ANCHOR + '''            + (
                ["violent_content_specialist"]
                if violent_content_decision_applied
                else []
            )
'''

RETURN_ANCHOR = '''        "fact_check_used": fact_check_analysis_used,
        "fact_check": fact_check_result,
'''
RETURN_REPLACEMENT = '''        "violent_content_specialist_used": (
            violent_content_decision_applied
        ),
        "violent_content_specialist": (
            violent_content_analysis
        ),
        "fact_check_used": fact_check_analysis_used,
        "fact_check": fact_check_result,
'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label} anchor, found {count}.")
    return source.replace(old, new, 1)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    target = root / "backend" / "app" / "services" / "fusion_service.py"
    if not target.exists():
        raise FileNotFoundError(target)

    source = target.read_text(encoding="utf-8")
    if "violent_content_specialist_used" in source:
        print("Violent Content V1 fusion integration is already installed.")
        return

    updated = replace_once(
        source, IMPORT_ANCHOR, IMPORT_BLOCK + IMPORT_ANCHOR, "import"
    )
    updated = replace_once(
        updated, ANALYSIS_ANCHOR, ANALYSIS_BLOCK + ANALYSIS_ANCHOR, "analysis"
    )
    updated = replace_once(
        updated, DECISION_ANCHOR, DECISION_BLOCK + DECISION_ANCHOR, "decision"
    )
    updated = replace_once(
        updated, SOURCE_ANCHOR, SOURCE_REPLACEMENT, "decision source"
    )
    updated = replace_once(
        updated, RETURN_ANCHOR, RETURN_REPLACEMENT, "return metadata"
    )

    ast.parse(updated)
    backup = target.with_name(
        target.name
        + ".before_violent_content_v1_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    shutil.copy2(target, backup)
    target.write_text(updated, encoding="utf-8")

    print("Violent Content V1 fusion integration completed successfully.")
    print(f"Updated: {target}")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
