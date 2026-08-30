from __future__ import annotations

import json

from app.services import openrouter_advisory_service as service


VALID_KEY = "sk-or-v1-" + ("x" * 64)


def configure(monkeypatch):
    monkeypatch.setattr(service, "_setting_is_enabled", lambda: True)
    monkeypatch.setattr(service, "_configured_api_key", lambda: VALID_KEY)


def provider_response(**overrides):
    result = {
        "verdict": "illegal_activity_candidate",
        "family": "controlled_substances",
        "confidence": 0.91,
        "facilitation_present": True,
        "transaction_present": True,
        "safe_context_present": False,
        "jurisdiction_uncertain": False,
        "requires_human_review": True,
        "policy_ids": ["ILLEGAL-CONTROLLED-GOODS"],
        "rationale": "Transaction evidence matches the supplied product policy.",
    }
    result.update(overrides)
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(result),
                }
            }
        ]
    }


POLICY_EVIDENCE = [
    {
        "policy_id": "ILLEGAL-CONTROLLED-GOODS",
        "family": "controlled_substances",
        "rule": "Transaction signals require review.",
    }
]


def test_strict_schema_and_private_provider_contract(monkeypatch):
    configure(monkeypatch)
    captured = {}

    def fake_post(payload, api_key):
        captured["payload"] = payload
        captured["key_valid"] = api_key == VALID_KEY
        return provider_response()

    monkeypatch.setattr(service, "_post_payload", fake_post)
    result = service.analyze_illegal_activities_with_openrouter(
        "Illegal drugs are for sale. Contact me to order now.",
        POLICY_EVIDENCE,
    )

    assert result["used"] is True
    assert result["status"] == "schema_validated"
    assert result["automatic_enforcement_allowed"] is False
    assert result["llm_can_create_allow"] is False
    assert captured["key_valid"] is True
    payload = captured["payload"]
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["provider"] == {
        "data_collection": "deny",
        "zdr": True,
        "require_parameters": True,
        "allow_fallbacks": False,
    }


def test_sensitive_identifier_is_never_sent(monkeypatch):
    configure(monkeypatch)

    def must_not_post(*args, **kwargs):
        raise AssertionError("Sensitive content reached the provider.")

    monkeypatch.setattr(service, "_post_payload", must_not_post)
    result = service.analyze_illegal_activities_with_openrouter(
        "Contact user@example.com about illegal drugs.",
        POLICY_EVIDENCE,
    )
    assert result["used"] is False
    assert result["status"] == "sensitive_identifier_detected"


def test_child_safety_boundary_is_never_sent(monkeypatch):
    configure(monkeypatch)

    def must_not_post(*args, **kwargs):
        raise AssertionError("Child-risk content reached the provider.")

    monkeypatch.setattr(service, "_post_payload", must_not_post)
    result = service.analyze_illegal_activities_with_openrouter(
        "An underage child was asked for a private image.",
        POLICY_EVIDENCE,
    )
    assert result["used"] is False
    assert result["status"] == "child_safety_boundary"


def test_invalid_or_extra_model_output_fails_closed(monkeypatch):
    configure(monkeypatch)
    invalid = provider_response(unapproved_field="must be rejected")
    monkeypatch.setattr(service, "_post_payload", lambda *_: invalid)
    result = service.analyze_illegal_activities_with_openrouter(
        "An online betting service has unknown licensing.",
        POLICY_EVIDENCE,
    )
    assert result["used"] is False
    assert result["status"] == "schema_rejected_fail_closed"
    assert result["requires_human_review"] is True
    assert result["schema_attempts"] == 2


def test_single_schema_failure_gets_one_bounded_retry(monkeypatch):
    configure(monkeypatch)
    responses = [
        provider_response(unapproved_field="rejected"),
        provider_response(),
    ]

    monkeypatch.setattr(
        service,
        "_post_payload",
        lambda *_: responses.pop(0),
    )
    result = service.analyze_illegal_activities_with_openrouter(
        "Illegal drugs are for sale. Contact me to order now.",
        POLICY_EVIDENCE,
    )
    assert result["used"] is True
    assert result["schema_attempts"] == 2
    assert responses == []


def test_model_cannot_remove_review_from_illegal_candidate(monkeypatch):
    configure(monkeypatch)
    invalid = provider_response(requires_human_review=False)
    monkeypatch.setattr(service, "_post_payload", lambda *_: invalid)
    result = service.analyze_illegal_activities_with_openrouter(
        "Illegal drugs are for sale. Contact me to order now.",
        POLICY_EVIDENCE,
    )
    assert result["used"] is False
    assert result["status"] == "authority_contract_rejected"


def test_provider_error_does_not_expose_response_body(monkeypatch):
    configure(monkeypatch)

    def fail(*args):
        request = service.httpx.Request("POST", service.OPENROUTER_ENDPOINT)
        response = service.httpx.Response(
            401,
            request=request,
            text="secret provider diagnostic",
        )
        raise service.httpx.HTTPStatusError(
            "request failed",
            request=request,
            response=response,
        )

    monkeypatch.setattr(service, "_post_payload", fail)
    result = service.analyze_illegal_activities_with_openrouter(
        "Illegal drugs are for sale. Contact me to order now.",
        POLICY_EVIDENCE,
    )
    assert result["status"] == "provider_http_401"
    assert "secret" not in str(result)
