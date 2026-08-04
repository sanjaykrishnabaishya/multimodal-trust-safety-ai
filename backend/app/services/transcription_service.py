from functools import lru_cache
from pathlib import Path

from faster_whisper import WhisperModel


WHISPER_MODEL_SIZE = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"


class TranscriptionProcessingError(Exception):
    pass


@lru_cache(maxsize=1)
def get_transcription_model() -> WhisperModel:
    try:
        return WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )

    except Exception as exc:
        raise TranscriptionProcessingError(
            "The speech transcription model could not "
            "be downloaded or loaded."
        ) from exc


def get_transcription_status() -> dict:
    return {
        "available": True,
        "engine": "faster-whisper",
        "model": WHISPER_MODEL_SIZE,
        "device": WHISPER_DEVICE,
        "compute_type": WHISPER_COMPUTE_TYPE,
        "model_loaded": (
            get_transcription_model.cache_info().currsize > 0
        ),
        "note": (
            "The model is downloaded and loaded during "
            "the first video transcription."
        ),
    }


def transcribe_media(
    media_path: str,
) -> tuple[str, dict]:
    path = Path(media_path)

    if not path.exists():
        raise TranscriptionProcessingError(
            "The temporary media file does not exist."
        )

    try:
        model = get_transcription_model()

        segments, info = model.transcribe(
            str(path),
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        transcript_parts: list[str] = []
        segment_details: list[dict] = []

        for segment in segments:
            text = segment.text.strip()

            if not text:
                continue

            transcript_parts.append(text)

            segment_details.append(
                {
                    "start_seconds": round(
                        segment.start,
                        2,
                    ),
                    "end_seconds": round(
                        segment.end,
                        2,
                    ),
                    "text": text,
                }
            )

        transcript = " ".join(
            transcript_parts
        ).strip()

        metadata = {
            "transcription_engine": "faster-whisper",
            "transcription_model": WHISPER_MODEL_SIZE,
            "detected_language": info.language,
            "language_probability": round(
                info.language_probability,
                4,
            ),
            "transcript_segment_count": len(
                segment_details
            ),
            "transcript_segments": segment_details,
        }

        return transcript, metadata

    except TranscriptionProcessingError:
        raise

    except Exception as exc:
        raise TranscriptionProcessingError(
            "The audio track could not be transcribed."
        ) from exc