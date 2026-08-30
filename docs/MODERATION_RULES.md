# TrustScopeAI moderation rules

Updated: 2026-08-30

This is the concise product rulebook for the 19-category registry. Category
presence does not imply that its specialist passed independent readiness; see
`CATEGORY_READINESS_LEDGER.md`. Unless a category-specific contract says
otherwise, uncertain evidence goes to human review and automatic enforcement is
disabled.

| Category | Moderate when | Default action | Important allow/review boundary |
| --- | --- | --- | --- |
| Religiously Offensive Content | Sacred figures, texts, symbols, objects, or places are attacked, desecrated, or denigrated. | Remove and human review. | Neutral education, history, reporting, and good-faith criticism remain safe; disputed satire or art is reviewed. |
| Hate Speech & Discrimination | A protected person or group is dehumanized, threatened, excluded, or demeaned because of a protected characteristic. | Remove and escalate. | Counterspeech, reporting, education, quotation, and reclaimed or ambiguous language require context review. |
| Terrorism & Extremism | Content praises, recruits for, funds, propagandizes, or operationally supports a banned extremist entity. | Block and escalate. | Reporting, history, research, and condemnation remain safe; unknown legal status can only create review. |
| Violent Content | Graphic injury, torture, mutilation, blood, organs, or severe bodily harm is depicted. | Block or sensitive-content warning plus review. | Sufficient blur and non-graphic reporting may be allowed; uncertain severity is reviewed. |
| Dangerous Content | Content encourages hazardous stunts, experiments, endangerment, serious injury, death, or property destruction. | Remove and human review. | Controlled professional, educational, and prevention contexts are protected. |
| Graphic, Obscene & Sexual Content | Explicit adult nudity, sexual activity, sexual objects, commercial explicit material, or sexual violence is present. | Block, age-restrict, or limit distribution. | Verified art, monuments, health, and education have narrow safe routes; film/TV identity never creates Allow; uncertain age fails closed. |
| Sexual Harassment | Unwanted sexual messages, remarks, pornography, conduct, or demands for sexual favors target a person. | Remove and escalate. | Unclear consent or relationship requires review. |
| Cyberbullying & Harassment | Repeated targeting, direct threats, humiliation, or abusive conduct targets a person. | Limit or remove and human review. | Reporting, third-person depiction, quotation, and non-targeted language must not be misclassified. |
| Invasion of Privacy | A privacy-sensitive context is paired with credible non-consensual capture, surveillance/eavesdropping, stalking/tracking, private-space intrusion, or intimate-media sharing. | Restrict and send for human review. | Isolated keywords are insufficient; consent, ownership, private location, relationship, and identity cannot be inferred from appearance; documented consent and safe reporting do not override; uncertainty is reviewed. |
| Illegal Activities | A covered illegal/prohibited subject is paired with a current sale, supply, payment, delivery, access, or facilitation signal. | Restrict and human review. | Reporting, research, fiction, history, quotation, and legitimate commerce are vetoes; unresolved jurisdiction/licensing is Uncertain. |
| Publishing Private Information | Sensitive personal, contact, financial, government, location, or credential data is exposed without established authorization. | Remove exposed information and human review. | Public business details, fictional/redacted examples, ownership, and consent require verification. |
| Identity Theft & Impersonation | Another person or organization is fraudulently impersonated or their credentials/likeness are used deceptively. | Flag and human review. | Parody and identity ownership require verification. |
| Misinformation & Fake News | A materially false or manipulated factual claim is presented as true. | Flag and human review. | Satire, opinion, fiction, correction, and unresolved truth must not be automatically blocked. |
| Spam, Scam & Phishing | Unsolicited or deceptive content requests money, credentials, OTPs, passwords, clicks, or promotes suspicious schemes. | Block, warn, or limit distribution. | Expected transactions and legitimate commercial/service messages remain safe; dictionary terms alone are insufficient. |
| Intellectual Property Infringement | Protected works or marks appear distributed or reproduced without authorization. | Flag and qualified human review. | Licence, public-domain status, authorization, quotation, and fair dealing require evidence and legal review. |
| Malicious Programs | Content distributes or facilitates malware, ransomware, credential theft, or operational compromise. | Block and security review. | Defensive education without harmful payloads or facilitation remains safe. |
| Abusive Words | Targeted swear words, insults, or obfuscated abusive terms attack a person. | Remove/limit distribution and, when needed, review. | Non-targeted quotation, education, reporting, and self-reference remain safe. |
| Child Exploitation | A child/minor signal co-occurs with sexual exploitation, grooming, coercion, unsafe contact, trafficking, intimate-image, or physical-abuse evidence. | Block and immediately escalate to specialist human review. | No real suspected material is stored or sent externally; age is never inferred from appearance; uncertain age/risk is Uncertain; clear prevention/education is protected. |
| Normal/Ignore | No other category has sufficient ownership and the content is ordinary or safely contextualized. | Allow. | Weak evidence alone cannot justify restriction, but unresolved high-risk evidence must become Uncertain rather than Allow. |

## Shared authority rules

- Established category owners are preserved unless the explicit high-risk Child
  Exploitation priority boundary applies.
- Safe context prevents an unsupported override; it does not erase an already
  established high-risk decision.
- Models and LLMs may supply bounded evidence or increase review priority. They
  cannot independently prove age, consent, identity, licence, legal status, or
  provenance, and cannot create automatic Allow or enforcement.
- Unsupported media, insufficient evidence, provider failure, and unresolved
  high-risk ambiguity fail closed to `Uncertain` and human review.
- Secrets, raw provider output, complete private identifiers, real exploitative
  child material, and private holdouts must never be committed or added to RAG.
