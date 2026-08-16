from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.evaluate_dangerous_content_v6_rc5_live_fusion_contract_v2 import (
    build_cases as build_v2_cases,
)
from scripts.evaluate_dangerous_content_v6_rc5_live_fusion_contract import (
    evaluate_case,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v6_rc5_live_fusion_contract_v3"
    / "report.json"
)


def build_cases():
    cases = deepcopy(build_v2_cases())
    for case in cases:
        if case["case_id"] == "GRAPHIC-DEPICTION-BOUNDARY-001":
            case["allowed_statuses"] = [
                "blocked_by_violent_depiction_boundary",
            ]
    return cases


def main() -> None:
    print("Running the Dangerous Content V6 RC5 live fusion contract V3...")
    print("Independent holdouts are not used.\n")
    rows = [evaluate_case(case) for case in build_cases()]
    for row in rows:
        state = "PASS" if row["passed"] else "FAIL"
        print(
            f"{row['case_id']}: {state} | {row['category']} | "
            f"{row['action']} | RC5: {row['fusion_status']}"
        )

    passed = sum(bool(row["passed"]) for row in rows)
    contract_passed = passed == len(rows)
    report = {
        "contract": "dangerous-content-v6-rc5-live-fusion-v3",
        "records": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "passed_live_fusion_contract": contract_passed,
        "automatic_enforcement_allowed": False,
        "independent_holdouts_used": False,
        "frozen_candidates_modified": False,
        "graphic_depiction_cyberbullying_override_forbidden": True,
        "graphic_depiction_dangerous_content_override_forbidden": True,
        "rows": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("DANGEROUS CONTENT V6 RC5 LIVE FUSION CONTRACT V3")
    print("=" * 60)
    print(f"Records: {len(rows)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(rows) - passed}")
    print(f"Passed live fusion contract: {contract_passed}")
    print("Automatic enforcement allowed: False")
    print("Independent holdouts used: False")
    print("Frozen candidates modified: False")
    print(f"Report: {REPORT_PATH}")
    print("This is an integration contract, not an accuracy benchmark.")
    print(
        "V3 prevents a pure third-person violence depiction from becoming "
        "Cyberbullying or Dangerous Content. Violence coverage remains a "
        "separate component-readiness issue."
    )
    if not contract_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

