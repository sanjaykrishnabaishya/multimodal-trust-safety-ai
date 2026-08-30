"""Freeze development-passing Invasion of Privacy V1 RC1."""

from __future__ import annotations
import csv, hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]; BACKEND=ROOT/"backend"; CANDIDATE="invasion-of-privacy-v1-rc1"
DEST=BACKEND/"storage"/"candidates"/CANDIDATE
DATA=ROOT/"datasets"/"development"/"invasion_of_privacy_v1_rc1"/"development.csv"
REPORT=ROOT/"reports"/"evaluation"/"invasion_of_privacy"/"v1_rc1_development"/"report.json"
SOURCES={
 "source_snapshot/invasion_of_privacy_v1_rc1_service.py":BACKEND/"app"/"services"/"invasion_of_privacy_v1_rc1_service.py",
 "policy_snapshot/invasion_of_privacy_v1_rc1_policy.json":BACKEND/"app"/"evidence"/"invasion_of_privacy_v1_rc1_policy.json",
 "source_snapshot/evaluate_invasion_of_privacy_v1_rc1_development.py":BACKEND/"scripts"/"evaluate_invasion_of_privacy_v1_rc1_development.py",
 "source_snapshot/freeze_invasion_of_privacy_v1_rc1.py":Path(__file__).resolve(),
 "development/development.csv":DATA,"development_evidence/report.json":REPORT}
GATE={"minimum_accuracy":.95,"minimum_privacy_precision":.97,"minimum_privacy_recall":.95,"minimum_safe_specificity":.99,"minimum_f1":.96,"minimum_group_accuracy":.92,"maximum_action_contract_failures":0,"maximum_category_mix_failures":0,"maximum_privacy_storage_failures":0,"maximum_authority_contract_failures":0,"maximum_processing_errors":0,"require_zero_development_overlap":True,"require_frozen_source_hashes":True,"require_no_raw_holdout_storage":True}
def sha(path:Path)->str:
 d=hashlib.sha256()
 with path.open("rb") as h:
  for chunk in iter(lambda:h.read(1024*1024),b""): d.update(chunk)
 return d.hexdigest()
def read(path:Path)->dict[str,Any]: return json.loads(path.read_text(encoding="utf-8"))
def main()->None:
 if DEST.exists(): raise FileExistsError(DEST)
 report=read(REPORT)
 required={"passed_development_gate":True,"records":600,"unique_texts":600,"action_contract_failures":0,"category_mix_failures":0,"privacy_storage_failures":0,"authority_contract_failures":0,"processing_errors":0,"real_victim_media_used":False,"private_identifiers_used":False,"external_provider_used":False,"connected_to_live_moderation":False}
 for key,value in required.items():
  if report.get(key)!=value: raise RuntimeError(f"Development freeze requirement failed: {key}")
 if sha(DATA)!=report.get("dataset_sha256"): raise RuntimeError("Dataset hash mismatch")
 with DATA.open("r",encoding="utf-8",newline="") as h: rows=list(csv.DictReader(h))
 if len(rows)!=600 or len({r["text"] for r in rows})!=600: raise RuntimeError("Dataset uniqueness failed")
 temp=DEST.with_name(DEST.name+".tmp"); temp.mkdir(parents=True)
 try:
  artifacts=[]
  for relative,source in SOURCES.items():
   target=temp/relative; target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
   artifacts.append({"relative_path":relative,"size_bytes":target.stat().st_size,"sha256":sha(target)})
  manifest={"candidate":CANDIDATE,"component":"Invasion of Privacy","candidate_type":"local deterministic consent-aware review router","frozen_at_utc":datetime.now(timezone.utc).isoformat(),"development_gate_passed":True,"development_metrics":{k:report[k] for k in ("records","unique_texts","accuracy","privacy_precision","privacy_recall","safe_specificity","f1","minimum_group_accuracy","action_contract_failures","category_mix_failures","privacy_storage_failures","authority_contract_failures","processing_errors")},"artifacts":artifacts,"independent_gate_frozen_before_holdout":GATE,"independent_holdout_created_before_freeze":False,"independent_holdout_used_before_freeze":False,"independent_holdout_may_modify_rc1":False,"real_victim_media_used":False,"private_identifiers_used":False,"face_recognition_used":False,"appearance_based_identity_consent_or_location_inference_allowed":False,"external_provider_used":False,"external_transmission_allowed":False,"permitted_active_outputs":["Invasion of Privacy","Uncertain"],"required_privacy_action":"Restrict and send for human review","human_review_required":True,"independently_validated":False,"eligible_for_guarded_live_integration":False,"connected_to_live_moderation":False,"automatic_enforcement_allowed":False,"evaluation_reporting_contract":{"store_raw_holdout_text":False,"store_individual_predictions":False,"print_individual_predictions":False,"report_aggregate_metrics_only":True}}
  (temp/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8"); temp.rename(DEST)
 except Exception:
  if temp.exists(): shutil.rmtree(temp)
  raise
 print("INVASION OF PRIVACY V1 RC1 FREEZE\n"+"="*60+f"\nCandidate: {CANDIDATE}\nCandidate directory: {DEST}\nDevelopment gate passed: True\nIndependent holdout created before freeze: False\nIndependent holdout used before freeze: False\nReal victim media used: False\nExternal provider used: False\nConnected to live moderation: False\nAutomatic enforcement allowed: False\nRC1 is frozen for one aggregate-only independent challenge.")
if __name__=="__main__": main()
