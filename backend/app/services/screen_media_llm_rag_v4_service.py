from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from app.services.graphic_sexual_content_v2_service import (
    SEXUAL_CATEGORY,
    SEXUAL_HARASSMENT_CATEGORY,
    analyze_graphic_sexual_content_v2,
)


UNCERTAIN_CATEGORY = "Uncertain"
MEDIA_REVIEW_ACTION = "Refer to human review"
LLM_MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
LLM_MODEL_REVISION = "7ae557604adf67be50417f59c2c2f167def9a775"
LLM_MODEL_LICENSE = "Apache-2.0"
LLM_SCHEMA_VERSION = "screen-media-evidence-v1"
WIKIDATA_LICENSE = "CC0-1.0"
ALLOWED_WORK_TYPES = {"film", "television_series", "tv_series"}
TRUSTED_PUBLISHER_SOURCES = {
    "signed_publisher_metadata",
    "trusted_catalog_ingest",
    "verified_rights_holder_metadata",
}
EVIDENCE_CHANNELS = {"caption", "ocr", "transcript", "publisher_metadata"}
SEXUAL_CONCERN_VALUES = {"explicit", "adult_sexual", "uncertain"}
LLM_SEXUAL_CONCERN_VALUES = {"explicit", "possibly_explicit"}
LLM_OBSCURATION_VALUES = {"fully_obscured", "partial", "unblurred", "uncertain"}
QID_PATTERN = re.compile(r"^Q[1-9][0-9]*$")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCREEN_MEDIA_CATALOG_DIRECTORY = (
    PROJECT_ROOT / "datasets" / "public" / "wikidata_screen_works_v2"
)
SCREEN_MEDIA_CATALOG_PATH = SCREEN_MEDIA_CATALOG_DIRECTORY / "records.json"
SCREEN_MEDIA_MANIFEST_PATH = SCREEN_MEDIA_CATALOG_DIRECTORY / "manifest.json"


class ScreenMediaLLMError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_screen_media_catalog() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not SCREEN_MEDIA_CATALOG_PATH.is_file() or not SCREEN_MEDIA_MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            "The CC0 screen-media RAG catalog is missing. Run "
            "'python -m scripts.import_wikidata_screen_works_v2' first."
        )
    records_value = json.loads(SCREEN_MEDIA_CATALOG_PATH.read_text(encoding="utf-8"))
    manifest_value = json.loads(SCREEN_MEDIA_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(records_value, list) or not isinstance(manifest_value, dict):
        raise RuntimeError("The screen-media RAG catalog has an invalid format.")
    if manifest_value.get("license") != WIKIDATA_LICENSE:
        raise RuntimeError("The screen-media RAG catalog is not marked CC0-1.0.")
    if manifest_value.get("creative_media_downloaded") is not False:
        raise RuntimeError("The screen-media catalog violates the no-creative-media contract.")
    records = [
        valid
        for item in records_value
        if isinstance(item, dict)
        for valid in [_catalog_record(item)]
        if valid is not None
    ]
    if len(records) != len(records_value):
        raise RuntimeError("One or more screen-media catalog records failed validation.")
    if int(manifest_value.get("record_count", -1)) != len(records):
        raise RuntimeError("The screen-media catalog count does not match its manifest.")
    return records, manifest_value


def get_screen_media_rag_status() -> dict[str, Any]:
    status = {
        "available": False,
        "catalog_path": str(SCREEN_MEDIA_CATALOG_PATH),
        "source": "Wikidata structured entity data",
        "license": WIKIDATA_LICENSE,
        "candidate_generation_only": True,
        "can_verify_provenance": False,
    }
    try:
        records, manifest = load_screen_media_catalog()
    except (FileNotFoundError, RuntimeError, json.JSONDecodeError) as exc:
        status["error"] = str(exc)
        return status
    status.update(
        {
            "available": True,
            "record_count": len(records),
            "retrieved_at_utc": manifest.get("retrieved_at_utc"),
            "content_hash_sha256": manifest.get("content_hash_sha256"),
        }
    )
    return status


def _normalized(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = _normalized(text)
    normalized_phrase = _normalized(phrase)
    if not normalized_phrase:
        return False
    return bool(
        re.search(
            rf"(?<![\w]){re.escape(normalized_phrase)}(?![\w])",
            normalized_text,
        )
    )


def _base(status: str) -> dict[str, Any]:
    return {
        "available": True,
        "category": None,
        "severity": "None",
        "action": None,
        "confidence": 0.0,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "decision_applied": False,
        "status": status,
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
        "llm_used": False,
        "rag_used": False,
        "screen_work_verified": False,
    }


def _catalog_record(record: Mapping[str, Any]) -> dict[str, Any] | None:
    qid = str(record.get("qid", "")).strip()
    title = " ".join(str(record.get("title", "")).split())
    work_type = str(record.get("work_type", "")).strip().lower()
    source = str(record.get("source", "")).strip().lower()
    license_value = str(record.get("license", "")).strip()
    if (
        not QID_PATTERN.fullmatch(qid)
        or not title
        or work_type not in ALLOWED_WORK_TYPES
        or source != "wikidata"
        or license_value != WIKIDATA_LICENSE
    ):
        return None
    aliases = [
        " ".join(str(alias).split())
        for alias in record.get("aliases", [])
        if " ".join(str(alias).split())
    ]
    return {
        "qid": qid,
        "title": title,
        "aliases": list(dict.fromkeys(aliases)),
        "work_type": work_type,
        "release_year": record.get("release_year"),
        "source": "wikidata",
        "license": WIKIDATA_LICENSE,
        "source_url": str(
            record.get("source_url") or f"https://www.wikidata.org/wiki/{qid}"
        ),
    }


def retrieve_screen_work_candidates(
    evidence: Mapping[str, Any],
    catalog_records: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve exact title/alias candidates from CC0 structured records.

    Retrieval is candidate generation only. A matching title in a caption, OCR,
    or transcript is never treated as verified provenance.
    """

    if catalog_records is None:
        catalog_records, _ = load_screen_media_catalog()
    channel_text = {
        channel: str(evidence.get(channel, ""))
        for channel in ("caption", "ocr", "transcript")
    }
    candidates: list[dict[str, Any]] = []
    for raw_record in catalog_records:
        record = _catalog_record(raw_record)
        if record is None:
            continue
        names = [record["title"], *record["aliases"]]
        matched_channels = [
            channel
            for channel, text in channel_text.items()
            if any(_contains_phrase(text, name) for name in names)
        ]
        if not matched_channels:
            continue
        candidates.append(
            {
                **record,
                "matched_channels": matched_channels,
                "candidate_only": True,
                "verified_provenance": False,
            }
        )
    candidates.sort(key=lambda item: (item["title"].casefold(), item["qid"]))
    return candidates


def _validate_publisher_provenance(
    publisher_metadata: Mapping[str, Any] | None,
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    metadata = dict(publisher_metadata or {})
    source_type = str(metadata.get("source_type", "")).strip().lower()
    qid = str(metadata.get("qid", "")).strip()
    work_type = str(metadata.get("work_type", "")).strip().lower()
    signature_verified = metadata.get("signature_verified") is True
    if (
        source_type not in TRUSTED_PUBLISHER_SOURCES
        or not signature_verified
        or not QID_PATTERN.fullmatch(qid)
        or work_type not in ALLOWED_WORK_TYPES
    ):
        return None
    matching = [
        candidate
        for candidate in candidates
        if candidate.get("qid") == qid
        and candidate.get("work_type") == work_type
    ]
    if len(matching) != 1:
        return None
    return {
        **dict(matching[0]),
        "candidate_only": False,
        "verified_provenance": True,
        "publisher_source_type": source_type,
        "publisher_signature_verified": True,
    }


def validate_llm_analysis(
    raw: Mapping[str, Any] | None,
    *,
    available_evidence_ids: set[str],
    candidate_qids: set[str],
) -> dict[str, Any]:
    value = dict(raw or {})
    schema_valid = value.get("schema_version") == LLM_SCHEMA_VERSION
    abstained = value.get("abstained") is True
    sexual_signal = str(value.get("sexual_signal", "abstain")).strip().lower()
    obscuration = str(value.get("obscuration", "uncertain")).strip().lower()
    candidate_qid = str(value.get("candidate_qid", "")).strip()
    confidence = value.get("confidence", 0.0)
    try:
        confidence_value = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence_value = 0.0
    raw_evidence_ids = value.get("evidence_ids", [])
    evidence_list_valid = isinstance(raw_evidence_ids, list)
    evidence_ids = (
        [str(item).strip() for item in raw_evidence_ids if str(item).strip()]
        if evidence_list_valid
        else []
    )
    evidence_references_valid = set(evidence_ids).issubset(available_evidence_ids)
    qid_valid = not candidate_qid or candidate_qid in candidate_qids
    values_valid = bool(
        sexual_signal in {"none", "explicit", "possibly_explicit", "abstain"}
        and obscuration in LLM_OBSCURATION_VALUES
    )
    if abstained:
        abstention_fields_valid = bool(
            sexual_signal == "abstain"
            and obscuration == "uncertain"
            and not candidate_qid
        )
        evidence_valid = bool(evidence_list_valid and evidence_references_valid)
        valid = bool(
            schema_valid
            and values_valid
            and abstention_fields_valid
            and evidence_valid
        )
    else:
        abstention_fields_valid = True
        evidence_valid = bool(
            evidence_list_valid and evidence_ids and evidence_references_valid
        )
        valid = bool(
            schema_valid
            and values_valid
            and evidence_valid
            and qid_valid
        )
    failure_reasons = []
    if not schema_valid:
        failure_reasons.append("schema_version")
    if not values_valid:
        failure_reasons.append("enum_values")
    if not evidence_valid:
        failure_reasons.append("evidence_ids")
    if not qid_valid:
        failure_reasons.append("candidate_qid")
    if not abstention_fields_valid:
        failure_reasons.append("abstention_fields")
    return {
        "available": True,
        "valid": valid,
        "abstained": abstained or not valid,
        "sexual_signal": sexual_signal if valid else "abstain",
        "obscuration": obscuration if valid else "uncertain",
        "candidate_qid": candidate_qid if valid else "",
        "confidence": confidence_value if valid else 0.0,
        "evidence_ids": evidence_ids if valid else [],
        "status": (
            "validated_abstention"
            if valid and abstained
            else "validated_supporting_analysis"
            if valid
            else "invalid_analysis_abstained"
        ),
        "failure_reasons": failure_reasons,
        "cannot_verify_title": True,
        "cannot_create_allow": True,
    }


@lru_cache(maxsize=1)
def _load_local_llm() -> tuple[Any, Any]:
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            LLM_MODEL_NAME,
            revision=LLM_MODEL_REVISION,
        )
        model = AutoModelForCausalLM.from_pretrained(
            LLM_MODEL_NAME,
            revision=LLM_MODEL_REVISION,
            torch_dtype="auto",
        )
        model.to("cpu")
        model.eval()
        return tokenizer, model
    except Exception as exc:
        raise ScreenMediaLLMError(
            "The pinned local screen-media LLM could not be loaded."
        ) from exc


def get_screen_media_llm_status() -> dict[str, Any]:
    return {
        "available": True,
        "enabled": os.getenv("ENABLE_SCREEN_MEDIA_LLM", "0") == "1",
        "model": LLM_MODEL_NAME,
        "revision": LLM_MODEL_REVISION,
        "license": LLM_MODEL_LICENSE,
        "device": "CPU",
        "model_loaded": _load_local_llm.cache_info().currsize > 0,
        "permitted_role": "supporting evidence analysis only",
        "automatic_enforcement_allowed": False,
        "automatic_allow_allowed": False,
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ScreenMediaLLMError("The local LLM did not return a JSON object.")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ScreenMediaLLMError("The local LLM returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise ScreenMediaLLMError("The local LLM JSON was not an object.")
    return value


def _canonical_local_llm_abstention(
    adapter_status: str,
    *,
    raw_contract_failure_reasons: Sequence[str] = (),
    raw_candidate_qid_rejected: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": LLM_SCHEMA_VERSION,
        "abstained": True,
        "sexual_signal": "abstain",
        "obscuration": "uncertain",
        "candidate_qid": "",
        "confidence": 0.0,
        "evidence_ids": [],
        "adapter_status": adapter_status,
        "raw_model_contract_valid": False,
        "raw_contract_failure_reasons": list(raw_contract_failure_reasons),
        "raw_candidate_qid_rejected": raw_candidate_qid_rejected,
    }


def _adapt_local_llm_output(
    raw: Mapping[str, Any],
    *,
    available_evidence_ids: set[str],
) -> dict[str, Any]:
    value = dict(raw)
    schema_valid = value.get("schema_version") == LLM_SCHEMA_VERSION
    abstained = value.get("abstained") is True
    sexual_signal = str(value.get("sexual_signal", "abstain")).strip().lower()
    obscuration = str(value.get("obscuration", "uncertain")).strip().lower()
    raw_candidate_qid_rejected = bool(str(value.get("candidate_qid", "")).strip())
    raw_evidence_ids = value.get("evidence_ids", [])
    evidence_list_valid = isinstance(raw_evidence_ids, list)
    evidence_ids = (
        [str(item).strip() for item in raw_evidence_ids if str(item).strip()]
        if evidence_list_valid
        else []
    )
    evidence_references_valid = set(evidence_ids).issubset(available_evidence_ids)
    try:
        confidence = max(0.0, min(1.0, float(value.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    failure_reasons: list[str] = []
    if not schema_valid:
        failure_reasons.append("schema_version")
    if raw_candidate_qid_rejected:
        failure_reasons.append("model_generated_candidate_qid")
    if not evidence_list_valid or not evidence_references_valid:
        failure_reasons.append("evidence_ids")
    if abstained:
        if sexual_signal != "abstain" or obscuration != "uncertain":
            failure_reasons.append("abstention_fields")
    else:
        if sexual_signal not in {"none", "explicit", "possibly_explicit"}:
            failure_reasons.append("sexual_signal")
        if obscuration not in LLM_OBSCURATION_VALUES:
            failure_reasons.append("obscuration")
        if not evidence_ids:
            failure_reasons.append("missing_evidence_citation")

    if failure_reasons:
        return _canonical_local_llm_abstention(
            "raw_model_output_rejected_fail_closed",
            raw_contract_failure_reasons=failure_reasons,
            raw_candidate_qid_rejected=raw_candidate_qid_rejected,
        )
    return {
        "schema_version": LLM_SCHEMA_VERSION,
        "abstained": abstained,
        "sexual_signal": sexual_signal,
        "obscuration": obscuration,
        # The local LLM has no title-identity authority. RAG candidates remain in
        # the deterministic retrieval path and are never selected by generation.
        "candidate_qid": "",
        "confidence": confidence,
        "evidence_ids": evidence_ids,
        "adapter_status": "raw_model_output_accepted_without_title_authority",
        "raw_model_contract_valid": True,
        "raw_contract_failure_reasons": [],
        "raw_candidate_qid_rejected": False,
    }


def analyze_with_local_screen_media_llm(
    evidence_records: Sequence[Mapping[str, Any]],
    rag_candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if os.getenv("ENABLE_SCREEN_MEDIA_LLM", "0") != "1":
        return {
            "schema_version": LLM_SCHEMA_VERSION,
            "abstained": True,
            "sexual_signal": "abstain",
            "obscuration": "uncertain",
            "candidate_qid": "",
            "confidence": 0.0,
            "evidence_ids": [],
            "status": "local_llm_disabled",
            "adapter_status": "local_llm_disabled",
            "raw_model_contract_valid": False,
            "raw_contract_failure_reasons": [],
            "raw_candidate_qid_rejected": False,
        }
    try:
        import torch
    except ImportError as exc:
        raise ScreenMediaLLMError(
            "The optional local LLM runtime is not installed."
        ) from exc
    tokenizer, model = _load_local_llm()
    safe_evidence = [
        {
            "evidence_id": str(item.get("evidence_id", ""))[:80],
            "channel": str(item.get("channel", ""))[:40],
            "text": " ".join(str(item.get("text", "")).split())[:700],
        }
        for item in evidence_records[:12]
        if str(item.get("evidence_id", "")).strip()
    ]
    safe_candidates = [
        {
            "title": str(item.get("title", ""))[:200],
            "work_type": str(item.get("work_type", "")),
            "candidate_only": True,
        }
        for item in rag_candidates[:10]
    ]
    system_message = (
        "You are a cautious evidence analyst. Use only the supplied evidence IDs. "
        "A retrieved title is a candidate, never verified provenance. You cannot "
        "declare content safe, verify a title, or authorize enforcement. If evidence "
        "is missing or conflicting, abstain. Return only one JSON object and no "
        "markdown. The schema_version value must be exactly "
        f"{json.dumps(LLM_SCHEMA_VERSION)}. Use exactly these keys: schema_version, "
        "abstained, sexual_signal, obscuration, candidate_qid, confidence, "
        "evidence_ids. sexual_signal must be none, explicit, possibly_explicit, or "
        "abstain. obscuration must be fully_obscured, partial, unblurred, or "
        "uncertain. candidate_qid must always be an empty string because title "
        "identity belongs only to the deterministic RAG path. Never invent or copy "
        "a QID. For a non-abstaining answer, evidence_ids must be a non-empty "
        "array copied only from supplied evidence IDs. For abstention, return exactly "
        f"{{\"schema_version\":{json.dumps(LLM_SCHEMA_VERSION)},"
        "\"abstained\":true,\"sexual_signal\":\"abstain\","
        "\"obscuration\":\"uncertain\",\"candidate_qid\":\"\","
        "\"confidence\":0.0,\"evidence_ids\":[]}}."
    )
    user_message = json.dumps(
        {
            "evidence": safe_evidence,
            "rag_title_candidates_without_identity_authority": safe_candidates,
            "candidate_qid_rule": "must_always_be_empty",
        },
        ensure_ascii=True,
    )
    prompt = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=220,
            do_sample=False,
            repetition_penalty=1.05,
        )
    output_tokens = generated[0][inputs["input_ids"].shape[1] :]
    output_text = tokenizer.decode(output_tokens, skip_special_tokens=True)
    try:
        raw_output = _extract_json_object(output_text)
    except ScreenMediaLLMError:
        return _canonical_local_llm_abstention(
            "raw_model_output_parse_failed_closed",
            raw_contract_failure_reasons=("json_parse",),
        )
    return _adapt_local_llm_output(
        raw_output,
        available_evidence_ids={item["evidence_id"] for item in safe_evidence},
    )


def _validated_full_obscuration(visual_evidence: Mapping[str, Any] | None) -> bool:
    value = dict(visual_evidence or {})
    try:
        sample_coverage = float(value.get("sample_coverage", 0.0))
        sensitive_region_coverage = float(value.get("sensitive_region_coverage", 0.0))
        visible_explicit_regions = int(value.get("visible_explicit_regions", -1))
    except (TypeError, ValueError):
        return False
    return bool(
        value.get("independently_validated_blur_detector") is True
        and value.get("no_explicit_detail_visible") is True
        and sample_coverage >= 0.90
        and sensitive_region_coverage >= 0.95
        and visible_explicit_regions == 0
    )


def analyze_screen_media_llm_rag_v4(
    text: str,
    *,
    content_type: str,
    existing_category: str | None,
    extracted_evidence: Mapping[str, Any] | None,
    catalog_records: Iterable[Mapping[str, Any]] | None = None,
    publisher_metadata: Mapping[str, Any] | None = None,
    visual_evidence: Mapping[str, Any] | None = None,
    llm_analysis: Mapping[str, Any] | None = None,
    run_local_llm: bool = False,
) -> dict[str, Any]:
    base_result = analyze_graphic_sexual_content_v2(
        text,
        existing_category=existing_category,
    )
    base_status = str(base_result.get("status", ""))
    if base_status in {
        "child_exploitation_boundary_no_override",
        "blocked_by_established_category_owner",
    }:
        return {
            **base_result,
            "llm_used": False,
            "rag_used": False,
            "screen_work_verified": False,
            "v4_status": "blocked_by_higher_priority_owner",
        }
    if base_result.get("category") == SEXUAL_HARASSMENT_CATEGORY:
        return {
            **base_result,
            "llm_used": False,
            "rag_used": False,
            "screen_work_verified": False,
            "v4_status": "sexual_harassment_owner_preserved",
        }
    if str(content_type).strip().lower() not in {"image", "video"}:
        return {
            **base_result,
            "llm_used": False,
            "rag_used": False,
            "screen_work_verified": False,
            "v4_status": "non_visual_content_falls_back_to_v2",
        }

    evidence = dict(extracted_evidence or {})
    has_retrieval_text = any(
        str(evidence.get(channel, "")).strip()
        for channel in ("caption", "ocr", "transcript")
    )
    candidates = (
        retrieve_screen_work_candidates(evidence, catalog_records)
        if has_retrieval_text
        else []
    )
    verified_work = _validate_publisher_provenance(publisher_metadata, candidates)
    evidence_records = [
        {
            "evidence_id": f"{channel}-1",
            "channel": channel,
            "text": str(evidence.get(channel, "")),
        }
        for channel in ("caption", "ocr", "transcript")
        if str(evidence.get(channel, "")).strip()
    ]
    if publisher_metadata:
        evidence_records.append(
            {
                "evidence_id": "publisher-metadata-1",
                "channel": "publisher_metadata",
                "text": json.dumps(dict(publisher_metadata), ensure_ascii=True),
            }
        )
    raw_llm = dict(llm_analysis or {})
    if run_local_llm and not raw_llm:
        try:
            raw_llm = analyze_with_local_screen_media_llm(evidence_records, candidates)
        except ScreenMediaLLMError:
            raw_llm = {}
    validated_llm = validate_llm_analysis(
        raw_llm,
        available_evidence_ids={item["evidence_id"] for item in evidence_records},
        candidate_qids={str(item["qid"]) for item in candidates},
    )
    llm_used = bool(validated_llm.get("valid") and not validated_llm.get("abstained"))
    visual = dict(visual_evidence or {})
    visual_explicitness = str(visual.get("explicitness", "uncertain")).strip().lower()
    visual_concern = visual_explicitness in SEXUAL_CONCERN_VALUES
    llm_concern = bool(
        llm_used
        and validated_llm.get("sexual_signal") in LLM_SEXUAL_CONCERN_VALUES
        and float(validated_llm.get("confidence", 0.0)) >= 0.70
    )
    base_concern = base_result.get("category") == SEXUAL_CATEGORY
    full_obscuration = _validated_full_obscuration(visual)
    common = {
        "llm_used": llm_used,
        "llm_analysis": validated_llm,
        "rag_used": bool(candidates),
        "rag_candidates": candidates,
        "screen_work_verified": verified_work is not None,
        "verified_screen_work": verified_work,
        "full_obscuration_independently_verified": full_obscuration,
        "automatic_enforcement_allowed": False,
    }

    if verified_work is not None and full_obscuration:
        return {
            **_base("verified_screen_work_fully_obscured_no_override"),
            **common,
            "v4_status": "full_obscuration_verified_without_llm_allow",
        }
    if verified_work is not None and (base_concern or visual_concern or llm_concern):
        return {
            **_base("verified_screen_work_review_candidate"),
            **common,
            "category": SEXUAL_CATEGORY,
            "severity": "Medium",
            "action": MEDIA_REVIEW_ACTION,
            "confidence": 0.78,
            "human_review_required": True,
            "decision_applied": True,
            "v4_status": "verified_screen_work_with_explicit_or_uncertain_evidence",
        }
    if llm_concern and not base_concern:
        return {
            **_base("llm_concern_uncertain_review_candidate"),
            **common,
            "category": UNCERTAIN_CATEGORY,
            "severity": "Unknown",
            "action": MEDIA_REVIEW_ACTION,
            "confidence": min(float(validated_llm["confidence"]), 0.75),
            "human_review_required": True,
            "decision_applied": True,
            "v4_status": "llm_can_escalate_but_not_verify_or_allow",
        }
    return {
        **base_result,
        **common,
        "v4_status": (
            "retrieved_title_candidate_not_verified"
            if candidates and verified_work is None
            else "no_screen_media_policy_override"
        ),
    }
