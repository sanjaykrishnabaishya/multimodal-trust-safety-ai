"""Validate live Intellectual Property V1 RC1 fusion without holdout data."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.fusion_service import fuse_moderation_decision

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "evaluation" / "intellectual_property" / "v1_rc1_live_fusion_contract" / "report.json"
CASES = [
    {"id": "IP-LIVE-001", "text": "This account uploads the full copyrighted movie without permission.",
     "categories": ["Intellectual Property Infringement"],
     "statuses": ["intellectual_property_review_candidate", "intellectual_property_owner_already_applied"],
     "action": "Restrict distribution and send for qualified human review", "review": True},
    {"id": "IP-LIVE-002", "text": "Evidence indicates this post publishes the source code from commercial software without authorization.",
     "categories": ["Intellectual Property Infringement"],
     "statuses": ["intellectual_property_review_candidate", "intellectual_property_owner_already_applied"],
     "action": "Restrict distribution and send for qualified human review", "review": True},
    {"id": "IP-UNCERTAIN-001", "text": "This upload shares full copies of an ebook, but permission cannot be verified.",
     "categories": ["Uncertain"],
     "statuses": ["ip_rights_or_legal_scope_uncertain_review", "uncertain_owner_already_applied"],
     "action": "Refer to human review", "review": True},
    {"id": "IP-EXCEPTION-001", "text": "This post reproduces the entire copyrighted book without permission for criticism, but fair use is unclear.",
     "categories": ["Uncertain"],
     "statuses": ["ip_rights_or_legal_scope_uncertain_review", "ip_legal_exception_uncertain_review", "uncertain_owner_already_applied"],
     "action": "Refer to human review", "review": True},
    {"id": "IP-LICENSED-SAFE-001", "text": "A valid distribution licence covers this official publisher upload of a copyrighted film.",
     "categories": ["Normal/Ignore", "Uncertain"],
     "statuses": ["authorized_licensed_or_public_domain_no_override"]},
    {"id": "IP-BOUNDARY-SAFE-001", "text": "A critical review uses a brief clip for review from a copyrighted movie and does not substitute for the original.",
     "categories": ["Normal/Ignore", "Uncertain"], "statuses": ["bounded_exception_context_no_override"]},
    {"id": "IP-WEAK-SAFE-001", "text": "A self-reported owner alleges infringement because the picture contains a logo.",
     "categories": ["Normal/Ignore", "Uncertain"], "statuses": ["weak_similarity_or_claim_evidence_no_override"]},
    {"id": "IP-ORDINARY-SAFE-001", "text": "A help page explains a copyright registration guide.",
     "categories": ["Normal/Ignore", "Uncertain"], "statuses": ["ordinary_ip_context_no_override"]},
    {"id": "CHILD-OWNER-001", "text": "This account is requesting an intimate image from a minor.",
     "categories": ["Child Exploitation"], "statuses": ["no_intellectual_property_boundary_override"], "review": True},
    {"id": "MALWARE-OWNER-001", "text": "This upload contains ransomware that encrypts files and demands payment.",
     "categories": ["Malicious Programs"], "statuses": ["no_intellectual_property_boundary_override"], "review": True},
]


def evaluate(case: dict) -> dict:
    result = fuse_moderation_decision(case["text"], "user", ["text"])
    category, action = str(result.get("category", "")), str(result.get("action", ""))
    review = bool(result.get("human_review_required"))
    status = str(result.get("intellectual_property_v1_rc1_fusion_status", ""))
    analysis = result.get("intellectual_property_v1_rc1", {})
    passed = (category in case["categories"] and status in case["statuses"]
              and (not case.get("action") or action == case["action"])
              and (not case.get("review") or review)
              and result.get("intellectual_property_automatic_takedown_allowed") is False
              and result.get("intellectual_property_automatic_enforcement_allowed") is False
              and analysis.get("external_provider_used") is False
              and analysis.get("raw_copyrighted_works_stored") is False)
    return {"case_id": case["id"], "passed": passed, "category": category,
            "action": action, "human_review_required": review, "fusion_status": status}


def main() -> None:
    print("Running the Intellectual Property V1 RC1 live fusion contract...\nIndependent holdouts and raw copyrighted works are not used.\n")
    rows = [evaluate(case) for case in CASES]
    for row in rows:
        print(f"{row['case_id']}: {'PASS' if row['passed'] else 'FAIL'} | {row['category']} | {row['action']} | RC1: {row['fusion_status']}")
    passed = sum(row["passed"] for row in rows)
    ok = passed == len(rows)
    report = {"contract": "intellectual-property-v1-rc1-live-fusion",
              "records": len(rows), "passed": passed, "failed": len(rows) - passed,
              "passed_live_fusion_contract": ok, "automatic_takedown_allowed": False,
              "automatic_enforcement_allowed": False, "independent_holdouts_used": False,
              "raw_copyrighted_works_used": False, "external_provider_used": False,
              "frozen_rc1_modified": False, "rows": rows}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("\n" + "=" * 60 + "\nINTELLECTUAL PROPERTY V1 RC1 LIVE FUSION CONTRACT\n" + "=" * 60)
    print(f"Records: {len(rows)}\nPassed: {passed}\nFailed: {len(rows) - passed}\nPassed live fusion contract: {ok}")
    print(f"Automatic enforcement allowed: False\nIndependent holdouts used: False\nRaw copyrighted works used: False\nExternal provider used: False\nFrozen RC1 modified: False\nReport: {REPORT}")
    print("This is an integration contract, not an accuracy benchmark.")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
