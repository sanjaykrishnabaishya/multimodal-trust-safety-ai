import re
import shutil
from io import BytesIO
from pathlib import Path

import pytesseract
from PIL import (
    Image,
    ImageEnhance,
    ImageFilter,
    ImageOps,
)
from pytesseract import Output


COMMON_TESSERACT_PATHS = [
    Path(
        r"C:\Program Files\Tesseract-OCR"
        r"\tesseract.exe"
    ),
    Path(
        r"C:\Program Files (x86)"
        r"\Tesseract-OCR\tesseract.exe"
    ),
]

MINIMUM_WORD_CONFIDENCE = 55.0
MINIMUM_ALPHANUMERIC_CHARACTERS = 4


class OCRProcessingError(Exception):
    pass


def configure_tesseract() -> str:
    command_from_path = shutil.which(
        "tesseract"
    )

    if command_from_path:
        pytesseract.pytesseract.tesseract_cmd = (
            command_from_path
        )
        return command_from_path

    for candidate in COMMON_TESSERACT_PATHS:
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = (
                str(candidate)
            )
            return str(candidate)

    raise OCRProcessingError(
        "Tesseract OCR was not found. Install it in "
        r"C:\Program Files\Tesseract-OCR "
        "or add it to Windows PATH."
    )


def get_ocr_status() -> dict:
    try:
        executable = configure_tesseract()
        version = str(
            pytesseract.get_tesseract_version()
        )

        languages = sorted(
            pytesseract.get_languages(
                config=""
            )
        )

        return {
            "available": True,
            "engine": "Tesseract",
            "version": version,
            "executable": executable,
            "languages": languages,
            "minimum_word_confidence": (
                MINIMUM_WORD_CONFIDENCE
            ),
        }

    except Exception as exc:
        return {
            "available": False,
            "engine": "Tesseract",
            "error": str(exc),
        }


def prepare_image_for_ocr(
    image: Image.Image,
) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")

    if image.width < 1200:
        scale = 1200 / max(
            image.width,
            1,
        )

        image = image.resize(
            (
                int(image.width * scale),
                int(image.height * scale),
            ),
            Image.Resampling.LANCZOS,
        )

    image = ImageOps.autocontrast(image)

    image = ImageEnhance.Contrast(
        image
    ).enhance(1.5)

    image = image.filter(
        ImageFilter.SHARPEN
    )

    return image


def is_meaningful_token(
    token: str,
    confidence: float,
) -> bool:
    if confidence < MINIMUM_WORD_CONFIDENCE:
        return False

    cleaned = token.strip()

    if not cleaned:
        return False

    alphanumeric = re.sub(
        r"[^A-Za-z0-9]",
        "",
        cleaned,
    )

    if len(alphanumeric) < 2:
        return False

    return True


def extract_confident_text(
    prepared_image: Image.Image,
    language: str,
) -> str:
    try:
        data = pytesseract.image_to_data(
            prepared_image,
            lang=language,
            config="--oem 3 --psm 6",
            output_type=Output.DICT,
        )

    except pytesseract.TesseractError as exc:
        raise OCRProcessingError(
            "Tesseract could not process "
            f"the image: {exc}"
        ) from exc

    lines: dict[tuple, list[str]] = {}

    word_count = len(
        data.get("text", [])
    )

    for index in range(word_count):
        token = str(
            data["text"][index]
        ).strip()

        try:
            confidence = float(
                data["conf"][index]
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence = -1.0

        if not is_meaningful_token(
            token,
            confidence,
        ):
            continue

        line_key = (
            data.get(
                "page_num",
                [0] * word_count,
            )[index],
            data.get(
                "block_num",
                [0] * word_count,
            )[index],
            data.get(
                "par_num",
                [0] * word_count,
            )[index],
            data.get(
                "line_num",
                [0] * word_count,
            )[index],
        )

        lines.setdefault(
            line_key,
            [],
        ).append(token)

    detected_lines = [
        " ".join(words)
        for words in lines.values()
        if words
    ]

    detected_text = "\n".join(
        detected_lines
    ).strip()

    alphanumeric_count = len(
        re.sub(
            r"[^A-Za-z0-9]",
            "",
            detected_text,
        )
    )

    if (
        alphanumeric_count
        < MINIMUM_ALPHANUMERIC_CHARACTERS
    ):
        return ""

    return detected_text


def extract_text_from_pil_image(
    image: Image.Image,
    language: str = "eng",
) -> str:
    configure_tesseract()

    prepared_image = prepare_image_for_ocr(
        image
    )

    return extract_confident_text(
        prepared_image,
        language,
    )


def extract_text_from_image_bytes(
    image_bytes: bytes,
    language: str = "eng",
) -> str:
    try:
        with Image.open(
            BytesIO(image_bytes)
        ) as image:
            image.load()

            return extract_text_from_pil_image(
                image,
                language,
            )

    except OCRProcessingError:
        raise

    except Exception as exc:
        raise OCRProcessingError(
            "The image could not be "
            "prepared for OCR."
        ) from exc