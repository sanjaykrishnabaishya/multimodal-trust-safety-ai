# Identity-theft and impersonation source boundary

This feature is a safety router. It does not identify people or automatically suspend accounts.

It follows three ideas from official sources:

- The U.S. Federal Trade Commission describes identity theft as someone using another person's personal or financial information without permission.
- The FTC's government and business impersonation rule addresses materially false posing as, or false claims of affiliation with, a government entity, business, or their officers.
- NIST treats reliable digital identity as an identity-proofing and authentication process with security, privacy, fraud, and assurance controls. A picture or model guess is not identity proofing.

The tool therefore needs evidence of both identity/deceptive-representation conduct and a current act or impact. It cannot confirm identity from a face, voice, name, logo, resemblance, self-claim, or AI output. Unknown identity, consent, authorization, authenticity, provenance, or deceptive intent goes to `Uncertain` review.

Official references:

- [FTC: What To Know About Identity Theft](https://consumer.ftc.gov/articles/what-know-about-identity-theft)
- [FTC: Impersonation of Government and Businesses Rule](https://www.ftc.gov/legal-library/browse/rules/impersonation-government-businesses-rule)
- [NIST SP 800-63 Revision 4 Digital Identity Guidelines](https://pages.nist.gov/800-63-4/)

The live RC5 route uses two evidence checks:

- deceptive impersonation plus a concrete current contact, payment, access, or
  victim-impact act; or
- identity or credential material plus lack of permission plus a concrete
  account, transaction, access, communication, loan, benefit, or care impact.

Plausible cases with missing identity, authority, consent, intent, provenance,
or source evidence become `Uncertain` and require human review. Confirmed
identity cases also require human review. Automatic account suspension and
automatic enforcement are disabled.

The frozen candidates contain only synthetic descriptions. They contain no real
identity documents, account credentials, complete personal identifiers, face or
voice embeddings, private complaints, or individual challenge predictions.
RC1-RC4 failed later readiness or live checks and remain immutable and
ineligible; RC5 is the only guarded live identity route.
