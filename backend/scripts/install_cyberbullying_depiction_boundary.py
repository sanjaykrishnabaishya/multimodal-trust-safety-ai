from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
FUSION_PATH = (
    ROOT_DIRECTORY / "backend" / "app" / "services" / "fusion_service.py"
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label} anchor, found {count}. "
            "No boundary changes were written."
        )
    return text.replace(old, new, 1)


def main() -> None:
    original = FUSION_PATH.read_text(encoding="utf-8")
    if "cyberbullying_depiction_boundary_service" in original:
        raise RuntimeError("The cyberbullying depiction boundary is already installed.")
    updated = original

    import_anchor = '''from app.services.cyberbullying_rc2_service import (
    analyze_cyberbullying_rc2,
    apply_cyberbullying_rc2_fusion,
)
'''
    updated = replace_once(
        updated,
        import_anchor,
        import_anchor
        + '''from app.services.cyberbullying_depiction_boundary_service import (
    analyze_cyberbullying_depiction_boundary,
)
''',
        "import",
    )

    analysis_anchor = '''    cyberbullying_rc2_analysis = analyze_cyberbullying_rc2(
        text,
        input_sources,
    )
'''
    updated = replace_once(
        updated,
        analysis_anchor,
        analysis_anchor
        + '''    cyberbullying_depiction_boundary_analysis = (
        analyze_cyberbullying_depiction_boundary(text)
    )
''',
        "analysis",
    )

    safe_anchor = '''            or bool(
                identity_impersonation_analysis.get(
                    "safe_context_signals",
                    [],
                )
            )
'''
    updated = replace_once(
        updated,
        safe_anchor,
        safe_anchor
        + '''            or (
                cyberbullying_rc2_analysis.get("predicted_label")
                == "targeted_threat"
                and bool(
                    cyberbullying_depiction_boundary_analysis.get(
                        "confirmed_third_person_depiction",
                        False,
                    )
                )
            )
''',
        "safe-context boundary",
    )

    result_anchor = '''        "cyberbullying_rc2_fusion_status": (
            cyberbullying_rc2_fusion["fusion_status"]
        ),
'''
    updated = replace_once(
        updated,
        result_anchor,
        result_anchor
        + '''        "cyberbullying_depiction_boundary": (
            cyberbullying_depiction_boundary_analysis
        ),
''',
        "result",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = FUSION_PATH.with_name(
        FUSION_PATH.name + f".before_cyber_depiction_boundary_{timestamp}"
    )
    shutil.copy2(FUSION_PATH, backup)
    FUSION_PATH.write_text(updated, encoding="utf-8")

    print("Cyberbullying third-person depiction boundary installed.")
    print(f"Updated: {FUSION_PATH}")
    print(f"Backup: {backup}")
    print("Frozen Cyberbullying RC2 modified: False")
    print("Frozen Dangerous Content RC5 modified: False")
    print("Direct threats and repeated targeting remain eligible: True")
    print("Automatic enforcement allowed: False")


if __name__ == "__main__":
    main()

