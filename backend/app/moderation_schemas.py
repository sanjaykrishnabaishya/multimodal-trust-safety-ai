from typing import (
    Any,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.policy_config import (
    ModerationCategory,
    normalize_category_name,
)


ContentType = Literal[
    "text",
    "document",
    "image",
    "video",
]

# Uncertain is a decision state, not an additional policy category.
DecisionCategory = ModerationCategory | Literal["Uncertain"]


class ModerationTextRequest(
    BaseModel
):
    text: str = Field(
        min_length=1,
        max_length=100_000,
    )

    source_context: str = Field(
        default="unknown",
        max_length=100,
    )


class ModerationResponse(
    BaseModel
):
    content_type: ContentType

    file_name: (
        str | None
    ) = None

    category: DecisionCategory

    severity: str

    action: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    human_review_required: bool

    reason: str

    review_case_id: (
        str | None
    ) = None

    review_status: (
        str | None
    ) = None

    source_context: str

    matched_signals: list[
        str
    ] = Field(
        default_factory=list,
    )

    decision_sources: list[
        str
    ] = Field(
        default_factory=list,
    )

    rag_used: bool = False

    rag_consensus: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    illegal_activities_v1_used: bool = False

    illegal_activities_v1: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    illegal_activities_v1_fusion_status: str = "not_evaluated"

    illegal_activities_v2_rc2_used: bool = False

    illegal_activities_v2_rc2: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    illegal_activities_v2_rc2_fusion_status: str = "not_evaluated"

    illegal_activities_automatic_enforcement_allowed: bool = False

    child_exploitation_v1_rc1_used: bool = False

    child_exploitation_v1_rc1: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    child_exploitation_v1_rc1_fusion_status: str = "not_evaluated"

    child_exploitation_automatic_enforcement_allowed: bool = False

    invasion_of_privacy_v1_rc1_used: bool = False

    invasion_of_privacy_v1_rc1: dict[
        str,
        Any,
    ] = Field(default_factory=dict)

    invasion_of_privacy_v1_rc1_fusion_status: str = "not_evaluated"

    invasion_of_privacy_automatic_enforcement_allowed: bool = False

    malicious_programs_v2_rc2_used: bool = False

    malicious_programs_v2_rc2: dict[
        str,
        Any,
    ] = Field(default_factory=dict)

    malicious_programs_v2_rc2_fusion_status: str = "not_evaluated"

    malicious_programs_automatic_enforcement_allowed: bool = False

    retrieved_evidence: list[
        dict[str, Any]
    ] = Field(
        default_factory=list,
    )

    analyzed_text_preview: str = ""

    extraction_metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    warnings: list[
        str
    ] = Field(
        default_factory=list,
    )

    @field_validator(
        "category",
        mode="before",
    )
    @classmethod
    def normalize_category(
        cls,
        value: object,
    ) -> str:
        if isinstance(
            value,
            ModerationCategory,
        ):
            return value.value

        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                "Moderation category "
                "must be text."
            )

        if value.strip() == "Uncertain":
            return "Uncertain"

        try:
            return (
                normalize_category_name(
                    value
                )
            )

        except (
            ValueError,
            KeyError,
        ) as exc:
            raise ValueError(
                "Unsupported moderation "
                f"category: {value}"
            ) from exc
