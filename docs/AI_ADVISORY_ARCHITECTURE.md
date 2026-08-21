# TrustScopeAI server-side AI advisory architecture

Updated: 2026-08-21

The OpenRouter integration is a bounded evidence source. It is not an
enforcement engine and cannot replace the deterministic policy layer,
independently evaluated specialists, category-owner precedence, or a qualified
human reviewer.

## Request boundary

1. The key is loaded only from the backend process environment or
   `backend/.env`. It is never returned by an endpoint or included in a report.
2. Only direct text that already contains a local Illegal Activities policy
   family can be routed in V1. Visual descriptions, raw images, audio, and video
   are not sent by this component.
3. Text containing detected private identifiers or combined child/exploitation
   indicators is rejected before any provider request.
4. Requests require a pinned model, strict JSON Schema, zero-data-retention
   routing, provider data-collection denial, required-parameter support, and no
   provider fallback.
5. Invalid JSON, extra fields, provider errors, timeouts, and authority-contract
   violations fail closed without storing the raw provider response. One bounded
   retry is permitted only after schema rejection; provider and authority errors
   are not retried.

V1 pins `openai/gpt-oss-20b`. The pin was selected from OpenRouter's current
ZDR and structured-output-compatible catalog and passed the bounded live schema
contract. Changing the model requires rerunning that contract.

## Decision authority

- A local transaction/facilitation signal can propose `Illegal Activities` and
  human review.
- Subject matter without enough facilitation, licensing, or jurisdiction
  evidence can propose `Uncertain` and human review.
- The LLM may support evidence, increase review confidence, or abstain.
- The LLM cannot create an automatic Allow, Block, legal determination,
  identity, age, consent, or provenance finding.
- Existing owners including Child Exploitation, Terrorism, Malicious Programs,
  Spam/Scam, Private Information, and other categories cannot be overwritten.
- Automatic enforcement remains disabled.

## Evaluation boundary

The V1 development contract uses 320 unique, safe synthetic records across
eight policy families. It is development evidence only. It does not establish
external or real-world accuracy. A frozen candidate and a new independent
holdout are required before Illegal Activities can be called independently
ready.

The planned independent gate requires at least 90% accuracy, 90% precision,
85% recall, 95% safe specificity, 85% minimum family accuracy, and zero action,
category-owner, privacy, or processing contract failures.
