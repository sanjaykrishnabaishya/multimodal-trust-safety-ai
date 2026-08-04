from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.services.ocr_service import (
    OCRProcessingError,
    extract_text_from_pil_image,
)


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ImageProcessingError(Exception):
    pass


def process_image(
    file_name: str,
    file_bytes: bytes,
) -> dict:
    extension = Path(file_name).suffix.lower()

    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ImageProcessingError(
            f"Unsupported image type: {extension}"
        )

    warnings: list[str] = []

    try:
        with Image.open(BytesIO(file_bytes)) as image:
            image.load()

            metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "color_mode": image.mode,
                "animated": bool(
                    getattr(image, "is_animated", False)
                ),
                "frame_count": int(
                    getattr(image, "n_frames", 1)
                ),
            }

            try:
                ocr_text = extract_text_from_pil_image(image)
            except OCRProcessingError as exc:
                ocr_text = ""
                warnings.append(f"OCR warning: {exc}")

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise ImageProcessingError(
            "The uploaded image is invalid, damaged, or unsafe to open."
        ) from exc

    if not ocr_text:
        warnings.append(
            "No readable English text was detected in the image."
        )

    warnings.append(
        "OCR is active. Full visual scene understanding "
        "has not been connected yet."
    )

    return {
        "visual_description": "",
        "ocr_text": ocr_text,
        "metadata": metadata,
        "warnings": warnings,
    }