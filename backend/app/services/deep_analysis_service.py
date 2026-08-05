import re
from typing import Any

from app.deep_analysis_schemas import (
    ContentSize,
    DeepAnalysisResponse,
    FactCheckSuggestion,
    SceneSummary,
)


FRAME_DESCRIPTION_PATTERN = re.compile(
    r"\[Frame at\s+"
    r"(?P<timestamp>\d+(?:\.\d+)?)"
    r"\s+seconds\]\s*"
    r"(?P<description>.+)"
)


FACT_CLAIM_MARKERS = [
    "according to",
    "research shows",
    "studies show",
    "scientists say",
    "officially confirmed",
    "guaranteed",
    "cures",
    "causes",
    "proves",
    "always",
    "never",
    "everyone",
    "no one",
]


def calculate_content_size(
    text: str,
    original_size_bytes: int | None = None,
) -> ContentSize:
    cleaned_text = text.strip()

    if original_size_bytes is not None:
        size_bytes = original_size_bytes
    else:
        size_bytes = len(
            cleaned_text.encode("utf-8")
        )

    return ContentSize(
        size_bytes=size_bytes,
        character_count=len(
            cleaned_text
        ),
        word_count=len(
            cleaned_text.split()
        ),
    )


def shorten_text(
    text: str,
    maximum_length: int = 600,
) -> str:
    cleaned_text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if len(cleaned_text) <= maximum_length:
        return cleaned_text

    shortened = cleaned_text[
        :maximum_length
    ].rsplit(
        " ",
        1,
    )[0]

    return f"{shortened}..."


def build_summary(
    content_type: str,
    extracted_text: str,
    ocr_text: str,
    audio_transcript: str,
    visual_description: str,
) -> str:
    if content_type == "image":
        parts: list[str] = []

        if visual_description.strip():
            parts.append(
                "Visual content: "
                + shorten_text(
                    visual_description,
                    350,
                )
            )

        if ocr_text.strip():
            parts.append(
                "Visible text: "
                + shorten_text(
                    ocr_text,
                    250,
                )
            )

        if parts:
            return " ".join(parts)

        return (
            "The image was processed, but no "
            "reliable description or readable "
            "text was available."
        )

    if content_type == "video":
        parts: list[str] = []

        if visual_description.strip():
            parts.append(
                "Sampled scenes: "
                + shorten_text(
                    visual_description,
                    400,
                )
            )

        if audio_transcript.strip():
            parts.append(
                "Spoken content: "
                + shorten_text(
                    audio_transcript,
                    400,
                )
            )

        if ocr_text.strip():
            parts.append(
                "On-screen text: "
                + shorten_text(
                    ocr_text,
                    250,
                )
            )

        if parts:
            return " ".join(parts)

        return (
            "The video was processed, but no "
            "reliable visual description, "
            "on-screen text, or speech transcript "
            "was available."
        )

    primary_text = (
        extracted_text.strip()
        or ocr_text.strip()
    )

    if primary_text:
        return shorten_text(
            primary_text,
            700,
        )

    return (
        "No readable text was available "
        "for summary generation."
    )


def build_scene_summaries(
    visual_description: str,
) -> list[SceneSummary]:
    scenes: list[SceneSummary] = []

    for line in visual_description.splitlines():
        cleaned_line = line.strip()

        if not cleaned_line:
            continue

        match = (
            FRAME_DESCRIPTION_PATTERN.fullmatch(
                cleaned_line
            )
        )

        if not match:
            continue

        timestamp = float(
            match.group("timestamp")
        )

        description = match.group(
            "description"
        ).strip()

        scenes.append(
            SceneSummary(
                timestamp_seconds=timestamp,
                summary=description,
            )
        )

    return scenes


def split_sentences(
    text: str,
) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            text.strip(),
        )
        if sentence.strip()
    ]


def build_fact_check_suggestions(
    text: str,
) -> list[FactCheckSuggestion]:
    suggestions: list[
        FactCheckSuggestion
    ] = []

    for sentence in split_sentences(
        text
    ):
        normalized_sentence = (
            sentence.lower()
        )

        contains_number = bool(
            re.search(
                r"\b\d+(?:\.\d+)?%?\b",
                sentence,
            )
        )

        contains_claim_marker = any(
            marker in normalized_sentence
            for marker in FACT_CLAIM_MARKERS
        )

        if not (
            contains_number
            or contains_claim_marker
        ):
            continue

        priority = (
            "High"
            if contains_claim_marker
            else "Medium"
        )

        suggestions.append(
            FactCheckSuggestion(
                claim=shorten_text(
                    sentence,
                    300,
                ),
                suggestion=(
                    "Verify this claim using an "
                    "authoritative primary source, "
                    "confirm its publication date, "
                    "and compare it with at least "
                    "one independent reliable source."
                ),
                priority=priority,
            )
        )

        if len(suggestions) >= 5:
            break

    return suggestions


def calculate_confidence(
    extracted_text: str,
    ocr_text: str,
    audio_transcript: str,
    visual_description: str,
) -> float:
    evidence_values = [
        extracted_text,
        ocr_text,
        audio_transcript,
        visual_description,
    ]

    evidence_count = sum(
        bool(value.strip())
        for value in evidence_values
    )

    if evidence_count == 0:
        return 0.30

    if evidence_count == 1:
        return 0.55

    if evidence_count == 2:
        return 0.68

    if evidence_count == 3:
        return 0.78

    return 0.84


def suggest_next_step(
    fact_check_suggestions: list[
        FactCheckSuggestion
    ],
    confidence_score: float,
) -> str:
    if confidence_score < 0.50:
        return (
            "Request qualified human review "
            "because the available evidence is "
            "too limited for a reliable automated "
            "deep analysis."
        )

    if fact_check_suggestions:
        return (
            "Verify the identified factual claims "
            "before publishing, approving, or "
            "widely distributing the content."
        )

    return (
        "Compare this report with the normal "
        "moderation decision and escalate any "
        "uncertain or high-risk finding to a "
        "qualified human reviewer."
    )


def create_deep_analysis(
    *,
    content_type: str,
    file_name: str | None = None,
    original_size_bytes: int | None = None,
    extracted_text: str = "",
    ocr_text: str = "",
    audio_transcript: str = "",
    visual_description: str = "",
    metadata: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> DeepAnalysisResponse:
    extraction_metadata = (
        metadata or {}
    )

    combined_text = "\n\n".join(
        value.strip()
        for value in [
            extracted_text,
            ocr_text,
            audio_transcript,
            visual_description,
        ]
        if value.strip()
    )

    fact_check_text = "\n\n".join(
        value.strip()
        for value in [
            extracted_text,
            ocr_text,
            audio_transcript,
        ]
        if value.strip()
    )

    fact_check_suggestions = (
        build_fact_check_suggestions(
            fact_check_text
        )
    )

    confidence_score = (
        calculate_confidence(
            extracted_text=extracted_text,
            ocr_text=ocr_text,
            audio_transcript=(
                audio_transcript
            ),
            visual_description=(
                visual_description
            ),
        )
    )

    duration_value = (
        extraction_metadata.get(
            "duration_seconds"
        )
    )

    if duration_value is not None:
        media_duration_seconds = float(
            duration_value
        )
    else:
        media_duration_seconds = None

    analysis_warnings = list(
        warnings or []
    )

    return DeepAnalysisResponse(
        content_type=content_type,
        file_name=file_name,
        summary=build_summary(
            content_type=content_type,
            extracted_text=extracted_text,
            ocr_text=ocr_text,
            audio_transcript=(
                audio_transcript
            ),
            visual_description=(
                visual_description
            ),
        ),
        scene_by_scene_summary=(
            build_scene_summaries(
                visual_description
            )
            if content_type == "video"
            else []
        ),
        exact_ocr_text=ocr_text.strip(),
        content_size=(
            calculate_content_size(
                text=combined_text,
                original_size_bytes=(
                    original_size_bytes
                ),
            )
        ),
        media_duration_seconds=(
            media_duration_seconds
        ),
        confidence_score=round(
            confidence_score,
            2,
        ),
        fact_check_suggestions=(
            fact_check_suggestions
        ),
        suggested_next_step=(
            suggest_next_step(
                fact_check_suggestions=(
                    fact_check_suggestions
                ),
                confidence_score=(
                    confidence_score
                ),
            )
        ),
        analysis_status={
            "summary": "available",
            "scene_summary": (
                "available"
                if content_type == "video"
                else "not_applicable"
            ),
            "ocr": (
                "available"
                if ocr_text.strip()
                else "no_text_detected"
            ),
            "fact_checking": (
                "suggestions_available"
                if fact_check_suggestions
                else "no_claims_flagged"
            ),
        },
        extraction_metadata=(
            extraction_metadata
        ),
        warnings=analysis_warnings,
    )