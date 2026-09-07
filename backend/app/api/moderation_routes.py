from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.moderation_schemas import (
    ModerationResponse,
    ModerationTextRequest,
)
from app.policy_config import (
    CATEGORY_POLICIES,
    POLICY_VERSION,
)
from app.services.document_processor import (
    SUPPORTED_DOCUMENT_EXTENSIONS,
    DocumentProcessingError,
    process_document,
)
from app.services.fusion_service import (
    fuse_moderation_decision,
)
from app.services.image_processor import (
    SUPPORTED_IMAGE_EXTENSIONS,
    ImageProcessingError,
    process_image,
)
from app.services.illegal_activities_v1_service import (
    get_illegal_activities_v1_status,
)
from app.services.illegal_activities_v2_rc2_service import (
    get_illegal_activities_v2_rc2_status,
)
from app.services.illegal_activities_v2_rc2_fusion import (
    get_illegal_activities_v2_rc2_readiness,
)
from app.services.child_exploitation_v1_rc1_service import (
    get_child_exploitation_v1_rc1_status,
)
from app.services.child_exploitation_v1_rc1_fusion import (
    get_child_exploitation_v1_rc1_readiness,
)
from app.services.invasion_of_privacy_v1_rc1_service import (
    get_invasion_of_privacy_v1_rc1_status,
)
from app.services.invasion_of_privacy_v1_rc1_fusion import (
    get_invasion_of_privacy_v1_rc1_readiness,
)
from app.services.malicious_programs_v2_rc2_service import (
    get_malicious_programs_v2_rc2_status,
)
from app.services.malicious_programs_v2_rc2_fusion import (
    get_malicious_programs_v2_rc2_readiness,
)
from app.services.intellectual_property_v1_rc1_service import (
    get_intellectual_property_v1_rc1_status,
)
from app.services.intellectual_property_v1_rc1_fusion import (
    get_intellectual_property_v1_rc1_readiness,
)
from app.services.moderation_service import (
    combine_extracted_signals,
)
from app.services.multimodal_capability_gate_service import (
    apply_multimodal_capability_gate,
    apply_violent_content_readiness_gate,
    get_multimodal_capability_status,
)
from app.services.rag_service import (
    get_rag_status,
)
from app.services.openrouter_advisory_service import (
    get_openrouter_advisory_status,
)
from app.services.review_database_service import (
    ReviewDatabaseError,
    create_review_case,
)
from app.services.video_processor import (
    SUPPORTED_VIDEO_EXTENSIONS,
    VideoProcessingError,
    process_video,
)


router = APIRouter(
    prefix="/moderation",
    tags=["Moderation"],
)

MAX_FILE_SIZE_BYTES = (
    100 * 1024 * 1024
)

ALL_SUPPORTED_EXTENSIONS = (
    SUPPORTED_DOCUMENT_EXTENSIONS
    | SUPPORTED_IMAGE_EXTENSIONS
    | SUPPORTED_VIDEO_EXTENSIONS
)


def prepare_stored_preview(
    *,
    category: str,
    text: str,
) -> str:
    if category == "Child Abuse":
        return (
            "[Sensitive child-safety "
            "content omitted from the "
            "review database.]"
        )

    cleaned_text = text.strip()

    if not cleaned_text:
        return (
            "[No readable text preview "
            "was available.]"
        )

    return cleaned_text[:500]


def save_moderation_case(
    *,
    content_type: str,
    file_name: str | None,
    analyzed_text: str,
    decision: dict[str, Any],
    warnings: list[str],
) -> tuple[
    str | None,
    str | None,
]:
    preview = prepare_stored_preview(
        category=decision[
            "category"
        ],
        text=analyzed_text,
    )

    try:
        saved_case = create_review_case(
            content_type=content_type,
            file_name=file_name,
            content_preview=preview,
            category=decision[
                "category"
            ],
            severity=decision[
                "severity"
            ],
            action=decision[
                "action"
            ],
            confidence=float(
                decision[
                    "confidence"
                ]
            ),
            human_review_required=bool(
                decision[
                    "human_review_required"
                ]
            ),
            reason=decision[
                "reason"
            ],
        )

        return (
            saved_case["case_id"],
            saved_case[
                "review_status"
            ],
        )

    except ReviewDatabaseError as exc:
        warnings.append(
            "Review-record warning: "
            f"{exc}"
        )

        return None, None


@router.get("/health")
def moderation_health() -> dict:
    rag_status = get_rag_status()

    return {
        "status": "available",
        "engine": (
            "multimodal-decision-fusion"
        ),
        "rule_engine_connected": True,
        "rag_connected": rag_status[
            "available"
        ],
        "visual_model_connected": True,
        "visual_description_connected": True,
        "visual_violence_independently_validated": False,
        "automatic_visual_safety_confirmation_allowed": False,
        "multimodal_capability_gate": (
            get_multimodal_capability_status()
        ),
        "ocr_connected": True,
        "transcription_connected": True,
        "review_storage_enabled": True,
        "openrouter_advisory": get_openrouter_advisory_status(),
        "illegal_activities_v1": get_illegal_activities_v1_status(),
        "illegal_activities_v2_rc2": {
            **get_illegal_activities_v2_rc2_status(),
            "readiness": get_illegal_activities_v2_rc2_readiness(),
        },
        "child_exploitation_v1_rc1": {
            **get_child_exploitation_v1_rc1_status(),
            "readiness": get_child_exploitation_v1_rc1_readiness(),
        },
        "invasion_of_privacy_v1_rc1": {
            **get_invasion_of_privacy_v1_rc1_status(),
            "readiness": get_invasion_of_privacy_v1_rc1_readiness(),
        },
        "malicious_programs_v2_rc2": {
            **get_malicious_programs_v2_rc2_status(),
            "readiness": get_malicious_programs_v2_rc2_readiness(),
        },
        "intellectual_property_v1_rc1": {
            **get_intellectual_property_v1_rc1_status(),
            "readiness": get_intellectual_property_v1_rc1_readiness(),
        },
    }


@router.get("/policies")
def moderation_policies() -> dict:
    """Return the canonical 19-category moderation rule registry."""

    policies = []
    for policy in CATEGORY_POLICIES.values():
        policies.append(
            {
                "category": policy.category.value,
                "severity": policy.default_severity,
                "default_action": policy.default_action,
                "human_review_required": policy.human_review_required,
                "moderation_conditions": list(policy.moderation_conditions),
                "allow_conditions": list(policy.allow_conditions),
                "review_conditions": list(policy.review_conditions),
                "notes": list(policy.notes),
            }
        )

    return {
        "policy_version": POLICY_VERSION,
        "category_count": len(policies),
        "automatic_enforcement_allowed": False,
        "policies": policies,
    }


@router.post(
    "/text",
    response_model=ModerationResponse,
)
def moderate_plain_text(
    request: ModerationTextRequest,
) -> ModerationResponse:
    cleaned_text = (
        request.text.strip()
    )

    decision = (
        fuse_moderation_decision(
            text=cleaned_text,
            source_context=(
                request.source_context
            ),
            input_sources=["text"],
        )
    )

    decision, readiness_warnings = (
        apply_violent_content_readiness_gate(
            decision=decision,
        )
    )

    fusion_warnings = decision.pop(
        "fusion_warnings",
        [],
    )

    warnings = (
        list(fusion_warnings)
        + list(readiness_warnings)
    )

    (
        review_case_id,
        review_status,
    ) = save_moderation_case(
        content_type="text",
        file_name=None,
        analyzed_text=cleaned_text,
        decision=decision,
        warnings=warnings,
    )

    return ModerationResponse(
        content_type="text",
        source_context=(
            request.source_context
        ),
        analyzed_text_preview=(
            cleaned_text[:500]
        ),
        review_case_id=(
            review_case_id
        ),
        review_status=(
            review_status
        ),
        warnings=warnings,
        **decision,
    )


@router.post(
    "/file",
    response_model=ModerationResponse,
)
async def moderate_uploaded_file(
    file: UploadFile = File(...),
    source_context: str = Form(
        default="unknown"
    ),
) -> ModerationResponse:
    original_name = (
        file.filename
        or "unnamed_file"
    )

    safe_name = Path(
        original_name
    ).name

    extension = Path(
        safe_name
    ).suffix.lower()

    if (
        extension
        not in ALL_SUPPORTED_EXTENSIONS
    ):
        allowed = ", ".join(
            sorted(
                ALL_SUPPORTED_EXTENSIONS
            )
        )

        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file extension "
                f"'{extension}'. "
                "Allowed extensions: "
                f"{allowed}"
            ),
        )

    try:
        file_bytes = await file.read(
            MAX_FILE_SIZE_BYTES + 1
        )

    finally:
        await file.close()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded file is empty."
            ),
        )

    if (
        len(file_bytes)
        > MAX_FILE_SIZE_BYTES
    ):
        raise HTTPException(
            status_code=413,
            detail=(
                "The uploaded file exceeds "
                "the 100 MB limit."
            ),
        )

    try:
        if (
            extension
            in SUPPORTED_DOCUMENT_EXTENSIONS
        ):
            content_type = "document"

            extraction = (
                process_document(
                    safe_name,
                    file_bytes,
                )
            )

        elif (
            extension
            in SUPPORTED_IMAGE_EXTENSIONS
        ):
            content_type = "image"

            extraction = process_image(
                safe_name,
                file_bytes,
            )

        else:
            content_type = "video"

            extraction = process_video(
                safe_name,
                file_bytes,
            )

    except (
        DocumentProcessingError,
        ImageProcessingError,
        VideoProcessingError,
    ) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    extracted_text = extraction.get(
        "extracted_text",
        "",
    )

    ocr_text = extraction.get(
        "ocr_text",
        "",
    )

    audio_transcript = (
        extraction.get(
            "audio_transcript",
            "",
        )
    )

    visual_description = (
        extraction.get(
            "visual_description",
            "",
        )
    )

    combined_text = (
        combine_extracted_signals(
            extracted_text=(
                extracted_text
            ),
            ocr_text=ocr_text,
            audio_transcript=(
                audio_transcript
            ),
            visual_description=(
                visual_description
            ),
        )
    )

    input_sources: list[str] = []

    if extracted_text.strip():
        input_sources.append(
            "extracted_text"
        )

    if ocr_text.strip():
        input_sources.append(
            "ocr_text"
        )

    if audio_transcript.strip():
        input_sources.append(
            "audio_transcript"
        )

    if visual_description.strip():
        input_sources.append(
            "visual_description"
        )

    decision = (
        fuse_moderation_decision(
            text=combined_text,
            source_context=(
                source_context
            ),
            input_sources=(
                input_sources
            ),
        )
    )

    decision, readiness_warnings = (
        apply_violent_content_readiness_gate(
            decision=decision,
        )
    )

    decision, capability_warnings = (
        apply_multimodal_capability_gate(
            decision=decision,
            content_type=content_type,
        )
    )

    fusion_warnings = decision.pop(
        "fusion_warnings",
        [],
    )

    extraction_warnings = (
        extraction.get(
            "warnings",
            [],
        )
    )

    warnings = (
        list(extraction_warnings)
        + list(fusion_warnings)
        + list(readiness_warnings)
        + list(capability_warnings)
    )

    (
        review_case_id,
        review_status,
    ) = save_moderation_case(
        content_type=content_type,
        file_name=safe_name,
        analyzed_text=combined_text,
        decision=decision,
        warnings=warnings,
    )

    return ModerationResponse(
        content_type=content_type,
        file_name=safe_name,
        source_context=source_context,
        analyzed_text_preview=(
            combined_text[:500]
        ),
        review_case_id=(
            review_case_id
        ),
        review_status=(
            review_status
        ),
        extraction_metadata=(
            extraction.get(
                "metadata",
                {},
            )
        ),
        warnings=warnings,
        **decision,
    )
