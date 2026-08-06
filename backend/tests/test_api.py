import pytest
from fastapi.testclient import (
    TestClient,
)

from app.main import app
from app.services import (
    review_database_service,
)


SPAM_CATEGORY = "Spam, Scam & Phishing"
VIOLENT_CATEGORY = "Violent Content"
PRIVATE_CATEGORY = (
    "Publishing Private Information"
)
NORMAL_CATEGORY = "Normal/Ignore"


@pytest.fixture(autouse=True)
def use_temporary_database(
    tmp_path,
    monkeypatch,
):
    temporary_data_directory = (
        tmp_path / "data"
    )

    temporary_database_path = (
        temporary_data_directory
        / "test_trust_safety.db"
    )

    monkeypatch.setattr(
        review_database_service,
        "DATA_DIRECTORY",
        temporary_data_directory,
    )

    monkeypatch.setattr(
        review_database_service,
        "DATABASE_PATH",
        temporary_database_path,
    )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_main_health_endpoint(
    client,
):
    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "healthy"
    assert "version" in result


def test_moderation_health_endpoint(
    client,
):
    response = client.get(
        "/moderation/health"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "available"

    assert (
        result[
            "review_storage_enabled"
        ]
        is True
    )


def test_deep_analysis_health_endpoint(
    client,
):
    response = client.get(
        "/deep-analysis/health"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "available"
    assert result["summary"] is True
    assert result["ocr_reporting"] is True


def test_review_health_endpoint(
    client,
):
    response = client.get(
        "/review/health"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["status"] == "available"

    assert (
        result["database_connected"]
        is True
    )


def test_text_moderation_creates_case(
    client,
):
    response = client.post(
        "/moderation/text",
        json={
            "text": (
                "Your account is blocked. "
                "Send your OTP and password "
                "immediately."
            ),
            "source_context": "unknown",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["content_type"] == "text"

    assert (
        result["category"]
        == SPAM_CATEGORY
    )

    assert result["review_case_id"]
    assert result["review_status"]

    assert (
        0.0
        <= result["confidence"]
        <= 1.0
    )


def test_private_information_requires_review(
    client,
):
    response = client.post(
        "/moderation/text",
        json={
            "text": (
                "His private email is "
                "john.smith@gmail.com."
            ),
            "source_context": "unknown",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["content_type"] == "text"

    assert (
        result["category"]
        == PRIVATE_CATEGORY
    )

    assert (
        result["action"]
        == "Refer to human review"
    )

    assert (
        result["human_review_required"]
        is True
    )

    assert (
        0.0
        <= result["confidence"]
        <= 1.0
    )

    assert result["review_case_id"]


def test_normal_news_is_not_private_information(
    client,
):
    response = client.post(
        "/moderation/text",
        json={
            "text": (
                "Microsoft announced a new "
                "office in London on Tuesday."
            ),
            "source_context": "unknown",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert (
        result["category"]
        == NORMAL_CATEGORY
    )

    assert result["action"] == "Allow"

    assert (
        result["human_review_required"]
        is False
    )


def test_preventative_security_advice_is_safe(
    client,
):
    response = client.post(
        "/moderation/text",
        json={
            "text": (
                "Never share your OTP or "
                "password with anyone."
            ),
            "source_context": "unknown",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert (
        result["category"]
        == NORMAL_CATEGORY
    )

    assert result["action"] == "Allow"


def test_text_deep_analysis(
    client,
):
    response = client.post(
        "/deep-analysis/text",
        json={
            "text": (
                "A short article claims "
                "that a city introduced "
                "a new public policy."
            )
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["content_type"] == "text"
    assert result["summary"]
    assert result["content_size"]
    assert result["confidence_score"]

    assert isinstance(
        result["fact_check_suggestions"],
        list,
    )

    assert isinstance(
        result["suggested_next_step"],
        str,
    )

    assert result["suggested_next_step"]


def test_review_case_workflow(
    client,
):
    moderation_response = client.post(
        "/moderation/text",
        json={
            "text": (
                "I will kill you tonight."
            ),
            "source_context": "unknown",
        },
    )

    assert (
        moderation_response.status_code
        == 200
    )

    moderation_result = (
        moderation_response.json()
    )

    case_id = moderation_result[
        "review_case_id"
    ]

    assert case_id

    case_response = client.get(
        f"/review/cases/{case_id}"
    )

    assert case_response.status_code == 200

    case_result = case_response.json()

    assert (
        case_result["case_id"]
        == case_id
    )

    assert (
        case_result["category"]
        == VIOLENT_CATEGORY
    )

    update_response = client.patch(
        f"/review/cases/{case_id}",
        json={
            "review_status": "approved",
            "reviewer_name": (
                "Automated Test Reviewer"
            ),
            "reviewer_notes": (
                "Verified during an "
                "automated API test."
            ),
            "final_category": (
                VIOLENT_CATEGORY
            ),
            "final_action": (
                "Block and escalate"
            ),
        },
    )

    assert (
        update_response.status_code
        == 200
    )

    updated_case = (
        update_response.json()
    )

    assert (
        updated_case["review_status"]
        == "approved"
    )

    assert (
        updated_case["reviewer_name"]
        == "Automated Test Reviewer"
    )

    assert (
        updated_case["final_category"]
        == VIOLENT_CATEGORY
    )

    audit_response = client.get(
        f"/review/cases/{case_id}/audit"
    )

    assert (
        audit_response.status_code
        == 200
    )

    audit_events = (
        audit_response.json()
    )

    event_types = {
        event["event_type"]
        for event in audit_events
    }

    assert "case_created" in event_types

    assert (
        "human_review_updated"
        in event_types
    )


def test_unknown_review_case_returns_404(
    client,
):
    response = client.get(
        "/review/cases/"
        "case-that-does-not-exist"
    )

    assert response.status_code == 404


def test_empty_text_is_rejected(
    client,
):
    response = client.post(
        "/moderation/text",
        json={
            "text": "",
            "source_context": "unknown",
        },
    )

    assert response.status_code == 422


def test_unsupported_file_is_rejected(
    client,
):
    response = client.post(
        "/moderation/file",
        files={
            "file": (
                "unsafe.exe",
                b"not-a-real-program",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 415