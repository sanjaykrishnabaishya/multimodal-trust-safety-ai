from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from app.deep_analysis_schemas import (
    DeepAnalysisResponse,
    DeepAnalysisTextRequest,
)
from app.services.deep_analysis_service import (
    create_deep_analysis,
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
from app.services.video_processor import (
    SUPPORTED_VIDEO_EXTENSIONS,
    VideoProcessingError,
    process_video,
)


router = APIRouter(
    prefix="/deep-analysis",
    tags=["Deep Analysis"],
)

MAX_FILE_SIZE_BYTES = (
    100 * 1024 * 1024
)

ALL_SUPPORTED_EXTENSIONS = (
    SUPPORTED_DOCUMENT_EXTENSIONS
    | SUPPORTED_IMAGE_EXTENSIONS
    | SUPPORTED_VIDEO_EXTENSIONS
)


@router.get("/health")
def deep_analysis_health() -> dict:
    return {
        "status": "available",
        "stage": "C2-simplified",
        "summary": True,
        "scene_summary": True,
        "ocr_reporting": True,
        "content_size": True,
        "media_duration": True,
        "fact_check_suggestions": True,
    }


@router.post(
    "/text",
    response_model=DeepAnalysisResponse,
)
def deeply_analyze_text(
    request: DeepAnalysisTextRequest,
) -> DeepAnalysisResponse:
    cleaned_text = (
        request.text.strip()
    )

    return create_deep_analysis(
        content_type="text",
        extracted_text=cleaned_text,
        original_size_bytes=len(
            cleaned_text.encode(
                "utf-8"
            )
        ),
    )


@router.post(
    "/file",
    response_model=DeepAnalysisResponse,
)
async def deeply_analyze_file(
    file: UploadFile = File(...),
) -> DeepAnalysisResponse:
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

            extraction = process_document(
                safe_name,
                file_bytes,
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

    return create_deep_analysis(
        content_type=content_type,
        file_name=safe_name,
        original_size_bytes=len(
            file_bytes
        ),
        extracted_text=(
            extraction.get(
                "extracted_text",
                "",
            )
        ),
        ocr_text=extraction.get(
            "ocr_text",
            "",
        ),
        audio_transcript=(
            extraction.get(
                "audio_transcript",
                "",
            )
        ),
        visual_description=(
            extraction.get(
                "visual_description",
                "",
            )
        ),
        metadata=extraction.get(
            "metadata",
            {},
        ),
        warnings=extraction.get(
            "warnings",
            [],
        ),
    )