# Phase 9B: keep context with the claim

## What changed

Previously, phrases like "I think" or "a post claims" could make the router
skip the whole message. But an opinion can also contain a factual statement.
For example, "I think Paris is the capital of Germany" contains a claim that
can be checked. A correction can quote a false statement without endorsing it.

An English context guard now runs before those skip rules. It recognizes a
limited set of factual cues, such as location, cause, cure, government decisions,
and percentages. When these appear with opinion, attribution, correction,
fiction, uncertainty, or multiple clauses, it asks for human review. It does
not send the entire mixed message to the single-claim evidence engine.

## Moderation rules

- Context plus a recognized factual cue: Uncertain, human review, no automatic
  misinformation accusation or enforcement.
- Multiple clauses plus a recognized factual cue: claim-by-claim review.
- More than 5,000 characters: review for claim separation.
- Pure taste, a simple question, or a disclosure without factual cues: preserve
  the existing router's behavior. Passing this guard does not mean approval.
- Other moderation categories retain priority.
- Straightforward claims still use the existing evidence engine and Phase 9A
  handoff checks. A supported claim can retain the existing Allow recommendation;
  refuted or insufficiently supported claims require review.

## Why this design

Small, deterministic Python checks are auditable and require no new framework,
API key, paid request, training, or media upload. They are a temporary safety
boundary, not language understanding. They can miss paraphrases and languages
other than English, and they can send harmless content for unnecessary review.
We have not measured the resulting review workload.

For compatibility, the existing `fact_check_analysis_used` flag also marks this
policy path. The nested `context_guard_used=true` and
`evidence_provider_used=false` distinguish it from actual evidence execution.

## Testing scope

24 distinct, authored English messages: 16 context-review fixtures and 8
pass-through fixtures. Additional tests check long inputs, category priority,
and fixture uniqueness. These 27 checks run alongside the 30 Phase 9A checks.
They are development contracts, not independently labeled real-world data.
September 10, 2026 run: **57/57 passed (100% contract pass rate)** in 47.59
seconds, including dependency loading, with two dependency deprecation warnings.
This test duration is not request latency.
No new production-user count, latency benchmark, visual evaluation, or
real-world accuracy estimate is claimed. No frozen candidate was changed.

## Next phase: evidence-quality validation

Before changing source decisions, test this matrix:

| Evidence condition | Required behavior |
| --- | --- |
| Missing, inaccessible, or unrelated source | Uncertain and review |
| Old source used for a current changing claim | Uncertain and review |
| Two credible sources disagree | Uncertain and review |
| Multiple pages copy one original source | Do not count as independent confirmation |
| Source matches subject but not date, place, or quantity | Do not confirm the claim |
| LLM assertion without attributable evidence | Cannot establish truth |
| Current, relevant evidence supports or refutes one claim | Apply existing guarded route |

Use a separately labeled, source-backed dataset for independent measurement.
Report precision, recall, abstention and coverage, not just total accuracy.
Source-backed evaluation and full application regression testing remain pending.
