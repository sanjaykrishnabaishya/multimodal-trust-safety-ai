from __future__ import annotations
import pytest
from app.services.invasion_of_privacy_v1_rc1_service import (
 PRIVACY_ACTION,PRIVACY_CATEGORY,analyze_invasion_of_privacy_v1_rc1,
 apply_invasion_of_privacy_v1_rc1_fusion)
def apply(category:str,action:str,analysis:dict)->dict:
 return apply_invasion_of_privacy_v1_rc1_fusion(category=category,severity="None" if category=="Normal/Ignore" else "High",action=action,confidence=.70,human_review_required=category!="Normal/Ignore",reason="Existing.",matched_signals=[],analysis=analysis)
@pytest.mark.parametrize("text",[
 "This user placed a hidden camera in a bedroom and recorded a resident without consent.",
 "Evidence indicates a covert microphone recorded a private conversation without permission.",
 "This account tracks live location of a tenant without authorization.",
 "This user shares a private photo of a guest without consent."])
def test_credible_privacy_intrusion_routes_to_review(text:str)->None:
 analysis=analyze_invasion_of_privacy_v1_rc1(text,["text"]);decision=apply("Normal/Ignore","Allow",analysis)
 assert decision["category"]==PRIVACY_CATEGORY;assert decision["action"]==PRIVACY_ACTION;assert decision["human_review_required"] is True;assert decision["automatic_enforcement_allowed"] is False
 assert analysis["external_provider_used"] is False;assert analysis["real_victim_media_stored"] is False
def test_uncertain_consent_fails_closed_to_review()->None:
 analysis=analyze_invasion_of_privacy_v1_rc1("A hidden camera involves a visitor, but consent cannot be verified.",["visual_description"]);decision=apply("Normal/Ignore","Allow",analysis)
 assert decision["category"]=="Uncertain";assert decision["action"]=="Refer to human review"
 assert analysis["consent_inference_from_appearance_allowed"] is False
def test_documented_consent_is_no_override()->None:
 analysis=analyze_invasion_of_privacy_v1_rc1("Explicit written consent covers this user-owned recording.",["text"]);decision=apply("Normal/Ignore","Allow",analysis)
 assert decision["category"]=="Normal/Ignore";assert analysis["fusion_status"]=="documented_consent_no_override"
def test_safe_reporting_is_no_override()->None:
 analysis=analyze_invasion_of_privacy_v1_rc1("Privacy awareness discusses hidden cameras and contains no victim media.",["text"]);decision=apply("Normal/Ignore","Allow",analysis)
 assert decision["category"]=="Normal/Ignore";assert analysis["fusion_status"]=="safe_reporting_education_no_override"
def test_unrelated_established_owner_is_preserved()->None:
 analysis=analyze_invasion_of_privacy_v1_rc1("This account tracks live location without consent.",["text"]);decision=apply("Child Exploitation","Block and immediately escalate",analysis)
 assert decision["category"]=="Child Exploitation";assert decision["fusion_status"]=="blocked_by_established_category_owner"
def test_appearance_and_external_authority_are_disabled()->None:
 analysis=analyze_invasion_of_privacy_v1_rc1("A public street scene shows a resident.",["visual_description"])
 for key in ("face_recognition_used","identity_inference_from_appearance_allowed","consent_inference_from_appearance_allowed","private_location_inference_from_appearance_allowed","external_provider_used","external_transmission_allowed"):assert analysis[key] is False
