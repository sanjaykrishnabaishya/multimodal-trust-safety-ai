# TrustScope category-readiness ledger

Updated: 2026-08-21

This ledger separates independent component evidence from development contracts
and product readiness. A component score is never presented as overall product
accuracy. Automatic enforcement remains disabled unless a later production
authorization explicitly changes that contract.

## Application phase 1: cross-device foundation

Completed on 2026-08-21:

- One responsive interface now serves analysis and the human-review queue on
  desktop, laptop, and mobile browsers.
- The frontend resolves the API on the current private-network host instead of
  assuming localhost, while production can use an explicit HTTPS API origin.
- The backend accepts only configured origins and optional RFC1918 private-LAN
  origins; wildcard CORS is not used.
- Installable PWA metadata and a safe application-shell service worker are in
  place. Moderation API responses and user submissions are not cached.
- A Windows launcher starts both services, verifies readiness, and prints the
  desktop and same-Wi-Fi phone URLs; a paired stop command validates recorded
  process start times before ending them.
- Provider credentials remain server-side and are excluded from Git. External
  LLM decision support remains opt-in and cannot create an automatic Allow,
  Block, age, consent, identity, or provenance finding.

Phase validation: 122 backend tests passed, including the focused private-LAN,
Illegal Activities, OpenRouter-contract, privacy-fallback, and API-policy tests.
The frontend production build and static checks also passed.

| Category | Latest evidence | Evaluated examples | Readiness boundary |
| --- | --- | ---: | --- |
| Religiously Offensive Content | 100.00% synthetic independent accuracy | 240 | Passed guarded-integration gate; review-only output; follower hate remains owned by Hate Speech. |
| Hate Speech & Discrimination | 88.19% selective precision, 39.44% recall | 2,170 external | Passed selective independent gate; high-confidence output only; human review required. |
| Terrorism & Extremism | 100.00% synthetic independent accuracy | 300 | Passed guarded-integration gate; community candidates are not legal designations and can only create review. |
| Violent Content | 91.25% synthetic independent accuracy | 80 | Failed per-class readiness gate; graphic-depiction boundary fails closed to Uncertain and review. |
| Dangerous Content | 98.61% synthetic independent accuracy | 360 | Passed guarded-integration gate; review-only; no automatic enforcement. |
| Graphic, Obscene & Sexual Content | 97.08% synthetic independent accuracy | 240 | Text/policy candidate passed; captionless visual dependency remains independently unvalidated. |
| Sexual Harassment | 100.00% precision, 93.33% recall | 60 positive-support records within the 240-record challenge | Passed the shared synthetic category gate; ownership must take precedence over generic sexual content. |
| Cyberbullying & Harassment | 89.59% selective accuracy at 89.67% coverage | 300 external | Passed independent selective gate; uncertain results go to review. |
| Invasion of Privacy | No dedicated independent evaluation | 0 | Not ready; next new category planned. |
| Illegal Activities | 100.00% synthetic independent accuracy, precision, recall, specificity, and F1 | 600 unique | RC2 passed its locked independent gate and guarded live-fusion contract; review-only and no automatic enforcement. |
| Publishing Private Information | 91.45% recall on a positive-only external synthetic set | 2,000 | Useful detector evidence, but no negative-set specificity gate; consent/ownership still requires review. |
| Identity Theft & Impersonation | 58.33% synthetic independent accuracy, 20.83% recall | 192 | Failed readiness gate. |
| Misinformation | 41.67% exact accuracy; 75.00% selective accuracy at 11.11% coverage | 36 | Failed readiness gate; insufficient evidence must remain Uncertain. |
| Spam, Scam & Phishing | 99.22% external human-labelled accuracy | 774 | Strong message-level component evidence; broader multimodal/product validation remains separate. |
| Intellectual Property Violations | No dedicated independent evaluation | 0 | Not ready; legal provenance must be reviewed by a qualified human. |
| Malicious Programs | No dedicated independent evaluation | 0 | Not ready; defensive context and operational capability must be separated. |
| Abusive Words | 95.00% accepted precision, 76.00% selective recall | 100 label-support records within the 300-record challenge | Passed as a selective RC2 output; quotation and non-targeted contexts must not be overridden. |
| Child Exploitation | No dedicated prohibited-media benchmark | 0 | High-risk owner boundary only; suspected child sexual abuse material must never be stored. |
| Normal/Ignore | Tested as safe/boundary examples inside component suites | No standalone independent set | May be returned only when no stronger category owns the case and safe evidence is sufficient. |

## Shared decision rules

- Frozen candidates and independent holdouts are never modified after results
  are observed.
- Synthetic challenge scores are labelled synthetic, not external or real-world
  accuracy.
- Established category ownership cannot be replaced by an unrelated specialist.
- Safe-context evidence may prevent an override but cannot erase an already
  established high-risk category.
- Low confidence, missing evidence, unsupported media, uncertain age, or a
  provider failure routes to Uncertain and qualified human review.
- An LLM may summarize evidence or increase review priority. It cannot create an
  automatic Allow, Block, legal designation, identity, age, consent, or
  provenance finding.
- Automatic enforcement is disabled for the current research candidates.

## Current captionless-visual evidence boundary

- The V7 visual execution check achieved 100% agreement on eight user-confirmed
  development examples. That is too small to establish independent accuracy.
- The V8 policy contract achieved 100% on 170 synthetic signed-evidence records.
  It tests routing logic, not visual recognition.
- The V9 open-candidate collector currently contains 110 records: 92 downloaded
  Met candidates and 18 Library of Congress film references. Zero records are
  approved for training, calibration, or independent evaluation until human
  rights and boundary review is complete.
- Art/culture/education can become an Allow route only with trusted provenance,
  validated visual evidence, no explicit sexual activity, and no child-risk
  conflict. Film or television identity never creates Allow.

## Prior category phase: Illegal Activities RC1

The V1 policy and AI-advisory development contract covers controlled goods and
unapproved medicines, weapons/documents/counterfeit material,
gambling/financial facilitation, prohibited commercial services and protected
symbols, safe reporting/prevention, legitimate commerce/jobs, fictional and
research context, and jurisdiction/licensing uncertainty.

The 320-record development contract passed with 100% accuracy, precision,
recall, safe specificity, and minimum group accuracy, with zero action or
processing failures. The data is safe and synthetic; no external or restricted
source was used. These results are not independent or real-world accuracy.

The five-case live OpenRouter execution contract also passed: three permitted
texts produced schema-valid advisory results, while a private-identifier case
and a child-risk case were stopped locally before provider use. No raw provider
output was stored and the model retained no enforcement authority. This smoke
contract tests execution and safety boundaries, not accuracy.

RC1 was frozen before its independent challenge. The freeze locked the local
service, policy, development evaluator, dataset, OpenRouter adapter, and a gate
requiring more than 85% accuracy, precision, recall, specificity, and minimum
group accuracy. The external model identifier is recorded, but remote model
weights are not claimed as frozen and the external advisory has no category or
enforcement authority.

The new aggregate-only challenge contained 500 unique synthetic records with
zero development overlap. Binary accuracy was 96.00%, Illegal Activities
precision was 100.00%, recall was 90.00%, safe specificity was 100.00%, F1 was
94.74%, and minimum group accuracy was 90.00%. Exact category agreement derived
from the aggregate group totals was 95.00%.

RC1 nevertheless failed its independent readiness gate because 25 cases broke
the exact category and action contracts. The candidate remains frozen, cannot
be tuned using holdout cases or predictions, is ineligible for a new guarded
integration claim, and retains no automatic-enforcement authority.

RC2 development used only the aggregate failure signals: transaction-family
recall, safe fiction/research boundary generalization, and exact action/category
routing. Individual RC1 cases, predictions, and mismatches were not inspected
or reused.

## Latest completed category phase: Illegal Activities V2 RC2

RC2 adds a two-signal transaction policy: a covered subject must be paired with
a current sale, supply, delivery, payment, access, promotion, or marketplace
signal. Reporting, prevention, education, research, history, fiction, quotation,
museum, and legitimate professional context are explicit no-override boundaries.
Unknown licensing, jurisdiction, location, purpose, or transaction status routes
to `Uncertain` and qualified human review. Existing category owners and the child
safety boundary retain precedence.

The fresh development set contained 480 unique synthetic records across twelve
groups, with zero V1 development overlap. It achieved 100.00% accuracy,
precision, recall, safe specificity, F1, and minimum group accuracy, with zero
action, category-mix, or processing failures. RC2 was frozen only after those
gates passed.

The post-freeze independent challenge contained 600 new unique synthetic
records: 250 Illegal Activities positives and 350 negative, safe, Uncertain,
child-owner, and established-owner boundaries. Development overlap was zero.
Accuracy, Illegal Activities precision, recall, safe specificity, F1, and
minimum group accuracy were all 100.00%, with zero action, category-mix,
authority, or processing failures. OpenRouter was not used for accuracy.

The guarded live-fusion contract passed 8/8 cases. RC2 is connected to live
moderation as a review-only component. It can propose `Illegal Activities` or
`Uncertain`; it cannot create an automatic Allow, legal determination, or
automatic enforcement action. The candidate and holdout remain immutable.

Phase 3 regression validation: 151 backend tests passed. Three third-party
deprecation warnings remain non-blocking; no phase secret or private holdout
path was published.

These are synthetic policy and integration results, not external or real-world
accuracy. The next category phase is Child Exploitation.

## Priority category after Illegal Activities: Child Exploitation

This category will be developed as a high-risk safety router, not as a system
for collecting or learning from exploitative media. Development and evaluation
will use high-level synthetic text, non-sensitive metadata, and lawful safety
fixtures only. Suspected child sexual abuse material must never be uploaded to
an external LLM, added to RAG, retained as a test fixture, or printed in a
report.

Initial policy contract:

- Any credible child-exploitation signal fails closed to the Child
  Exploitation owner and specialist human escalation.
- Adult/child status is never inferred from appearance alone; ambiguous age is
  treated as child-risk and reviewed.
- Reporting, prevention, medical, educational, and law-enforcement context does
  not create automatic enforcement, but it also cannot bypass the safety
  router when media risk is unresolved.
- No external AI provider receives suspected child-risk text, images, video,
  identifiers, or hashes.
- No automatic Allow or automatic enforcement is authorized.

The development gate will require at least 90% accuracy, 95% precision, 90%
recall, 99% safe specificity, 85% minimum family accuracy, and zero safety,
privacy, storage, action, category-mix, or processing-contract failures. A new
hidden independent challenge must still exceed the user's 85% readiness floor
before guarded integration can be considered.

## Later new category: Invasion of Privacy

The first development candidate will distinguish non-consensual capture,
voyeurism, stalking/tracking, private-space intrusion, and non-consensual
intimate sharing from ordinary public scenes, consented personal media,
journalism, safety reporting, and fictional examples.

Initial policy contract:

- No face recognition, identity inference, age inference, or consent inference
  from appearance alone.
- Captionless visual evidence alone may raise review priority, but cannot prove
  ownership or consent.
- Credible voyeurism, private-space surveillance, stalking, or non-consensual
  intimate-media evidence routes to remove/restrict and human escalation.
- Ordinary public photography and consented or user-owned media remain allowed
  when no private-information or other safety owner is triggered.
- Unclear consent, jurisdiction, relationship, provenance, or location routes to
  Uncertain and human review.
- Publishing Private Information, Sexual Harassment, Child Exploitation, and
  other established owners retain precedence.

The development data will use safe synthetic text/metadata and lawful
CC0/public-domain contextual media. Real victim media and permission-restricted
sources will not be collected. The first gate will require at least 90% policy
precision, 90% safe specificity, 85% minimum family accuracy, and zero action,
category-mix, privacy-storage, or processing-contract failures.
