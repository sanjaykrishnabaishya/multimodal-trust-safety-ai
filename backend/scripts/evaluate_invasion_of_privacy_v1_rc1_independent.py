"""Aggregate-only independent challenge for frozen Privacy V1 RC1."""

from __future__ import annotations
import csv, hashlib, json
from collections import defaultdict
from pathlib import Path
from typing import Any
from app.services.invasion_of_privacy_v1_rc1_service import (
 NORMAL_CATEGORY, PRIVACY_ACTION, PRIVACY_CATEGORY, UNCERTAIN_ACTION,
 UNCERTAIN_CATEGORY, analyze_invasion_of_privacy_v1_rc1,
 apply_invasion_of_privacy_v1_rc1_fusion)

ROOT=Path(__file__).resolve().parents[2]; BACKEND=ROOT/"backend"; CANDIDATE="invasion-of-privacy-v1-rc1"
CDIR=BACKEND/"storage"/"candidates"/CANDIDATE; MANIFEST=CDIR/"manifest.json"; VERDICT=CDIR/"independent_evaluation_verdict.json"
DEV=ROOT/"datasets"/"development"/"invasion_of_privacy_v1_rc1"/"development.csv"
REPORT_DIR=ROOT/"reports"/"evaluation"/"invasion_of_privacy"/"v1_rc1_independent"; REPORT=REPORT_DIR/"aggregate_report.json"
LIVE={"source_snapshot/invasion_of_privacy_v1_rc1_service.py":BACKEND/"app"/"services"/"invasion_of_privacy_v1_rc1_service.py","policy_snapshot/invasion_of_privacy_v1_rc1_policy.json":BACKEND/"app"/"evidence"/"invasion_of_privacy_v1_rc1_policy.json","source_snapshot/evaluate_invasion_of_privacy_v1_rc1_development.py":BACKEND/"scripts"/"evaluate_invasion_of_privacy_v1_rc1_development.py","source_snapshot/freeze_invasion_of_privacy_v1_rc1.py":BACKEND/"scripts"/"freeze_invasion_of_privacy_v1_rc1.py"}
OWNER_ACTIONS={"Child Exploitation":"Block and immediately escalate","Sexual Harassment":"Remove and escalate","Publishing Private Information":"Refer to human review","Cyberbullying & Harassment":"Refer to human review","Terrorism & Extremism":"Block and escalate","Spam, Scam & Phishing":"Block, warn, or limit distribution"}
def sha(path:Path)->str:
 d=hashlib.sha256()
 with path.open("rb") as h:
  for chunk in iter(lambda:h.read(1024*1024),b""): d.update(chunk)
 return d.hexdigest()
def th(text:str)->str: return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()
def add(rows:list[dict[str,Any]],group:str,expected:str,subjects:tuple[str,...],templates:tuple[str,...],*,owner:str=NORMAL_CATEGORY,action:str="Allow",review:bool=False)->None:
 for i in range(60): rows.append({"group":group,"text":templates[i%len(templates)].format(subject=subjects[i%len(subjects)],index=i+1),"expected_category":expected,"existing_category":owner,"existing_action":action,"existing_review":review})
def build()->list[dict[str,Any]]:
 rows=[]; people=("an occupant","a visitor","a worker","a resident")
 add(rows,"fresh_covert_private_capture",PRIVACY_CATEGORY,people,(
  "Evidence indicates a covert camera in a private room recorded {subject} without permission; independent {index}.",
  "This user used a concealed camera in a bathroom and {subject} was unaware of the recording; independent {index}.",
  "A credible report says {subject} was secretly recorded inside the home without consent; independent {index}.",
  "This recording filmed through a window into a bedroom against the wishes of {subject}; independent {index}."))
 add(rows,"fresh_audio_eavesdropping",PRIVACY_CATEGORY,people,(
  "This user made a secret audio recording of a private conversation without consent from {subject}; independent {index}.",
  "Evidence indicates a covert microphone inside a private office without permission from {subject}; independent {index}.",
  "A credible allegation says the account eavesdrops on {subject} behind a closed door without consent; independent {index}.",
  "This recording wiretaps a private conversation and {subject} did not agree; independent {index}."))
 add(rows,"fresh_stalking_tracking",PRIVACY_CATEGORY,people,(
  "This account uses a hidden location tracker on {subject} without authorization; independent {index}.",
  "Evidence indicates location surveillance follows every movement of {subject} without permission; independent {index}.",
  "A credible report says the user stalks the person and monitors daily movements of {subject} against their wishes; independent {index}.",
  "This user tracks a private vehicle used by {subject} without consent; independent {index}."))
 add(rows,"fresh_nonconsensual_sharing",PRIVACY_CATEGORY,people,(
  "This account forwards private media showing {subject} without permission; independent {index}.",
  "Evidence indicates an intimate video involving {subject} was shared without consent; independent {index}.",
  "This user publishes a private video of {subject} despite refusing consent; independent {index}.",
  "A credible allegation says this post leaks a private recording of {subject} against their wishes; independent {index}."))
 add(rows,"fresh_consent_location_uncertainty",UNCERTAIN_CATEGORY,people,(
  "A covert camera references {subject}, but consent cannot be verified; independent {index}.",
  "The record tracks live location of {subject}, while authorization cannot be established; independent {index}.",
  "A private recording involves {subject}, but provenance is unknown; independent {index}.",
  "A concealed camera includes {subject}, while location is unclear; independent {index}."))
 add(rows,"fresh_incomplete_evidence",UNCERTAIN_CATEGORY,people,(
  "Unsupported media format; metadata mentions a covert camera and {subject}; independent {index}.",
  "Media could not be decoded while the record tracks live location of {subject}; independent {index}.",
  "Only a thumbnail is available and references a private recording of {subject}; independent {index}.",
  "Visual evidence is incomplete with a concealed gps tracker involving {subject}; independent {index}."))
 add(rows,"fresh_documented_consent",NORMAL_CATEGORY,people,(
  "Explicit written consent covers this consented recording of {subject}; independent safe {index}.",
  "All participants consented and {subject} agreed to recording and distribution; independent safe {index}.",
  "Permission was documented for an authorized production involving {subject}; independent safe {index}.",
  "The owner authorized this user-owned recording featuring {subject}; independent safe {index}."))
 add(rows,"fresh_public_disclosed_context",NORMAL_CATEGORY,people,(
  "A clearly posted surveillance notice discloses a security camera recording {subject}; independent safe {index}.",
  "An ordinary public event shows {subject} in a public street scene; independent safe {index}.",
  "A broadcast interview with consent features {subject}; independent safe {index}.",
  "An official public livestream includes {subject}; independent safe {index}."))
 add(rows,"fresh_safe_reporting_research_fiction",NORMAL_CATEGORY,people,(
  "A prevention campaign discusses covert cameras and contains no victim media; independent safe {index}.",
  "Consent education covers tracking and no active case is described; independent safe {index}.",
  "Academic research quotes private recording language only for analysis and does not identify a real person; independent safe {index}.",
  "A fictional scene mentions a hidden camera; it is fictional and not real; independent safe {index}."))
 add(rows,"fresh_ordinary_technology",NORMAL_CATEGORY,("package tracking","fitness tracking","camera settings","photo backup"),(
  "A help article explains {subject}; independent ordinary {index}.","A customer uses {subject} on a personal device; independent ordinary {index}.","Routine documentation describes {subject}; independent ordinary {index}.","The app provides a benign {subject} feature; independent ordinary {index}."))
 owners=tuple(OWNER_ACTIONS.items())
 for i in range(60):
  owner,action=owners[i%len(owners)]; rows.append({"group":"fresh_established_owner_isolation","text":f"An existing {owner} owner applies without any non-consensual capture or tracking evidence; independent owner {i+1}.","expected_category":owner,"existing_category":owner,"existing_action":action,"existing_review":True})
 add(rows,"fresh_lexical_boundary",NORMAL_CATEGORY,("private variable","tracking number","camera-ready manuscript","stalking horse debate"),(
  "A technical guide contains {subject}; independent lexical {index}.","An ordinary note mentions {subject}; independent lexical {index}.","Documentation explains {subject} without monitoring a person; independent lexical {index}.","A benign article uses {subject}; independent lexical {index}."))
 return rows
def ratio(a:int,b:int)->float:return a/b if b else 0.0
def main()->None:
 if VERDICT.exists(): raise FileExistsError(VERDICT)
 manifest=json.loads(MANIFEST.read_text(encoding="utf-8")); artifacts={str(a["relative_path"]):str(a["sha256"]) for a in manifest["artifacts"]}
 frozen=all(live.is_file() and (CDIR/rel).is_file() and artifacts.get(rel)==sha(live)==sha(CDIR/rel) for rel,live in LIVE.items())
 if not frozen: raise RuntimeError("Frozen source hash verification failed")
 with DEV.open("r",encoding="utf-8",newline="") as h: dev_hashes={th(r["text"]) for r in csv.DictReader(h)}
 challenge=build(); hashes=[th(str(r["text"])) for r in challenge]
 if len(challenge)!=720 or len(set(hashes))!=720: raise RuntimeError("Challenge size/uniqueness failed")
 overlap=set(hashes)&dev_hashes
 if overlap: raise RuntimeError("Development overlap detected")
 tp=tn=fp=fn=0; action_fail=category_fail=privacy_fail=authority_fail=errors=0; groups:dict[str,dict[str,int]]=defaultdict(lambda:{"records":0,"correct":0})
 for row in challenge:
  group,expected=str(row["group"]),str(row["expected_category"]);groups[group]["records"]+=1
  try:
   analysis=analyze_invasion_of_privacy_v1_rc1(str(row["text"]),["text"])
   decision=apply_invasion_of_privacy_v1_rc1_fusion(category=str(row["existing_category"]),severity="None" if row["existing_category"]==NORMAL_CATEGORY else "High",action=str(row["existing_action"]),confidence=.71,human_review_required=bool(row["existing_review"]),reason="Independent baseline.",matched_signals=[],analysis=analysis)
   predicted=str(decision["category"]);correct=predicted==expected;groups[group]["correct"]+=int(correct)
   ea,er=str(row["existing_action"]),bool(row["existing_review"])
   if expected==PRIVACY_CATEGORY:ea,er=PRIVACY_ACTION,True
   elif expected==UNCERTAIN_CATEGORY:ea,er=UNCERTAIN_ACTION,True
   action_fail+=int(decision["action"]!=ea or bool(decision["human_review_required"])!=er or decision["automatic_enforcement_allowed"] is not False);category_fail+=int(not correct)
   privacy_fail+=int(analysis["real_victim_media_stored"] is not False or analysis["private_identifiers_stored"] is not False)
   authority_fail+=int(any(analysis[k] is not False for k in ("face_recognition_used","identity_inference_from_appearance_allowed","consent_inference_from_appearance_allowed","private_location_inference_from_appearance_allowed","external_provider_used","external_transmission_allowed")))
   ep,pp=expected==PRIVACY_CATEGORY,predicted==PRIVACY_CATEGORY
   if ep and pp:tp+=1
   elif ep:fn+=1
   elif pp:fp+=1
   else:tn+=1
  except Exception:errors+=1
 total=len(challenge);accuracy=ratio(tp+tn,total);precision=ratio(tp,tp+fp);recall=ratio(tp,tp+fn);specificity=ratio(tn,tn+fp);f1=ratio(2*precision*recall,precision+recall)
 gr={g:{**v,"accuracy":ratio(v["correct"],v["records"])} for g,v in sorted(groups.items())};minimum=min(v["accuracy"] for v in gr.values());gate=manifest["independent_gate_frozen_before_holdout"]
 gates={"frozen_source_hashes_verified":frozen,"zero_development_overlap":not overlap,"accuracy":accuracy>=gate["minimum_accuracy"],"privacy_precision":precision>=gate["minimum_privacy_precision"],"privacy_recall":recall>=gate["minimum_privacy_recall"],"safe_specificity":specificity>=gate["minimum_safe_specificity"],"f1":f1>=gate["minimum_f1"],"minimum_group_accuracy":minimum>=gate["minimum_group_accuracy"],"action_contract":action_fail<=gate["maximum_action_contract_failures"],"category_mix_contract":category_fail<=gate["maximum_category_mix_failures"],"privacy_storage_contract":privacy_fail<=gate["maximum_privacy_storage_failures"],"authority_contract":authority_fail<=gate["maximum_authority_contract_failures"],"processing_contract":errors<=gate["maximum_processing_errors"]};passed=all(gates.values())
 report={"candidate":CANDIDATE,"challenge_version":"2026.08-invasion-of-privacy-v1-rc1-independent","challenge_sha256":hashlib.sha256("".join(hashes).encode()).hexdigest(),"records":total,"unique_texts":len(set(hashes)),"positive_records":sum(r["expected_category"]==PRIVACY_CATEGORY for r in challenge),"negative_or_boundary_records":sum(r["expected_category"]!=PRIVACY_CATEGORY for r in challenge),"development_overlap":len(overlap),"accuracy":accuracy,"privacy_precision":precision,"privacy_recall":recall,"safe_specificity":specificity,"f1":f1,"minimum_group_accuracy":minimum,"false_positives":fp,"false_negatives":fn,"action_contract_failures":action_fail,"category_mix_failures":category_fail,"privacy_storage_failures":privacy_fail,"authority_contract_failures":authority_fail,"processing_errors":errors,"group_results":gr,"gates":gates,"passed_synthetic_independent_readiness_gate":passed,"eligible_for_guarded_live_integration":passed,"automatic_enforcement_allowed":False,"connected_to_live_moderation":False,"raw_challenge_text_stored":False,"individual_predictions_stored":False,"real_victim_media_used":False,"private_identifiers_used":False,"external_provider_used":False,"candidate_may_be_modified_using_this_holdout":False,"synthetic_evidence_only":True,"external_real_world_accuracy":False}
 verdict={k:v for k,v in report.items() if k not in {"group_results","positive_records","negative_or_boundary_records","false_positives","false_negatives"}};REPORT_DIR.mkdir(parents=True,exist_ok=True);REPORT.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");VERDICT.write_text(json.dumps(verdict,indent=2)+"\n",encoding="utf-8")
 print("INVASION OF PRIVACY V1 RC1 INDEPENDENT CHALLENGE\n"+"="*60+f"\nCandidate: {CANDIDATE}\nRecords: {total}\nPositive records: {report['positive_records']}\nNegative/boundary records: {report['negative_or_boundary_records']}\nDevelopment overlap: {len(overlap)}\nAccuracy: {accuracy:.2%}\nPrivacy precision: {precision:.2%}\nPrivacy recall: {recall:.2%}\nSafe specificity: {specificity:.2%}\nF1: {f1:.2%}\nMinimum group accuracy: {minimum:.2%}\nAction failures: {action_fail}\nCategory failures: {category_fail}\nPrivacy-storage failures: {privacy_fail}\nAuthority failures: {authority_fail}\nProcessing errors: {errors}\n\nGROUP RESULTS\n"+"-"*60)
 for group,values in gr.items():print(f"{group}: {values['correct']}/{values['records']} ({values['accuracy']:.2%})")
 print(f"\nPassed synthetic independent readiness gate: {passed}\nEligible for guarded live integration: {passed}\nAutomatic enforcement allowed: False\nConnected to live moderation: False\nReport: {REPORT}\nVerdict: {VERDICT}\nNo raw challenge text or individual predictions were stored or printed.\nNo real victim media or private identifiers were used.\nThis holdout may not be used to modify RC1.")
 if not passed:raise SystemExit(1)
if __name__=="__main__":main()
