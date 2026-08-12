from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FUSION_PATH = ROOT / "backend" / "app" / "services" / "fusion_service.py"
CANDIDATE = (
    ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "religiously-offensive-v7-rc6"
)
MANIFEST_PATH = CANDIDATE / "manifest.json"
VERDICT_PATH = CANDIDATE / "independent_evaluation_verdict.json"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label} marker, found {count}.")
    return source.replace(old, new, 1)


def verify_candidate() -> None:
    for path in (FUSION_PATH, MANIFEST_PATH, VERDICT_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required integration file is missing: {path}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    if manifest.get("candidate") != "religiously-offensive-v7-rc6":
        raise RuntimeError("Unexpected RC6 manifest.")
    if verdict.get("candidate") != "religiously-offensive-v7-rc6":
        raise RuntimeError("Unexpected RC6 verdict.")
    if verdict.get("passed_independent_readiness_gate") is not True:
        raise RuntimeError("RC6 failed independent validation.")
    if verdict.get("eligible_for_guarded_live_integration") is not True:
        raise RuntimeError("RC6 is not eligible for guarded integration.")
    if verdict.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC6 enforcement contract is invalid.")
    if manifest.get("follower_boundary_output_enabled") is not False:
        raise RuntimeError("RC6 cannot own the protected-follower boundary.")


def main() -> None:
    verify_candidate()
    source = FUSION_PATH.read_text(encoding="utf-8")
    install_marker = "religiously_offensive_v7_rc6_fusion_status"
    if install_marker in source:
        print("Religiously Offensive Content V7 RC6 fusion is already installed.")
        print(f"Unchanged: {FUSION_PATH}")
        return

    source = replace_once(
        source,
        """from app.services.hate_speech_v7_service import (
    analyze_hate_speech_v7,
    apply_hate_speech_v7_fusion,
)
""",
        """from app.services.hate_speech_v7_service import (
    analyze_hate_speech_v7,
    apply_hate_speech_v7_fusion,
)
from app.services.religiously_offensive_v7_rc6_fusion import (
    analyze_religiously_offensive_v7_rc6_for_fusion,
    apply_religiously_offensive_v7_rc6_fusion,
)
""",
        "import",
    )
    source = replace_once(
        source,
        """    hate_speech_v7_analysis = analyze_hate_speech_v7(
        text,
        input_sources,
    )

    identity_impersonation_analysis = (
""",
        """    hate_speech_v7_analysis = analyze_hate_speech_v7(
        text,
        input_sources,
    )
    religiously_offensive_v7_rc6_analysis = (
        analyze_religiously_offensive_v7_rc6_for_fusion(
            text,
            input_sources,
        )
    )

    identity_impersonation_analysis = (
""",
        "analysis",
    )
    source = replace_once(
        source,
        """    hate_speech_v7_applied = bool(
        hate_speech_v7_fusion["decision_applied"]
    )

    fact_check_result: dict[str, Any]
""",
        """    hate_speech_v7_applied = bool(
        hate_speech_v7_fusion["decision_applied"]
    )

    religiously_offensive_v7_rc6_fusion = (
        apply_religiously_offensive_v7_rc6_fusion(
            category=category,
            severity=severity,
            action=action,
            confidence=confidence,
            human_review_required=human_review_required,
            reason=reason,
            matched_signals=matched_signals,
            analysis=religiously_offensive_v7_rc6_analysis,
            safe_context_confirmed=(
                safe_context_detected
                and not direct_action_detected
            ),
        )
    )
    category = str(religiously_offensive_v7_rc6_fusion["category"])
    severity = str(religiously_offensive_v7_rc6_fusion["severity"])
    action = str(religiously_offensive_v7_rc6_fusion["action"])
    confidence = float(religiously_offensive_v7_rc6_fusion["confidence"])
    human_review_required = bool(
        religiously_offensive_v7_rc6_fusion["human_review_required"]
    )
    reason = str(religiously_offensive_v7_rc6_fusion["reason"])
    matched_signals = list(
        religiously_offensive_v7_rc6_fusion["matched_signals"]
    )
    religiously_offensive_v7_rc6_applied = bool(
        religiously_offensive_v7_rc6_fusion["decision_applied"]
    )

    fact_check_result: dict[str, Any]
""",
        "fusion application",
    )
    source = replace_once(
        source,
        """            + (
                ["hate_speech_v7_rc1"]
                if hate_speech_v7_applied
                else []
            )
            + (
                ["spam_dictionary"]
""",
        """            + (
                ["hate_speech_v7_rc1"]
                if hate_speech_v7_applied
                else []
            )
            + (
                ["religiously_offensive_v7_rc6"]
                if religiously_offensive_v7_rc6_applied
                else []
            )
            + (
                ["spam_dictionary"]
""",
        "decision source",
    )
    source = replace_once(
        source,
        """        "hate_speech_v7_fusion_status": (
            hate_speech_v7_fusion["fusion_status"]
        ),
        "cyberbullying_rc2_used": cyberbullying_rc2_applied,
""",
        """        "hate_speech_v7_fusion_status": (
            hate_speech_v7_fusion["fusion_status"]
        ),
        "religiously_offensive_v7_rc6_used": (
            religiously_offensive_v7_rc6_applied
        ),
        "religiously_offensive_v7_rc6": (
            religiously_offensive_v7_rc6_analysis
        ),
        "religiously_offensive_v7_rc6_fusion_status": (
            religiously_offensive_v7_rc6_fusion["fusion_status"]
        ),
        "cyberbullying_rc2_used": cyberbullying_rc2_applied,
""",
        "return metadata",
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = FUSION_PATH.with_name(f"fusion_service.py.before_religious_rc6_{stamp}")
    shutil.copy2(FUSION_PATH, backup)
    FUSION_PATH.write_text(source, encoding="utf-8")
    print("Religiously Offensive Content V7 RC6 guarded fusion installed.")
    print(f"Updated: {FUSION_PATH}")
    print(f"Backup: {backup}")
    print("Automatic enforcement allowed: False")
    print("Follower-targeted Hate ownership: Hate Speech & Discrimination V7")
    print("Unrelated category override allowed: False")


if __name__ == "__main__":
    main()
