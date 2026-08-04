from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.schemas import (
    ExtractionResponse,
    TextExtractionRequest,
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
from app.services.ocr_service import get_ocr_status
from app.services.video_processor import (
    SUPPORTED_VIDEO_EXTENSIONS,
    VideoProcessingError,
    process_video,
)


router = APIRouter(
    prefix="/extract",
    tags=["Multimodal extraction"],
)

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

ALL_SUPPORTED_EXTENSIONS = (
    SUPPORTED_DOCUMENT_EXTENSIONS
    | SUPPORTED_IMAGE_EXTENSIONS
    | SUPPORTED_VIDEO_EXTENSIONS
)


@router.get("/ocr-health")
def ocr_health() -> dict:
    status = get_ocr_status()

    if not status["available"]:
        raise HTTPException(
            status_code=503,
            detail=status,
        )

    return status


@router.post(
    "/text",
    response_model=ExtractionResponse,
)
def extract_text(
    request: TextExtractionRequest,
) -> ExtractionResponse:
    cleaned_text = request.text.strip()

    return ExtractionResponse(
        content_type="text",
        extracted_text=cleaned_text,
        source_context=request.source_context,
        metadata={
            "character_count": len(cleaned_text),
            "word_count": len(cleaned_text.split()),
        },
    )


@router.post(
    "/file",
    response_model=ExtractionResponse,
)
async def extract_file(
    file: UploadFile = File(...),
    source_context: str = Form(default="user"),
) -> ExtractionResponse:
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

    common_values = {
        "file_name": safe_name,
        "file_extension": extension,
        "media_type": file.content_type,
        "file_size_bytes": len(file_bytes),
        "source_context": source_context,
    }

    try:
        if extension in SUPPORTED_DOCUMENT_EXTENSIONS:
            result = process_document(
                safe_name,
                file_bytes,
            )

            return ExtractionResponse(
                content_type="document",
                **common_values,
                **result,
            )

        if extension in SUPPORTED_IMAGE_EXTENSIONS:
            result = process_image(
                safe_name,
                file_bytes,
            )

            return ExtractionResponse(
                content_type="image",
                **common_values,
                **result,
            )

        result = process_video(
            safe_name,
            file_bytes,
        )

        return ExtractionResponse(
            content_type="video",
            **common_values,
            **result,
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