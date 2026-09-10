"""Conservative English context guard, not a truth or intent classifier."""
import re

# Narrow claim cues avoid treating taste ("best film") as a factual verdict.
FACT_CUE = re.compile(
    r"\b(capital of|located in|orbits|revolves around|causes|prevents|"
    r"cures|banned|approved|ordered|announced|invented|founded)\b|\d\s*%",
    re.I,
)
CONTEXT_CUE = re.compile(
    r"\b(i think|i believe|in my opinion|i feel|someone said|a post claims|"
    r"a message says|according to|the article reports|the report describes|"
    r"the documentary discusses|the news article mentions|it is rumored|"
    r"the headline claims|correction|fact check|fact-check|not true|"
    r"false claim|debunk|satire|parody|fictional|might|may|could|predict)\b",
    re.I,
)


def context_review_reason(text: str) -> str | None:
    """Do not pass whole contextual/multi-claim messages to a single-claim engine.

    Cue matching is deliberately limited and cannot prove endorsement, satire,
    completeness, or factuality. These cases require claim/context separation.
    """
    if len(text) > 5000:
        return "Long text requires claim separation before fact-checking."
    if not FACT_CUE.search(text):
        return None
    if CONTEXT_CUE.search(text):
        return "Separate factual content from opinion, attribution or correction before review."
    parts = [part.strip() for part in re.split(r"[.!?;]+\s*", text) if part.strip()]
    if len(parts) > 1 or re.search(r"\b(and|but|however)\b", text, re.I):
        return "Multiple clauses require claim-by-claim review."
    return None
