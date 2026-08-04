import shutil
from io import BytesIO
from pathlib import Path

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


COMMON_TESSERACT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
]


class OCRProcessingError(Exception):
    pass


def configure_tesseract() -> str:
    command_from_path = shutil.which("tesseract")

    if command_from_path:
        pytesseract.pytesseract.tesseract_cmd = command_from_path
        return command_from_path

    for candidate in COMMON_TESSERACT_PATHS:
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return str(candidate)

    raise OCRProcessingError(
        "Tesseract OCR was not found. Install it in "
        r"C:\Program Files\Tesseract-OCR or add it to Windows PATH."
    )


def get_ocr_status() -> dict:
    try:
        executable = configure_tesseract()
        version = str(pytesseract.get_tesseract_version())

        languages = sorted(
            pytesseract.get_languages(config="")
        )

        return {
            "available": True,
            "engine": "Tesseract",
            "version": version,
            "executable": executable,
            "languages": languages,
        }

    except Exception as exc:
        return {
            "available": False,
            "engine": "Tesseract",
            "error": str(exc),
        }


def prepare_image_for_ocr(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")

    if image.width < 1200:
        scale = 1200 / max(image.width, 1)

        image = image.resize(
            (
                int(image.width * scale),
                int(image.height * scale),
            ),
            Image.Resampling.LANCZOS,
        )

    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(1.5)
    image = image.filter(ImageFilter.SHARPEN)

    return image


def extract_text_from_pil_image(
    image: Image.Image,
    language: str = "eng",
) -> str:
    configure_tesseract()

    prepared_image = prepare_image_for_ocr(image)

    try:
        text = pytesseract.image_to_string(
            prepared_image,
            lang=language,
            config="--oem 3 --psm 6",
        )
    except pytesseract.TesseractError as exc:
        raise OCRProcessingError(
            f"Tesseract could not process the image: {exc}"
        ) from exc

    return text.strip()


def extract_text_from_image_bytes(
    image_bytes: bytes,
    language: str = "eng",
) -> str:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.load()
            return extract_text_from_pil_image(image, language)

    except OCRProcessingError:
        raise
    except Exception as exc:
        raise OCRProcessingError(
            "The image could not be prepared for OCR."
        ) from exc