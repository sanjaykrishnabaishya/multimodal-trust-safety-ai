"""Validate live Identity Theft & Impersonation V2 RC5 fusion."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.fusion_service import fuse_moderation_decision

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports/evaluation/identity_theft_impersonation/v2_rc5_live_fusion_contract/report.json"
CASES = [
    {"id": "IDENTITY-LIVE-001", "text": "Someone is impersonating me using a cloned account.",
     "categories": ["Identity Theft & Impersonation"],
     "action": "Restrict account activity and send for identity review", "review": True},
    {"id": "IDENTITY-LIVE-002", "text": "This caller is pretending to be official support and requested account access.",
     "categories": ["Identity Theft & Impersonation"],
     "action": "Restrict account activity and send for identity review", "review": True},
    {"id": "IDENTITY-LIVE-003", "text": "This user uses stolen credentials and accessed the account.",
     "categories": ["Identity Theft & Impersonation"],
     "action": "Restrict account activity and send for identity review", "review": True},
    {"id": "IDENTITY-LIVE-004", "text": "This account uses financial information without authorization and applied for a loan.",
     "categories": ["Identity Theft & Impersonation"],
     "action": "Restrict account activity and send for identity review", "review": True},
    {"id": "IDENTITY-UNCERTAIN-001", "text": "A possible account using login credentials is described while authorization is unknown.",
     "categories": ["Uncertain"], "action": "Refer to human review", "review": True},
    {"id": "IDENTITY-SAFE-001", "text": "Written authorization confirms the owner-approved representative.",
     "categories": ["Normal/Ignore", "Uncertain"]},
    {"id": "IDENTITY-PARODY-001", "text": "A clearly labelled parody account claims no official affiliation.",
     "categories": ["Normal/Ignore", "Uncertain"]},
    {"id": "IDENTITY-WEAK-001", "text": "A page has the same name, but no active misuse or victim impact is described.",
     "categories": ["Normal/Ignore", "Uncertain"]},
    {"id": "SPAM-OWNER-001", "text": "I am the official bank support agent. Send your OTP immediately.",
     "categories": ["Spam, Scam & Phishing"], "review": True},
    {"id": "CHILD-OWNER-001", "text": "This account is requesting an intimate image from a minor.",
     "categories": ["Child Exploitation"], "review": True},
]


def evaluate(case: dict) -> dict:
    result = fuse_moderation_decision(case["text"], "user", ["text"])
    category, action = str(result.get("category", "")), str(result.get("action", ""))
    review = bool(result.get("human_review_required"))
    status = str(result.get("identity_theft_impersonation_v2_rc5_fusion_status", ""))
    analysis = result.get("identity_theft_impersonation_v2_rc5", {})
    passed = (category in case["categories"]
              and (not case.get("action") or action == case["action"])
              and (not case.get("review") or review)
              and result.get("identity_automatic_account_suspension_allowed") is False
              and result.get("identity_automatic_enforcement_allowed") is False
              and analysis.get("external_provider_used") is False
              and analysis.get("real_identity_documents_stored") is False)
    return {"case_id": case["id"], "passed": passed, "category": category,
            "action": action, "human_review_required": review, "fusion_status": status}


def main() -> None:
    print("Running the Identity V2 RC5 live fusion contract...\nIndependent holdouts and real identity documents are not used.\n")
    rows = [evaluate(case) for case in CASES]
    for row in rows:
        print(f"{row['case_id']}: {'PASS' if row['passed'] else 'FAIL'} | {row['category']} | {row['action']} | RC5: {row['fusion_status']}")
    passed = sum(row["passed"] for row in rows); ok = passed == len(rows)
    report = {"contract": "identity-theft-impersonation-v2-rc5-live-fusion",
              "records": len(rows), "passed": passed, "failed": len(rows) - passed,
              "passed_live_fusion_contract": ok,
              "automatic_account_suspension_allowed": False,
              "automatic_enforcement_allowed": False,
              "independent_holdouts_used": False, "real_identity_documents_used": False,
              "raw_credentials_used": False, "external_provider_used": False,
              "frozen_rc5_modified": False, "rows": rows}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("\n" + "=" * 60 + "\nIDENTITY V2 RC5 LIVE FUSION CONTRACT\n" + "=" * 60)
    print(f"Records: {len(rows)}\nPassed: {passed}\nFailed: {len(rows) - passed}\nPassed live fusion contract: {ok}")
    print(f"Automatic enforcement allowed: False\nIndependent holdouts used: False\nReal identity documents used: False\nExternal provider used: False\nFrozen RC5 modified: False\nReport: {REPORT}")
    print("This is an integration contract, not an accuracy benchmark.")
    if not ok: raise SystemExit(1)


if __name__ == "__main__": main()
