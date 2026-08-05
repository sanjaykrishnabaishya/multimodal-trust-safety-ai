from typing import (
    Any,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
)


ReviewStatus = Literal[
    "pending",
    "approved",
    "overturned",
    "escalated",
    "closed",
]


class ReviewCaseResponse(BaseModel):
    case_id: str
    created_at: str
    updated_at: str

    content_type: str
    file_name: str | None = None
    content_preview: str

    category: str
    severity: str
    action: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    human_review_required: bool
    reason: str

    review_status: ReviewStatus

    reviewer_name: str | None = None
    reviewer_notes: str | None = None

    final_category: str | None = None
    final_action: str | None = None
    reviewed_at: str | None = None


class ReviewCaseUpdateRequest(
    BaseModel
):
    review_status: ReviewStatus

    reviewer_name: str = Field(
        min_length=1,
        max_length=100,
    )

    reviewer_notes: str = Field(
        default="",
        max_length=2_000,
    )

    final_category: (
        str | None
    ) = Field(
        default=None,
        max_length=100,
    )

    final_action: (
        str | None
    ) = Field(
        default=None,
        max_length=200,
    )


class AuditEventResponse(BaseModel):
    event_id: int
    case_id: str
    event_type: str

    event_data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    created_at: str