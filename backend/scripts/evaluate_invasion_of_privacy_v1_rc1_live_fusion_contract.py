"""Validate live privacy fusion without holdout data."""
from __future__ import annotations
import json
from pathlib import Path
from app.services.fusion_service import fuse_moderation_decision
ROOT=Path(__file__).resolve().parents[2];REPORT=ROOT/"reports"/"evaluation"/"invasion_of_privacy"/"v1_rc1_live_fusion_contract"/"report.json"
CASES=[
 {"id":"PRIVACY-LIVE-001","text":"This user placed a hidden camera in a bedroom and recorded a resident without consent.","categories":["Invasion of Privacy"],"statuses":["invasion_of_privacy_review_candidate","privacy_owner_already_applied"],"action":"Restrict and send for human review","review":True},
 {"id":"PRIVACY-LIVE-002","text":"This account tracks live location of a tenant without authorization.","categories":["Invasion of Privacy"],"statuses":["invasion_of_privacy_review_candidate","privacy_owner_already_applied"],"action":"Restrict and send for human review","review":True},
 {"id":"PRIVACY-LIVE-003","text":"This user shares a private photo of a guest without consent.","categories":["Invasion of Privacy"],"statuses":["invasion_of_privacy_review_candidate","privacy_owner_already_applied"],"action":"Restrict and send for human review","review":True},
 {"id":"PRIVACY-UNCERTAIN-001","text":"A hidden camera involves a visitor, but consent cannot be verified.","categories":["Uncertain"],"statuses":["privacy_consent_or_evidence_uncertain_review","uncertain_owner_already_applied"],"action":"Refer to human review","review":True},
 {"id":"CONSENT-SAFE-001","text":"Explicit written consent covers this user-owned recording.","categories":["Normal/Ignore","Uncertain"],"statuses":["documented_consent_no_override"]},
 {"id":"REPORT-SAFE-001","text":"Privacy awareness discusses hidden cameras and contains no victim media.","categories":["Normal/Ignore","Uncertain"],"statuses":["safe_reporting_education_no_override"]},
 {"id":"CHILD-OWNER-001","text":"This account is requesting an intimate image from a minor.","categories":["Child Exploitation"],"statuses":["no_privacy_boundary_override"],"review":True},
 {"id":"PRIVATE-OWNER-001","text":"His private email is john.smith@gmail.com.","categories":["Publishing Private Information"],"statuses":["no_privacy_boundary_override"],"review":True},
 {"id":"SPAM-OWNER-001","text":"Your bank account is blocked. Share your password immediately.","categories":["Spam, Scam & Phishing"],"statuses":["no_privacy_boundary_override"]},
 {"id":"LEXICAL-SAFE-001","text":"The developer updates a private variable and package tracking number.","categories":["Normal/Ignore","Uncertain"],"statuses":["ordinary_benign_context_no_override"]}]
def evaluate(case:dict)->dict:
 result=fuse_moderation_decision(case["text"],"user",["text"]);category=str(result.get("category",""));action=str(result.get("action",""));review=bool(result.get("human_review_required"));status=str(result.get("invasion_of_privacy_v1_rc1_fusion_status",""));analysis=result.get("invasion_of_privacy_v1_rc1",{})
 passed=category in case["categories"] and status in case["statuses"] and (not case.get("action") or action==case["action"]) and (not case.get("review") or review) and result.get("invasion_of_privacy_automatic_enforcement_allowed") is False and analysis.get("external_provider_used") is False and analysis.get("real_victim_media_stored") is False
 return {"case_id":case["id"],"passed":passed,"category":category,"action":action,"human_review_required":review,"fusion_status":status}
def main()->None:
 print("Running the Invasion of Privacy V1 RC1 live fusion contract...\nIndependent holdouts and real victim media are not used.\n");rows=[evaluate(c) for c in CASES]
 for row in rows:print(f"{row['case_id']}: {'PASS' if row['passed'] else 'FAIL'} | {row['category']} | {row['action']} | RC1: {row['fusion_status']}")
 passed=sum(r["passed"] for r in rows);ok=passed==len(rows);report={"contract":"invasion-of-privacy-v1-rc1-live-fusion","records":len(rows),"passed":passed,"failed":len(rows)-passed,"passed_live_fusion_contract":ok,"automatic_enforcement_allowed":False,"independent_holdouts_used":False,"real_victim_media_used":False,"external_provider_used":False,"frozen_rc1_modified":False,"rows":rows};REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
 print("\n"+"="*60+f"\nINVASION OF PRIVACY V1 RC1 LIVE FUSION CONTRACT\n"+"="*60+f"\nRecords: {len(rows)}\nPassed: {passed}\nFailed: {len(rows)-passed}\nPassed live fusion contract: {ok}\nAutomatic enforcement allowed: False\nIndependent holdouts used: False\nReal victim media used: False\nExternal provider used: False\nFrozen RC1 modified: False\nReport: {REPORT}\nThis is an integration contract, not an accuracy benchmark.")
 if not ok:raise SystemExit(1)
if __name__=="__main__":main()
