# TrustScopeAI architecture

Updated: 2026-09-07

## The whole system

```mermaid
flowchart TD
    A[Phone, laptop, or desktop browser] --> B[React and Vite web app]
    B -->|text or file over HTTP| C[FastAPI]
    C --> D{Input type}
    D -->|Plain text| E[Text normalizer]
    D -->|TXT, PDF, or DOCX| F[Document reader and OCR fallback]
    D -->|JPG, PNG, or WEBP| G[Image checks, metadata, and OCR]
    D -->|MP4, MOV, AVI, MKV, or WEBM| H[Video metadata, sampled frames, OCR, and speech]
    E --> I[Combined evidence]
    F --> I
    G --> I
    H --> I
    I --> J[Shared policy rules]
    I --> K[Local specialist models]
    I -. approved text only .-> L[Optional RAG and external AI advice]
    J --> M[Guarded decision fusion]
    K --> M
    L --> M
    M --> N[Category, severity, action, reason, and confidence]
    N --> O{Human review needed?}
    O -->|Yes| P[SQLite review queue and audit history]
    O -->|No| Q[Result shown to the user]
```

## What each layer does

1. **The web app** lets a person paste text or choose a file. It works on a
   computer or a phone browser.
2. **The API** checks the request and sends it to the correct reader.
3. **The readers** turn documents, visible words, video frames, and speech into
   evidence the moderation system can use.
4. **The policy and model layer** looks for risk while protecting safe contexts
   such as reporting, education, prevention, and approved work.
5. **Guarded fusion** keeps category ownership stable and prevents an optional
   AI from becoming an enforcement engine.
6. **The result layer** explains the category and next action. Risky or unclear
   cases are saved for a human reviewer.

## Trust boundaries

```mermaid
flowchart LR
    A[Public browser] -->|No provider key| B[TrustScope server]
    B --> C[Local rules and models]
    B --> D[Local review database]
    B -. only when enabled and allowed .-> E[External AI provider]
    F[Local .env or secret manager] -->|key stays here| B
    E -->|advice only| B
```

- A provider key stays on the server and never enters the browser bundle.
- Child-safety, private, or security-sensitive evidence is stopped before the
  optional external-advice path when its policy forbids transmission.
- Moderation responses, uploads, review databases, private holdouts, and raw AI
  output are excluded from Git.
- The external AI cannot create automatic Allow, Block, identity, age, consent,
  licence, legal-status, or provenance findings.
- Automatic enforcement is disabled.

## Current scaling boundary

The current SQLite queue and in-process local models are appropriate for a
laptop research prototype. A small benchmark completed 95/95 text requests and
tested up to 10 simulated users, but response times became much slower under
concurrency. Production should add authenticated users, a managed database,
background task queues, model workers, rate limits, monitoring, and HTTPS.

See [the performance snapshot](PERFORMANCE_SNAPSHOT.json) for the measured
numbers and [Technical Decisions](TECHNICAL_DECISIONS.md) for the reasons behind
the design.
