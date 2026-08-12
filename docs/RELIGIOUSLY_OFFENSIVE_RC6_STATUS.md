# Religiously Offensive Content V7 RC6

## Status

RC6 passed its frozen synthetic independent readiness gate and its guarded live-fusion contract. It is connected to TrustScopeAI as a review-only specialist.

This does **not** mean that the application has 100% real-world accuracy. The independent result is based on a fixed synthetic English-language challenge. External, multilingual, image, and video validation remain future work.

## Category ownership

RC6 may classify direct attacks against:

- sacred or religious objects and texts;
- places of worship; and
- deities, prophets, founders, or other revered religious figures.

RC6 does not own attacks against people because of their religion. Those remain with **Hate Speech & Discrimination V7**.

Reporting, education, preservation, condemnation, neutral religious discussion, and unrelated category decisions do not receive a religious-category override.

## Decision contract

RC6 needs all of the following:

1. A direct sacred-target attack.
2. Either a validated semantic signal or an explicit advocacy signal.
3. No reporting, condemnation, negation, educational, or follower-Hate veto.

An accepted result is always:

- Category: `Religiously Offensive Content`
- Severity: `High`
- Action: `Remove and send for human review`
- Human review: required
- Automatic enforcement: disabled

RC6 cannot replace established Spam, Violence, Cyberbullying, Hate Speech, privacy, child-exploitation, or other category owners.

## Evidence

### Development

- Records: 360
- Development overlap: 0
- Accuracy: 100.00%
- Precision: 100.00%
- Recall: 100.00%
- Specificity: 100.00%
- Category-mix failures: 0
- Direct-advocacy recoveries beyond the semantic path: 9

Development scores are tuning evidence, not independent accuracy.

### Frozen synthetic independent challenge

- Records: 240
- Positive records: 90
- Negative records: 150
- Development overlap: 0
- Binary accuracy: 100.00%
- Precision: 100.00%
- Recall: 100.00%
- Specificity: 100.00%
- Reported-advocacy safe routing: 100.00%
- Protected-follower safe routing: 100.00%
- Category-mix failures: 0
- Action-contract failures: 0
- Processing errors: 0

No raw challenge text or individual predictions were stored or printed. The holdout may not be used to modify RC6.

### Product regression and live integration

- Full backend regression: 56 tests passed
- Guarded fusion unit contract: 13/13 passed
- Corrected live fusion contract V2: 12/12 passed
- Independent holdouts used by live contract: no
- Frozen candidate modified by integration: no

## Candidate history

- RC1–RC4 failed their locked independent gates and remain disconnected.
- RC5 passed development but failed a pre-holdout policy contract. It was retired without spending an independent holdout.
- RC6 added a tightly scoped direct-advocacy path and stronger reporting/follower boundaries before it was frozen and independently evaluated.

## Remaining limitations

- Synthetic independent evidence is not a substitute for external real-world evaluation.
- English text is the validated input for this component.
- OCR, transcripts, and extracted document text can reach the text pipeline, but modality-specific religious-content accuracy has not been independently established.
- Visual-only religious attacks are not automatically classified by this text specialist.
- All accepted RC6 decisions require human review.
