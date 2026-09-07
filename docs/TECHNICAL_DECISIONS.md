# TrustScopeAI technical decisions

Updated: 2026-09-07

This file explains why the project uses its current tools. The words are kept
simple so a new learner can understand the main idea.

## The big decision

We did not give one AI model complete control. One model can misunderstand a
joke, invent a fact, or miss an important detail. TrustScopeAI therefore uses a
team:

- extraction tools collect clues;
- local rules handle clear policy boundaries;
- specialist models recognize broader patterns;
- optional AI and RAG add advice;
- guardrails decide which category is allowed to act; and
- a human checks dangerous or uncertain cases.

This is called **guarded fusion**. It is like asking several helpers and then
making them follow one rulebook.

## Tool choices

| Tool or choice | Why we chose it | Important trade-off |
| --- | --- | --- |
| React | It makes a responsive screen from reusable pieces. The same page works on computers and phones. | Browser code cannot safely hold secrets. |
| Vite | It starts the React development app quickly and creates a small production build. | A real public deployment still needs secure hosting. |
| Progressive Web App files | They let an HTTPS deployment feel more like an installed phone app. | The service worker must never cache private submissions or decisions. |
| FastAPI | It makes a clear Python web API and automatic API documentation. | Production needs authentication, rate limits, monitoring, and HTTPS around it. |
| Pydantic | It checks that API input and output have the expected shape. | A valid shape does not prove that an AI answer is true. |
| Python | It has strong libraries for language, images, video, documents, testing, and machine learning. | Local AI models can use a lot of memory and CPU time. |
| SQLite | It is simple and works without installing a database server, which is good for a laptop prototype. | It is not the final choice for many simultaneous production writers. |
| Pillow and OpenCV | They read images and sample video frames. | Reading pixels is not the same as understanding the full scene. |
| Tesseract OCR and PyMuPDF | They recover visible words from images and scanned documents. | Blurry, stylized, rotated, or tiny writing can be missed. |
| faster-whisper | It turns local video speech into timestamped text without sending audio to a remote service. | Transcription can be slow and accents/noise can reduce accuracy. |
| Transformers and Sentence-Transformers | They help recognize meaning beyond exact keywords. | They can still make mistakes and require model downloads and memory. |
| scikit-learn and joblib | They provide small, inspectable classifiers and saved model bundles. | Synthetic accuracy does not guarantee real-world accuracy. |
| Local policy rules | They make important boundaries predictable and testable. | Rules need careful maintenance and cannot cover every sentence. |
| RAG | It gives an AI a small set of approved evidence instead of asking it to remember everything. | Retrieved evidence can still be incomplete or outdated. |
| Optional OpenRouter advice | It lets the server ask a stronger hosted model for bounded review evidence when enabled. | It adds cost, network delay, provider risk, and privacy checks; it has no enforcement authority. |
| Pytest | It quickly tells us when a new change breaks an old promise. | Passing tests prove only the cases that were tested. |
| npm security override | NanoID 3.3.18 is pinned because it is the patched 3.x release for [GHSA-2v37-7h3g-55p8](https://github.com/advisories/GHSA-2v37-7h3g-55p8). | The override must be reviewed when Vite or PostCSS changes its dependency tree. |
| Frozen candidates | The model, policy, hashes, and gates are locked before an independent challenge. | A failed frozen candidate cannot be repaired with that same hidden test. A new version is required. |
| Human review | People handle uncertainty, context, appeals, legal questions, and high-risk cases. | Review needs training, access control, staffing, and quality checks. |

## Why local first

Child-safety, privacy, security, and personal information can be very sensitive.
Local processing keeps more data on the user's machine and continues working
when an outside AI is unavailable. External advice is optional, server-side,
schema-limited, and blocked for protected evidence paths.

## Why AI is advisory instead of the boss

The external AI may:

- summarize approved evidence;
- support a local concern;
- increase review priority; or
- say that it is unsure.

It may not independently prove or create:

- a person's age, identity, or consent;
- ownership, a licence, or legal status;
- trusted media provenance;
- an automatic Allow or Block action; or
- a replacement for an established category owner.

If its response is late, malformed, missing, or unsupported, the system keeps
the local result and may send the case to a human.

## Safety and privacy decisions

- Real API keys live only in a local environment file or secret manager.
- Key values are never returned by health endpoints or saved in reports.
- The frontend receives no provider credential.
- Complete private identifiers, raw provider output, local review databases,
  uploaded media, private holdouts, and downloaded model files stay out of Git.
- Child Exploitation uses safe, high-level synthetic examples and no real
  exploitative media.
- Malicious Programs never executes code, opens archives, or stores payloads,
  credentials, or live infrastructure.
- Intellectual Property stores only synthetic descriptions and aggregate
  scores. It does not store copied works or claimant documents, decide licence
  validity or legal exceptions, use an external provider, or issue automatic
  takedowns.
- Automatic enforcement is disabled. High-risk and uncertain cases require a
  qualified human.

## Evaluation decisions

Development examples teach and tune a candidate. An independent challenge is a
new exam created after the candidate is frozen. The exam's raw answers are not
used to repair that candidate.

We report different measurements by their real names:

- **accuracy**: how many total answers were correct;
- **precision**: when the tool raised a category, how often it was right;
- **recall**: how many real category examples it found;
- **specificity**: how many safe or other-category examples it left alone;
- **coverage**: how often a selective model felt confident enough to answer;
- **request success**: whether the API returned a valid result, not whether the
  moderation decision was correct; and
- **response time**: how long the measured request took on one stated machine.

Synthetic, external, positive-only, shared-category, policy-contract, and live-
integration results are never presented as if they were the same kind of test.

## Decisions we intentionally did not make

- We did not claim that all 19 categories are production-ready.
- We did not turn synthetic 100% scores into a claim of real-world perfection.
- We did not call community-maintained group names official legal designations.
- We did not let film or television identity automatically make sexual content
  safe.
- We did not infer age, identity, consent, ownership, licence, or location from
  appearance alone.
- We did not use a frontend API key.
- We did not promise a number of production users from a 10-user laptop test.

## When these decisions should change

Move from SQLite to a managed production database when real authenticated
review teams need concurrent access. Add a task queue when long image and video
jobs should run in the background. Add production authorization only after
external evaluation, security review, monitoring, appeal design, and written
policy approval.

Every large change should receive a new decision entry, tests, measured results,
and a clear statement of what is still unknown.
