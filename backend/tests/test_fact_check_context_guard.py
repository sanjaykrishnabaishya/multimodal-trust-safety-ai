"""Authored English routing fixtures, not an independent accuracy holdout."""
import pytest

from app.services.fact_check_context_guard import context_review_reason
from app.services import fact_check_fusion_service as fusion


REVIEW_TEXTS = [
    "I think Paris is the capital of Germany.",
    "In my opinion, this drink cures diabetes.",
    "I believe the medicine was banned yesterday.",
    "Someone said the bridge is located in Rome.",
    "A post claims the vaccine causes infertility, and I agree.",
    "The article reports that the government approved the project.",
    "Correction: the claim that this herb cures cancer is not true.",
    "This is satire: the mayor announced a tax on clouds.",
    "In this fictional story, Earth orbits Mars.",
    "The minister might have ordered the closure.",
    "I predict the agency approved the application.",
    "Paris is the capital of France. Why is the museum closed?",
    "Is the post accurate? It says this treatment prevents infection.",
    "The company was founded in 1900; its office is located in Milan.",
    "The city banned cars, but buses are still running.",
    "According to the survey, 70% agreed.",
]
PASS_THROUGH_TEXTS = [
    "I think this is the best film.",
    "In my opinion, blue looks beautiful.",
    "What is the capital of France?",
    "Someone said they enjoyed the concert.",
    "This is a clearly marked parody account.",
    "Never share your password with strangers.",
    "Paris is the capital of France.",
    "The tower is located in Paris.",
]


@pytest.mark.parametrize("text", REVIEW_TEXTS)
def test_context_requires_review_without_provider(monkeypatch, text):
    def fail(*args, **kwargs):
        pytest.fail("Context needs separation, not a whole-message truth verdict")
    monkeypatch.setattr(fusion, "analyze_fact_check", fail)
    result = fusion.analyze_fact_check_for_fusion(text, fusion.NORMAL_CATEGORY)
    assert result["category"] == "Uncertain"
    assert result["human_review_required"] is True
    assert result["automatic_enforcement_allowed"] is False
    assert result["analysis"]["evidence_provider_used"] is False


@pytest.mark.parametrize("text", PASS_THROUGH_TEXTS)
def test_guard_preserves_existing_route(text):
    assert context_review_reason(text) is None


def test_long_input_requires_separation(monkeypatch):
    result = fusion.analyze_fact_check_for_fusion("x" * 5001, fusion.NORMAL_CATEGORY)
    assert result["category"] == "Uncertain"


def test_existing_category_keeps_priority(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("Do not call evidence service for another category")
    monkeypatch.setattr(fusion, "analyze_fact_check", fail)
    result = fusion.analyze_fact_check_for_fusion(REVIEW_TEXTS[0], "Violent Content")
    assert result["decision_override_allowed"] is False


def test_fixtures_are_distinct():
    texts = REVIEW_TEXTS + PASS_THROUGH_TEXTS
    assert len(texts) == len(set(texts)) == 24
