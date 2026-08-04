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
from app.services.image_processor import (
    SUPPORTED_IMAGE_EXTENSIONS,
    ImageProcessingError,
    process_image,
)
from app.services.moderation_service import (
    combine_extracted_signals,
    moderate_text,
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
    return {
        "status": "available",
        "engine": "baseline-rule-engine",
        "rag_connected": False,
        "visual_model_connected": False,
    }


@router.post(
    "/text",
    response_model=ModerationResponse,
)
def moderate_plain_text(
    request: ModerationTextRequest,
) -> ModerationResponse:
    decision = moderate_text(
        text=request.text,
        source_context=request.source_context,
    )

    preview = request.text.strip()[:500]

    return ModerationResponse(
        content_type="text",
        source_context=request.source_context,
        analyzed_text_preview=preview,
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
    original_name = file.filename or "unnamed_file"
    safe_name = Path(original_name).name
    extension = Path(safe_name).suffix.lower()

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

    combined_text = combine_extracted_signals(
        extracted_text=extraction.get(
            "extracted_text",
            "",
        ),
        ocr_text=extraction.get(
            "ocr_text",
            "",
        ),
        audio_transcript=extraction.get(
            "audio_transcript",
            "",
        ),
        visual_description=extraction.get(
            "visual_description",
            "",
        ),
    )

    decision = moderate_text(
        text=combined_text,
        source_context=source_context,
    )

    return ModerationResponse(
        content_type=content_type,
        file_name=safe_name,
        source_context=source_context,
        analyzed_text_preview=combined_text[:500],
        extraction_metadata=extraction.get(
            "metadata",
            {},
        ),
        warnings=extraction.get(
            "warnings",
            [],
        ),
        **decision,
    )