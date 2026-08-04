from pathlib import Path

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
from app.services.moderation_service import (
    combine_extracted_signals,
)
from app.services.rag_service import (
    get_rag_status,
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

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

ALL_SUPPORTED_EXTENSIONS = (
    SUPPORTED_DOCUMENT_EXTENSIONS
    | SUPPORTED_IMAGE_EXTENSIONS
    | SUPPORTED_VIDEO_EXTENSIONS
)


@router.get("/health")
def moderation_health() -> dict:
    rag_status = get_rag_status()

    return {
        "status": "available",
        "engine": "multimodal-decision-fusion",
        "rule_engine_connected": True,
        "rag_connected": rag_status[
            "available"
        ],
        "visual_model_connected": True,
        "ocr_connected": True,
        "transcription_connected": True,
    }


@router.post(
    "/text",
    response_model=ModerationResponse,
)
def moderate_plain_text(
    request: ModerationTextRequest,
) -> ModerationResponse:
    cleaned_text = request.text.strip()

    decision = fuse_moderation_decision(
        text=cleaned_text,
        source_context=request.source_context,
        input_sources=["text"],
    )

    fusion_warnings = decision.pop(
        "fusion_warnings",
        [],
    )

    return ModerationResponse(
        content_type="text",
        source_context=request.source_context,
        analyzed_text_preview=(
            cleaned_text[:500]
        ),
        warnings=fusion_warnings,
        **decision,
    )


@router.post(
    "/file",
    response_model=ModerationResponse,
)
async def moderate_uploaded_file(
    file: UploadFile = File(...),
    source_context: str = Form(default="user"),
) -> ModerationResponse:
    original_name = (
        file.filename or "unnamed_file"
    )
    safe_name = Path(original_name).name

    extension = Path(
        safe_name
    ).suffix.lower()

    if extension not in ALL_SUPPORTED_EXTENSIONS:
        allowed = ", ".join(
            sorted(ALL_SUPPORTED_EXTENSIONS)
        )

        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file extension "
                f"'{extension}'. "
                f"Allowed extensions: {allowed}"
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
            detail="The uploaded file is empty.",
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "The uploaded file exceeds "
                "the 100 MB limit."
            ),
        )

    try:
        if extension in SUPPORTED_DOCUMENT_EXTENSIONS:
            content_type = "document"

            extraction = process_document(
                safe_name,
                file_bytes,
            )

        elif extension in SUPPORTED_IMAGE_EXTENSIONS:
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
    audio_transcript = extraction.get(
        "audio_transcript",
        "",
    )
    visual_description = extraction.get(
        "visual_description",
        "",
    )

    combined_text = combine_extracted_signals(
        extracted_text=extracted_text,
        ocr_text=ocr_text,
        audio_transcript=audio_transcript,
        visual_description=visual_description,
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

    decision = fuse_moderation_decision(
        text=combined_text,
        source_context=source_context,
        input_sources=input_sources,
    )

    fusion_warnings = decision.pop(
        "fusion_warnings",
        [],
    )

    extraction_warnings = extraction.get(
        "warnings",
        [],
    )

    all_warnings = (
        extraction_warnings
        + fusion_warnings
    )

    return ModerationResponse(
        content_type=content_type,
        file_name=safe_name,
        source_context=source_context,
        analyzed_text_preview=(
            combined_text[:500]
        ),
        extraction_metadata=extraction.get(
            "metadata",
            {},
        ),
        warnings=all_warnings,
        **decision,
    )