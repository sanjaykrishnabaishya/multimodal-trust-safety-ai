# Hate Speech V7 RC1 Status

Updated: 12 August 2026

## Component status

Hate Speech V7 RC1 passed its predeclared independent readiness gate and is connected to TrustScopeAI through guarded fusion.

It is a conservative English text specialist. It may propose only **Hate Speech & Discrimination**. Every applied decision is sent to human review. It cannot automatically remove, block, allow, or otherwise enforce a decision.

This component result is not the accuracy of the complete TrustScopeAI product.

## Policy boundary

The component is intended for demeaning, dehumanizing, discriminatory, exclusionary, or harmful content targeting a person or group based on religion, caste, nationality, ethnicity, or another protected characteristic.

The guarded fusion rules are:

- Reporting, education, counterspeech, and condemnation cannot receive a Hate Speech override.
- Cyberbullying & Harassment cannot be replaced by this component.
- Violence, Spam/Scam/Phishing, Publishing Private Information, Misinformation, Religiously Offensive Content, and other unrelated categories cannot be replaced.
- Abusive Words can be refined to Hate Speech only when an explicit protected-group reference is also detected.
- Safe and below-threshold model outputs never create an Allow decision.
- Applied Hate Speech decisions always use `Refer to human review`.

## Model and data

- Base model: `microsoft/MiniLM-L12-H384-uncased`
- Pinned revision: `86186eff27cda7c5bc520e45de4800c575d9d8b3`
- Base-model licence: MIT
- Training task: three-class English text classification
- Development classes: Hate Speech, Abusive Words, and Safe/Other
- Permitted live output: Hate Speech only
- Training records: 7,500
- Validation records: 2,382
- Training classes: 2,500 records per class
- Development sources: permitted Civil Comments and HateXplain training splits

The reserved Civil Comments and HateXplain test splits were excluded from training, calibration, and RAG. They were opened once only after RC1 was frozen.

## Development result

The raw three-class result was diagnostic only:

- Raw accuracy: 70.40%
- Raw macro F1: 70.56%

The predeclared selective Hate Speech output passed every development gate:

- Probability threshold: 0.84
- Accepted validation records: 284
- Selective precision: 91.20%
- Recall: 39.66%
- Specificity: 98.55%
- Civil Comments precision: 92.86%
- Civil Comments recall: 86.67%
- HateXplain precision: 90.79%
- HateXplain recall: 34.91%

## Independent result

The frozen RC1 was evaluated once on 2,170 reserved records with zero development/test overlap:

- Overall binary accuracy: 80.46%
- Accepted records: 288
- Selective precision: 88.19%
- Recall: 39.44%
- Specificity: 97.77%
- F1: 54.51%

Source results:

- Civil Comments: 93.02% selective precision, 80.00% recall, 98.50% specificity
- HateXplain: 87.35% selective precision, 36.03% recall, 97.66% specificity

Boundary errors among accepted test decisions:

- Abusive Words false positives: 18
- Safe/Other false positives: 16

The component passed the independent gate frozen before the test was opened. These results must not be described as 88.19% overall accuracy. They mean that 88.19% of the selectively accepted Hate Speech decisions matched the test labels.

## Integration verification

- Guarded fusion unit tests: 7/7 passed
- Complete backend regression suite: 43/43 passed
- Live synthetic fusion contract V2: 7/7 passed
- Automatic enforcement: disabled
- Required action: Refer to human review

The live fusion contract is an integration check, not an accuracy benchmark.

## Known limitations

- The specialist misses many Hate Speech cases; independent recall is 39.44%.
- It is validated for English text, not multilingual content.
- Text extracted from documents, OCR, or speech transcription may be analyzed, but extraction errors can affect the decision.
- The result must be reviewed by a person before enforcement.
- Model weights and public datasets are excluded from public Git because of file size, redistribution, privacy, and evaluation-integrity requirements.
- Reserved test data must never enter training, calibration, RAG, prompt examples, or candidate revisions.
- The RC1 holdout results may not be used to modify RC1. Any improvement must become a newly versioned candidate with a new untouched evaluation set.

## Reproducibility

The repository contains scripts for data import, development training, calibration, candidate freezing, independent aggregate evaluation, guarded integration, regression tests, and the live fusion contract.

Local model artifacts, datasets, and detailed reports remain excluded from Git. A production deployment will require a separately controlled model-artifact store with integrity hashes and licence records.
