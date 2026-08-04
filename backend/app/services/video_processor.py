import os
import tempfile
from pathlib import Path

import cv2
from PIL import Image

from app.services.ocr_service import (
    OCRProcessingError,
    extract_text_from_pil_image,
)


SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
}

MAX_SAMPLE_FRAMES = 12


class VideoProcessingError(Exception):
    pass


def calculate_sample_positions(
    frame_count: int,
    sample_count: int,
) -> list[int]:
    if frame_count <= 0:
        return []

    if sample_count <= 1:
        return [0]

    return [
        round(index * (frame_count - 1) / (sample_count - 1))
        for index in range(sample_count)
    ]


def process_video(
    file_name: str,
    file_bytes: bytes,
) -> dict:
    extension = Path(file_name).suffix.lower()

    if extension not in SUPPORTED_VIDEO_EXTENSIONS:
        raise VideoProcessingError(
            f"Unsupported video type: {extension}"
        )

    temporary_path: str | None = None
    capture = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temporary_file:
            temporary_file.write(file_bytes)
            temporary_path = temporary_file.name

        capture = cv2.VideoCapture(temporary_path)

        if not capture.isOpened():
            raise VideoProcessingError(
                "The video could not be opened or decoded."
            )

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT)
        )
        width = int(
            capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        )
        height = int(
            capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        )

        duration_seconds = (
            frame_count / fps
            if fps > 0 and frame_count > 0
            else 0.0
        )

        desired_samples = min(
            MAX_SAMPLE_FRAMES,
            max(1, int(duration_seconds // 5) + 1),
        )

        positions = calculate_sample_positions(
            frame_count,
            desired_samples,
        )

        sample_timestamps: list[float] = []
        frame_ocr_results: list[str] = []
        readable_frame_count = 0
        ocr_failure_count = 0

        for position in positions:
            capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                position,
            )

            success, frame = capture.read()

            if not success:
                continue

            timestamp = (
                position / fps
                if fps > 0
                else 0.0
            )

            rounded_timestamp = round(timestamp, 2)

            sample_timestamps.append(rounded_timestamp)
            readable_frame_count += 1

            try:
                rgb_frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB,
                )

                pil_image = Image.fromarray(rgb_frame)

                detected_text = (
                    extract_text_from_pil_image(
                        pil_image
                    )
                )

                if detected_text:
                    frame_ocr_results.append(
                        f"[Frame at "
                        f"{rounded_timestamp} seconds]\n"
                        f"{detected_text}"
                    )

            except OCRProcessingError:
                ocr_failure_count += 1

        if readable_frame_count == 0:
            raise VideoProcessingError(
                "No readable frames could be extracted "
                "from the video."
            )

        metadata = {
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "frame_count": frame_count,
            "duration_seconds": round(
                duration_seconds,
                2,
            ),
            "sampled_frame_count": (
                readable_frame_count
            ),
            "frames_with_ocr_text": len(
                frame_ocr_results
            ),
            "ocr_failure_count": ocr_failure_count,
            "sample_timestamps_seconds": (
                sample_timestamps
            ),
        }

        warnings = [
            "Video metadata and sample frames were processed.",
            "Sampled frames were not permanently stored.",
            "OCR checked visible text in sampled frames.",
            "Speech transcription and full visual "
            "understanding have not been connected yet.",
        ]

        if not frame_ocr_results:
            warnings.append(
                "No readable English text was detected "
                "in the sampled video frames."
            )

        if ocr_failure_count:
            warnings.append(
                f"OCR failed on {ocr_failure_count} "
                f"sampled frame(s)."
            )

        return {
            "audio_transcript": "",
            "ocr_text": "\n\n".join(
                frame_ocr_results
            ),
            "visual_description": "",
            "metadata": metadata,
            "warnings": warnings,
        }

    except VideoProcessingError:
        raise

    except Exception as exc:
        raise VideoProcessingError(
            "An unexpected error occurred while "
            "processing the video."
        ) from exc

    finally:
        if capture is not None:
            capture.release()

        if (
            temporary_path
            and os.path.exists(temporary_path)
        ):
            try:
                os.remove(temporary_path)
            except OSError:
                pass