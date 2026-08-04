import os
import tempfile
from pathlib import Path

import cv2
from PIL import Image

from app.services.ocr_service import (
    OCRProcessingError,
    extract_text_from_pil_image,
)
from app.services.transcription_service import (
    TranscriptionProcessingError,
    transcribe_media,
)
from app.services.visual_service import (
    VisualProcessingError,
    describe_pil_image,
)


SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
}

MAX_SAMPLE_FRAMES = 12
MAX_VISUAL_DESCRIPTION_FRAMES = 4


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
        round(
            index
            * (frame_count - 1)
            / (sample_count - 1)
        )
        for index in range(sample_count)
    ]


def process_video(
    file_name: str,
    file_bytes: bytes,
) -> dict:
    extension = Path(
        file_name
    ).suffix.lower()

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

        capture = cv2.VideoCapture(
            temporary_path
        )

        if not capture.isOpened():
            raise VideoProcessingError(
                "The video could not be "
                "opened or decoded."
            )

        fps = float(
            capture.get(
                cv2.CAP_PROP_FPS
            )
        )
        frame_count = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
        )
        width = int(
            capture.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
        )
        height = int(
            capture.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
        )

        duration_seconds = (
            frame_count / fps
            if fps > 0 and frame_count > 0
            else 0.0
        )

        desired_samples = min(
            MAX_SAMPLE_FRAMES,
            max(
                1,
                int(duration_seconds // 5)
                + 1,
            ),
        )

        positions = calculate_sample_positions(
            frame_count,
            desired_samples,
        )

        sample_timestamps: list[float] = []
        frame_ocr_results: list[str] = []
        frame_visual_results: list[str] = []
        seen_visual_descriptions: set[str] = set()

        readable_frame_count = 0
        visual_frame_count = 0
        ocr_failure_count = 0
        visual_failure_count = 0

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

            rounded_timestamp = round(
                timestamp,
                2,
            )

            sample_timestamps.append(
                rounded_timestamp
            )
            readable_frame_count += 1

            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            pil_image = Image.fromarray(
                rgb_frame
            )

            try:
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

            if (
                visual_frame_count
                < MAX_VISUAL_DESCRIPTION_FRAMES
            ):
                try:
                    description = (
                        describe_pil_image(
                            pil_image
                        )
                    ).strip()

                    visual_frame_count += 1

                    normalized_description = (
                        description.lower()
                    )

                    if (
                        description
                        and normalized_description
                        not in seen_visual_descriptions
                    ):
                        seen_visual_descriptions.add(
                            normalized_description
                        )

                        frame_visual_results.append(
                            f"[Frame at "
                            f"{rounded_timestamp} seconds] "
                            f"{description}"
                        )

                except VisualProcessingError:
                    visual_failure_count += 1
                    visual_frame_count += 1

        if readable_frame_count == 0:
            raise VideoProcessingError(
                "No readable frames could be "
                "extracted from the video."
            )

        audio_transcript = ""
        transcription_metadata: dict = {}
        transcription_warning: str | None = None

        try:
            (
                audio_transcript,
                transcription_metadata,
            ) = transcribe_media(
                temporary_path
            )

            if not audio_transcript:
                transcription_warning = (
                    "No intelligible speech was "
                    "detected in the video audio."
                )

        except TranscriptionProcessingError as exc:
            transcription_warning = (
                "Speech transcription warning: "
                f"{exc}"
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
            "visually_analyzed_frame_count": (
                visual_frame_count
            ),
            "unique_visual_description_count": (
                len(frame_visual_results)
            ),
            "ocr_failure_count": (
                ocr_failure_count
            ),
            "visual_failure_count": (
                visual_failure_count
            ),
            "sample_timestamps_seconds": (
                sample_timestamps
            ),
            **transcription_metadata,
        }

        warnings = [
            "Video metadata and sampled frames "
            "were processed.",
            "Sampled frames were not "
            "permanently stored.",
            "OCR used a minimum-confidence filter.",
            "Visual descriptions were generated "
            "from a limited number of frames.",
            "General visual captions can be "
            "incomplete or inaccurate.",
        ]

        if not frame_ocr_results:
            warnings.append(
                "No sufficiently confident English "
                "text was detected in sampled frames."
            )

        if not frame_visual_results:
            warnings.append(
                "No visual frame description "
                "was generated."
            )

        if ocr_failure_count:
            warnings.append(
                f"OCR failed on "
                f"{ocr_failure_count} frame(s)."
            )

        if visual_failure_count:
            warnings.append(
                f"Visual description failed on "
                f"{visual_failure_count} frame(s)."
            )

        if transcription_warning:
            warnings.append(
                transcription_warning
            )

        return {
            "audio_transcript": audio_transcript,
            "ocr_text": "\n\n".join(
                frame_ocr_results
            ),
            "visual_description": "\n".join(
                frame_visual_results
            ),
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
            and os.path.exists(
                temporary_path
            )
        ):
            try:
                os.remove(
                    temporary_path
                )
            except OSError:
                pass