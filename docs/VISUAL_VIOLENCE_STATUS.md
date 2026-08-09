# Visual and Video Violence Capability Status

Last updated: 2026-08-10

## Current product behaviour

TrustScopeAI does not automatically confirm an image or video as safe when no
violation is detected. A visually safe-looking result is changed to the
`Uncertain` decision state and sent for human review.

Clear violations detected through OCR, document text, an audio transcript, or
another validated signal keep their detected policy category. Text moderation
is not changed by this safety gate.

## Violent Content V2 RC1

- Status: frozen candidate
- Development result: 100% on 200 development records
- Independent validation: not yet completed
- Production enforcement: not permitted

Development results are not independent accuracy and must not be presented as
production accuracy.

## Rejected visual candidates

### Frame image classifier

- Candidate: `jaranohaal/vit-base-violence-detection`
- Diagnostic records: 20 clips / 60 frames
- Best accuracy: 60%
- Violence recall: 40%
- Specificity: 80%
- Decision: rejected; never integrated

The repository also contained architecture metadata that did not match the
checkpoint. The corrected native checkpoint loader was used for the reported
diagnostic.

### Temporal ONNX classifier

- Candidate: `mostafaalazzaly/aleris-violence-detector-x3d-resnet18`
- Decision: rejected before prediction
- Reason: the published preprocessing contract specifies frame count, image
  size, channels, and tensor layout but omits pixel scaling and normalization
  values. TrustScopeAI refuses to guess these values.

## Required future work

1. Build or select a model with a complete licence, model card, preprocessing
   contract, label mapping, and immutable checkpoint.
2. Use real videos with enough consecutive frames for temporal evaluation.
3. Keep development, validation, and independent holdout records separate.
4. Require at least 85% accuracy, precision, recall, specificity, and F1 on the
   independent scope-specific holdout.
5. Run category-isolation and action-contract tests.
6. Integrate only after the candidate is frozen and passes the independent
   readiness gate.

Until then, visual violence remains a human-review capability rather than an
automatic enforcement capability.
