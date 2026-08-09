from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path


OLD_BLOCK = '''    try:
        fact_check_result = analyze_fact_check_for_fusion(
            text=text,
            current_category=safely_normalize_category(category),
        )
    except Exception as error:
        fact_check_error = f"{type(error).__name__}: {error}"
        fact_check_result = {
            "fact_check_router_used": True,
            "fact_check_analysis_used": False,
            "decision_override_allowed": False,
            "route_reason": "Fact-check processing failed safely.",
            "category": "",
            "evidence_status": "ERROR",
            "confidence": 0.0,
            "action": "",
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "analysis": {},
        }
'''

NEW_BLOCK = '''    if violent_content_safe_override:
        fact_check_result = {
            "fact_check_router_used": False,
            "fact_check_analysis_used": False,
            "decision_override_allowed": False,
            "route_reason": (
                "Fact-check routing was suppressed for a confirmed violence "
                "metaphor, prevention statement, or documented threat report."
            ),
            "category": "",
            "evidence_status": "NOT_ROUTED",
            "confidence": 0.0,
            "action": "",
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "analysis": {},
        }
    else:
        try:
            fact_check_result = analyze_fact_check_for_fusion(
                text=text,
                current_category=safely_normalize_category(category),
            )
        except Exception as error:
            fact_check_error = f"{type(error).__name__}: {error}"
            fact_check_result = {
                "fact_check_router_used": True,
                "fact_check_analysis_used": False,
                "decision_override_allowed": False,
                "route_reason": "Fact-check processing failed safely.",
                "category": "",
                "evidence_status": "ERROR",
                "confidence": 0.0,
                "action": "",
                "human_review_required": False,
                "automatic_enforcement_allowed": False,
                "analysis": {},
            }
'''


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    target = root / "backend" / "app" / "services" / "fusion_service.py"
    source = target.read_text(encoding="utf-8")
    marker = "Fact-check routing was suppressed for a confirmed violence"

    if marker in source:
        print("Safe violence-context fact-check suppression is already installed.")
        return

    count = source.count(OLD_BLOCK)
    if count != 1:
        raise RuntimeError(
            "Expected exactly one fact-check execution block, "
            f"found {count}."
        )

    updated = source.replace(OLD_BLOCK, NEW_BLOCK, 1)
    ast.parse(updated)

    backup = target.with_name(
        target.name
        + ".before_safe_violence_fact_check_v2_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    shutil.copy2(target, backup)
    target.write_text(updated, encoding="utf-8")

    print("Safe violence-context fact-check suppression installed successfully.")
    print(f"Updated: {target}")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
