# Phase 9A: safer fact-check handoff

The evidence engine is like a researcher. The moderation router is like an
editor. This change makes the editor check the researcher's response before
using it. It does not teach the researcher new facts.

## Changes and rules

- Another moderation category keeps priority; this route cannot replace it.
- A supported claim keeps the existing Normal/Ignore recommendation only when
  the internal response passes the handoff checks.
- A refuted claim goes to Misinformation & Fake News and human review.
- Missing evidence, conflicting evidence, invalid scores, broken responses,
  and evidence-service failures go to Uncertain and human review.
- A usable handoff must include a named source with an HTTP(S) address and
  an explicit successful claim-alignment flag. This is a structural check,
  not proof that a website is trustworthy or its statement is true.
- Scores must be finite numbers between zero and one; the existing 0.80 cap
  remains. Scores are not measured accuracy.
- No automatic enforcement is enabled. Provider error details are not returned
  to the user, because they might contain private information.

## Technical decision

Keep the existing Python evidence engine and add checks at its handoff to the
moderation router. No new framework, paid API, model, media copying, training,
or frozen-candidate changes are needed. The existing date, source-quality and
claim-matching logic still needs independent validation.

## Evaluation scope

The new offline test suite contains 30 handoff contract cases. These are
different failure/response conditions with mocked evidence, not 30 independent
news claims. There are zero new real-world claims, zero production users, and
no response-time benchmark in this phase. Do not present its pass percentage
as misinformation accuracy. The earlier 36-record result remains the last
reported claim evaluation; this change does not replace that evidence.

Run on September 10, 2026: **30/30 passed (100% contract pass rate)** in
98.84 seconds including dependency startup. There were two dependency
deprecation warnings and one cache-write warning. This duration is not an API
response-time measurement. The full backend suite and live providers were not
run in this phase.

## Next: Phase 9B

Audit claim routing, especially opinion phrases attached to factual claims,
questions containing assertions, quotations that endorse a claim, corrections,
satire, and multiple claims in one message. Define a source/date/conflict test
matrix before making changes. Then use separately labeled, source-backed
claims to measure false accusations, missed misinformation, abstention and
coverage. Keep development fixtures separate from an independent holdout.

This phase does not establish image/video authenticity, real-world accuracy,
or readiness for automatic enforcement.
