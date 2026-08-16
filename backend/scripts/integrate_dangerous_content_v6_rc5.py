from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
BACKEND_DIRECTORY = ROOT_DIRECTORY / "backend"
FUSION_PATH = BACKEND_DIRECTORY / "app" / "services" / "fusion_service.py"
CANDIDATE_DIRECTORY = (
    BACKEND_DIRECTORY
    / "storage"
    / "candidates"
    / "dangerous-content-v6-rc5"
)
EVIDENCE_DIRECTORY = (
    BACKEND_DIRECTORY
    / "app"
    / "evidence"
    / "dangerous-content-v6-rc5"
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label} anchor, found {count}. "
            "No integration changes were written."
        )
    return text.replace(old, new, 1)


def main() -> None:
    manifest = CANDIDATE_DIRECTORY / "manifest.json"
    verdict = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
    if not manifest.is_file() or not verdict.is_file():
        raise FileNotFoundError("Frozen RC5 manifest or independent verdict is missing.")

    original = FUSION_PATH.read_text(encoding="utf-8")
    if "dangerous_content_v6_rc5_fusion" in original:
        raise RuntimeError("Dangerous Content RC5 fusion is already installed.")
    updated = original

    import_anchor = '''from app.services.terrorism_extremism_v6_rc4_fusion import (
    analyze_terrorism_extremism_v6_rc4_for_fusion,
    apply_terrorism_extremism_v6_rc4_fusion,
)
'''
    updated = replace_once(
        updated,
        import_anchor,
        import_anchor
        + '''from app.services.dangerous_content_v6_rc5_fusion import (
    analyze_dangerous_content_v6_rc5_for_fusion,
    apply_dangerous_content_v6_rc5_fusion,
)
''',
        "import",
    )

    analysis_anchor = '''    terrorism_extremism_v6_rc4_analysis = (
        analyze_terrorism_extremism_v6_rc4_for_fusion(
            text,
            input_sources,
        )
    )

'''
    updated = replace_once(
        updated,
        analysis_anchor,
        analysis_anchor
        + '''    dangerous_content_v6_rc5_analysis = (
        analyze_dangerous_content_v6_rc5_for_fusion(
            text,
            input_sources,
        )
    )

''',
        "analysis",
    )

    application_anchor = '''    terrorism_extremism_v6_rc4_applied = bool(
        terrorism_extremism_v6_rc4_fusion["decision_applied"]
    )

'''
    application_block = '''    dangerous_content_v6_rc5_fusion = (
        apply_dangerous_content_v6_rc5_fusion(
            category=category,
            severity=severity,
            action=action,
            confidence=confidence,
            human_review_required=human_review_required,
            reason=reason,
            matched_signals=matched_signals,
            analysis=dangerous_content_v6_rc5_analysis,
        )
    )
    category = str(dangerous_content_v6_rc5_fusion["category"])
    severity = str(dangerous_content_v6_rc5_fusion["severity"])
    action = str(dangerous_content_v6_rc5_fusion["action"])
    confidence = float(dangerous_content_v6_rc5_fusion["confidence"])
    human_review_required = bool(
        dangerous_content_v6_rc5_fusion["human_review_required"]
    )
    reason = str(dangerous_content_v6_rc5_fusion["reason"])
    matched_signals = list(
        dangerous_content_v6_rc5_fusion["matched_signals"]
    )
    dangerous_content_v6_rc5_applied = bool(
        dangerous_content_v6_rc5_fusion["decision_applied"]
    )

'''
    updated = replace_once(
        updated,
        application_anchor,
        application_anchor + application_block,
        "application",
    )

    model_anchor = '''            + (
                ["terrorism_extremism_v6_rc4"]
                if terrorism_extremism_v6_rc4_applied
                else []
            )
'''
    updated = replace_once(
        updated,
        model_anchor,
        model_anchor
        + '''            + (
                ["dangerous_content_v6_rc5"]
                if dangerous_content_v6_rc5_applied
                else []
            )
''',
        "model list",
    )

    result_anchor = '''        "terrorism_extremism_automatic_enforcement_allowed": False,
'''
    updated = replace_once(
        updated,
        result_anchor,
        result_anchor
        + '''        "dangerous_content_v6_rc5_used": (
            dangerous_content_v6_rc5_applied
        ),
        "dangerous_content_v6_rc5": dangerous_content_v6_rc5_analysis,
        "dangerous_content_v6_rc5_fusion_status": (
            dangerous_content_v6_rc5_fusion["fusion_status"]
        ),
        "dangerous_content_automatic_enforcement_allowed": False,
''',
        "result",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = FUSION_PATH.with_name(
        FUSION_PATH.name + f".before_dangerous_content_rc5_{timestamp}"
    )
    shutil.copy2(FUSION_PATH, backup)
    FUSION_PATH.write_text(updated, encoding="utf-8")

    EVIDENCE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, EVIDENCE_DIRECTORY / "manifest.json")
    shutil.copy2(
        verdict,
        EVIDENCE_DIRECTORY / "independent_evaluation_verdict.json",
    )

    print("Dangerous Content V6 RC5 guarded fusion installed.")
    print(f"Updated: {FUSION_PATH}")
    print(f"Backup: {backup}")
    print(f"Packaged evidence: {EVIDENCE_DIRECTORY}")
    print("Automatic enforcement allowed: False")
    print("Permitted output: review-only Dangerous Content")
    print("Unrelated category override allowed: False")


if __name__ == "__main__":
    main()

