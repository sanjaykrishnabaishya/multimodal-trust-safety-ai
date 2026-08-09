from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


IMPORT_ANCHOR = "from app.services.violent_content_service import ("
IMPORT_BLOCK = """from app.services.targeted_threat_service import (
    analyze_targeted_threat,
)
"""

ANALYSIS_ANCHOR = "    violent_content_analysis = analyze_violent_content(text)\n"
ANALYSIS_REPLACEMENT = ANALYSIS_ANCHOR + (
    "    targeted_threat_analysis = analyze_targeted_threat(text)\n"
)

DECISION_ANCHOR = "    fact_check_result: dict[str, Any]\n"
DECISION_BLOCK = '''    targeted_threat_detected = bool(
        targeted_threat_analysis.get("detected", False)
    )
    targeted_threat_boundary_applied = False

    if targeted_threat_detected:
        threat_category = str(
            targeted_threat_analysis.get(
                "category", "Cyberbullying & Harassment"
            )
        )
        matched_signals.append(
            "targeted_threat_boundary:targeted_intimidation"
        )

        if category in {
            NORMAL_CATEGORY,
            "Violent Content",
            threat_category,
        }:
            category = threat_category
            severity = str(targeted_threat_analysis.get("severity", "High"))
            action = str(
                targeted_threat_analysis.get(
                    "action", "Limit, flag, and send for human review"
                )
            )
            confidence = max(
                confidence,
                float(targeted_threat_analysis.get("confidence", 0.85)),
            )
            human_review_required = True
            reason = str(targeted_threat_analysis.get("reason", reason))
            targeted_threat_boundary_applied = True
        else:
            human_review_required = True
            reason = (
                f"{reason} Targeted physical-intimidation evidence was also "
                "detected, but it did not replace the existing primary category."
            )

'''

SOURCE_ANCHOR = '''            + (
                ["violent_content_specialist"]
                if violent_content_decision_applied
                else []
            )
'''
SOURCE_REPLACEMENT = SOURCE_ANCHOR + '''            + (
                ["targeted_threat_boundary"]
                if targeted_threat_boundary_applied
                else []
            )
'''

RETURN_ANCHOR = '''        "violent_content_specialist_used": (
            violent_content_decision_applied
        ),
'''
RETURN_REPLACEMENT = '''        "targeted_threat_boundary_used": (
            targeted_threat_boundary_applied
        ),
        "targeted_threat": targeted_threat_analysis,
''' + RETURN_ANCHOR


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label} anchor, found {count}.")
    return source.replace(old, new, 1)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    target = root / "backend" / "app" / "services" / "fusion_service.py"
    source = target.read_text(encoding="utf-8")

    if "targeted_threat_boundary_used" in source:
        print("Targeted-threat category boundary is already installed.")
        return

    updated = replace_once(
        source, IMPORT_ANCHOR, IMPORT_BLOCK + IMPORT_ANCHOR, "import"
    )
    updated = replace_once(
        updated, ANALYSIS_ANCHOR, ANALYSIS_REPLACEMENT, "analysis"
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
        + ".before_targeted_threat_boundary_v1_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    shutil.copy2(target, backup)
    target.write_text(updated, encoding="utf-8")

    print("Targeted-threat category boundary integrated successfully.")
    print(f"Updated: {target}")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
