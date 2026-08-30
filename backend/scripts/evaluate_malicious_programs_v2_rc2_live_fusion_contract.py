"""Validate guarded Malicious Programs V2 RC2 live fusion boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.fusion_service import fuse_moderation_decision


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "malicious_programs"
    / "v2_rc2_live_fusion_contract"
    / "report.json"
)
CASES: list[dict[str, Any]] = [
    {
        "case_id": "MALICIOUS-LIVE-001",
        "text": "This upload distributes the malware to victim devices.",
        "categories": ["Malicious Programs"],
        "statuses": [
            "malicious_program_security_review_candidate",
            "malicious_program_owner_already_applied",
        ],
        "malicious_case": True,
    },
    {
        "case_id": "MALICIOUS-LIVE-002",
        "text": "Ransomware was published by the account for victim systems.",
        "categories": ["Malicious Programs"],
        "statuses": [
            "rc2_word_order_malicious_security_review_candidate",
            "malicious_program_owner_already_applied",
        ],
        "malicious_case": True,
    },
    {
        "case_id": "MALICIOUS-LIVE-003",
        "text": "A credential stealer is hosted for download by unrelated users.",
        "categories": ["Malicious Programs"],
        "statuses": [
            "rc2_word_order_malicious_security_review_candidate",
            "malicious_program_owner_already_applied",
        ],
        "malicious_case": True,
    },
    {
        "case_id": "ARTIFACT-UNCERTAIN-001",
        "text": (
            "This attachment is an unknown executable attachment and its "
            "purpose is unknown."
        ),
        "categories": ["Uncertain"],
        "statuses": [
            "malicious_capability_uncertain_review",
            "uncertain_owner_already_applied",
        ],
        "safe_pair": True,
    },
    {
        "case_id": "DEFENSIVE-SAFE-001",
        "text": (
            "A defensive malware analysis says ransomware was installed; "
            "it contains no executable payload."
        ),
        "categories": ["Normal/Ignore", "Uncertain"],
        "statuses": ["defensive_security_context_no_override"],
        "safe_pair": True,
    },
    {
        "case_id": "ADMIN-SAFE-001",
        "text": "A legitimate remote administration tool supports approved users.",
        "categories": ["Normal/Ignore", "Uncertain"],
        "statuses": ["benign_software_context_no_override"],
        "safe_pair": True,
    },
    {
        "case_id": "CHILD-OWNER-001",
        "text": "This account is requesting an intimate image from a minor.",
        "categories": ["Child Exploitation"],
        "statuses": ["no_malicious_program_boundary_override"],
        "review": True,
    },
    {
        "case_id": "ILLEGAL-OWNER-001",
        "text": (
            "A supplier offers controlled substances with courier delivery "
            "after payment."
        ),
        "categories": ["Illegal Activities"],
        "statuses": ["no_malicious_program_boundary_override"],
        "review": True,
    },
    {
        "case_id": "SPAM-OWNER-001",
        "text": (
            "Your bank account is blocked. Share your password immediately."
        ),
        "categories": ["Spam, Scam & Phishing"],
        "statuses": ["no_malicious_program_boundary_override"],
    },
    {
        "case_id": "PRIVACY-OWNER-001",
        "text": (
            "This user placed a hidden camera in a bedroom and recorded a "
            "resident without consent."
        ),
        "categories": ["Invasion of Privacy"],
        "statuses": ["no_malicious_program_boundary_override"],
        "review": True,
    },
]


def _valid_safe_pair(category: str, action: str, review: bool) -> bool:
    if category == "Normal/Ignore":
        return action == "Allow" and review is False
    if category == "Uncertain":
        return action == "Refer to human review" and review is True
    return False


def _evaluate(case: dict[str, Any]) -> dict[str, Any]:
    result = fuse_moderation_decision(case["text"], "user", ["text"])
    category = str(result.get("category", ""))
    action = str(result.get("action", ""))
    review = bool(result.get("human_review_required"))
    status = str(
        result.get("malicious_programs_v2_rc2_fusion_status", "")
    )
    analysis = result.get("malicious_programs_v2_rc2", {})
    passed = all(
        (
            category in case["categories"],
            status in case["statuses"],
            not case.get("review") or review is True,
            not case.get("safe_pair")
            or _valid_safe_pair(category, action, review),
            not case.get("malicious_case")
            or (
                action == "Block and send for security review"
                and review is True
            ),
            result.get(
                "malicious_programs_automatic_enforcement_allowed"
            )
            is False,
            analysis.get("code_executed") is False,
            analysis.get("archive_unpacked") is False,
            analysis.get("payload_stored") is False,
            analysis.get("external_provider_used") is False,
            analysis.get("readiness", {}).get("ready") is True,
        )
    )
    return {
        "case_id": case["case_id"],
        "passed": passed,
        "category": category,
        "action": action,
        "human_review_required": review,
        "fusion_status": status,
    }


def main() -> None:
    print("Running the Malicious Programs V2 RC2 live fusion contract...")
    print("Independent holdouts and executable payloads are not used.\n")
    rows = [_evaluate(case) for case in CASES]
    for row in rows:
        state = "PASS" if row["passed"] else "FAIL"
        print(
            f"{row['case_id']}: {state} | {row['category']} | "
            f"{row['action']} | RC2: {row['fusion_status']}"
        )
    passed_count = sum(row["passed"] for row in rows)
    report = {
        "contract": "malicious-programs-v2-rc2-live-fusion",
        "records": len(rows),
        "passed": passed_count,
        "failed": len(rows) - passed_count,
        "passed_live_fusion_contract": passed_count == len(rows),
        "automatic_enforcement_allowed": False,
        "independent_holdouts_used": False,
        "executable_payloads_used": False,
        "code_executed": False,
        "archives_unpacked": False,
        "payloads_stored": False,
        "external_provider_used": False,
        "frozen_candidates_modified": False,
        "rows": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print("\n" + "=" * 60)
    print("MALICIOUS PROGRAMS V2 RC2 LIVE FUSION CONTRACT")
    print("=" * 60)
    print(f"Records: {len(rows)}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {len(rows) - passed_count}")
    print(
        "Passed live fusion contract: "
        f"{report['passed_live_fusion_contract']}"
    )
    print("Automatic enforcement allowed: False")
    print("Independent holdouts used: False")
    print("Executable payloads used or executed: False")
    print("Frozen candidates modified: False")
    print(f"Report: {REPORT_PATH}")
    print("This is an integration contract, not an accuracy benchmark.")
    if not report["passed_live_fusion_contract"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
