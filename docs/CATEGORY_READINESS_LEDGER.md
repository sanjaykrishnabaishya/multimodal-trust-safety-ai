# TrustScope category-readiness ledger

Updated: 2026-08-30

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
| Invasion of Privacy | 100.00% synthetic independent accuracy, precision, recall, specificity, and F1 | 720 unique | RC1 passed its locked independent and guarded live-fusion gates; review-only, local-only, and no victim-media storage or automatic enforcement. |
| Illegal Activities | 100.00% synthetic independent accuracy, precision, recall, specificity, and F1 | 600 unique | RC2 passed its locked independent gate and guarded live-fusion contract; review-only and no automatic enforcement. |
| Publishing Private Information | 91.45% recall on a positive-only external synthetic set | 2,000 | Useful detector evidence, but no negative-set specificity gate; consent/ownership still requires review. |
| Identity Theft & Impersonation | 58.33% synthetic independent accuracy, 20.83% recall | 192 | Failed readiness gate. |
| Misinformation | 41.67% exact accuracy; 75.00% selective accuracy at 11.11% coverage | 36 | Failed readiness gate; insufficient evidence must remain Uncertain. |
| Spam, Scam & Phishing | 99.22% external human-labelled accuracy | 774 | Strong message-level component evidence; broader multimodal/product validation remains separate. |
| Intellectual Property Violations | No dedicated independent evaluation | 0 | Not ready; legal provenance must be reviewed by a qualified human. |
| Malicious Programs | No dedicated independent evaluation | 0 | Not ready; defensive context and operational capability must be separated. |
| Abusive Words | 95.00% accepted precision, 76.00% selective recall | 100 label-support records within the 300-record challenge | Passed as a selective RC2 output; quotation and non-targeted contexts must not be overridden. |
| Child Exploitation | 100.00% synthetic independent accuracy, precision, recall, specificity, and F1 | 720 unique | Passed guarded-integration gate; local-only critical review routing; no real exploitative media, external provider, automatic enforcement, or appearance-based age inference. |
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
accuracy. The next completed category phase is Child Exploitation.

## Latest completed category phase: Child Exploitation V1 RC1

This category was developed as a high-risk safety router, not as a system for
collecting or learning from exploitative media. Development and evaluation used
only high-level synthetic text and safe metadata. No real exploitative media,
graphic descriptions, or external AI provider was used.

Implemented policy contract:

- A child/minor signal plus high-level exploitation, grooming, coercion,
  unsafe-contact, trafficking, intimate-image, or physical-abuse evidence routes
  to `Child Exploitation`, `Critical`, `Block and immediately escalate`.
- Age is never inferred from appearance alone. Ambiguous age with sexual or
  intimate risk routes to `Uncertain` and human review.
- Clear reporting, prevention, medical, educational, research, and support
  context is a no-override boundary when there is no live-case or facilitation
  signal. Incomplete media evidence still fails closed to review.
- Verified adult-only sexual content remains owned by Graphic, Obscene & Sexual
  Content. Unrelated established category owners remain unchanged.
- No external AI provider receives child-risk text, images, video, identifiers,
  hashes, or derived evidence.
- The specialist can propose only Child Exploitation or Uncertain. It cannot
  create automatic Allow or automatic enforcement.

The development set contained 600 unique synthetic fixtures across twelve
families. Accuracy, child precision, child recall, safe specificity, F1, and
minimum family accuracy were all 100.00%, with zero action, category, privacy,
external-transmission, age-inference, or processing failures. RC1 was frozen
only after this gate passed.

The post-freeze independent challenge contained 720 new unique synthetic
fixtures: 240 Child Exploitation positives and 480 safe, Uncertain, adult-only,
lexical, and category-owner boundaries. Development overlap was zero. Accuracy,
precision, recall, specificity, F1, and minimum group accuracy were all 100.00%,
with zero contract failures. The guarded live-fusion contract passed 10/10.

Phase 4 regression validation: 165 backend tests passed. Three third-party
deprecation warnings remain non-blocking; no API key, real exploitative media,
private holdout path, raw challenge text, or individual prediction was
published.

These are synthetic policy and integration results, not external or real-world
accuracy. The frozen candidate and challenge may not be used for tuning.

## Latest completed category phase: Invasion of Privacy V1 RC1

This category was built as a local evidence-and-review router. It does not
identify people, infer consent or private location from appearance, collect
victim media, or ask an external provider to make privacy findings.

Implemented policy contract:

- Credible non-consensual capture, hidden-camera or eavesdropping behavior,
  stalking/location tracking, private-space intrusion, or non-consensual
  intimate-media sharing routes to `Invasion of Privacy`, `High`, `Restrict and
  send for human review`.
- A privacy-sensitive context must be paired with capture, surveillance,
  tracking, sharing, or an active-case signal. Isolated words such as “private”
  or “tracking” do not create a violation.
- Unclear consent, location, relationship, provenance, or incomplete evidence
  routes to `Uncertain` and human review; it never creates automatic Allow.
- Documented consent, user-owned recording, disclosed public monitoring, safe
  reporting, education, prevention, and fiction are no-override boundaries when
  there is no active non-consensual case.
- Child Exploitation, Publishing Private Information, Sexual Harassment, and all
  other established category owners retain precedence.
- The specialist can propose only Invasion of Privacy or Uncertain. Automatic
  enforcement and external-provider use are disabled.

The development set contained 600 unique synthetic fixtures across twelve
families. Accuracy, privacy precision, recall, safe specificity, F1, and minimum
family accuracy were all 100.00%, with zero action, category-mix,
privacy-storage, authority, or processing failures. RC1 was frozen only after
this gate passed.

The post-freeze independent challenge contained 720 new unique synthetic
fixtures: 240 privacy positives and 480 safe, Uncertain, consented, public,
reporting, lexical, and category-owner boundaries. Development overlap was
zero. Accuracy, precision, recall, specificity, F1, and minimum group accuracy
were all 100.00%, with zero contract failures. The guarded live-fusion contract
passed 10/10.

Phase 5 regression validation: 179 backend tests passed. Three third-party
deprecation warnings remain non-blocking; no API key, real victim media,
private identifier, raw challenge text, individual prediction, or external
provider payload was published.

These are synthetic policy and integration results, not external or real-world
accuracy. The frozen candidate and challenge may not be used for tuning.

## Next category: Malicious Programs

The first candidate will separate operational malware distribution or
facilitation from defensive cybersecurity work. It will use safe synthetic
text and metadata only; executable malware, credentials, live command-and-
control addresses, and functional payloads will not be collected or stored.

Initial policy contract:

- Distribution, installation, deployment, credential theft, persistence,
  evasion, ransomware, destructive action, or command-and-control intent must
  be paired with a malware/tool/payload signal before the category can apply.
- Defensive analysis, incident response, sandbox reports, detection rules,
  patched demonstrations, academic discussion, and benign administration are
  protected contexts when no live facilitation signal exists.
- Dual-use or incomplete intent, unsupported attachments, encrypted archives,
  and uncertain payload capability route to `Uncertain` and security review.
- Code is never executed during moderation. The specialist stores no executable
  payload and cannot generate or improve malicious capability.
- Illegal Activities, Spam/Phishing, Identity Theft, Child Exploitation, and
  other established owners retain precedence according to the primary harm.
- Automatic enforcement remains disabled; confirmed candidates route to block
  plus specialist security review.

The first gate will require at least 90% precision and safe specificity, at
least 85% recall and minimum family accuracy, and zero execution, payload-
storage, action, category-mix, authority, or processing-contract failures.
