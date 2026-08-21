# Multimodal Trust & Safety Application

A multimodal Trust and Safety system for processing and moderating:

- Plain text
- TXT, PDF, and DOCX documents
- JPG, PNG, and WEBP images
- MP4, MOV, AVI, MKV, and WEBM videos

## Current capabilities

The application currently supports:

- FastAPI backend
- Text submission
- Document upload and text extraction
- Image validation and metadata extraction
- Video metadata extraction and frame sampling
- OCR for standalone images
- OCR for scanned PDF pages
- OCR for sampled video frames
- Synthetic multimodal moderation datasets
- Shared Trust and Safety policy labels
- Local video speech transcription
- Automatic spoken-language detection
- Timestamped video transcript segments
- Responsive desktop, laptop, and mobile browser interface
- Installable Progressive Web App metadata for HTTPS deployments
- Private-LAN development access without wildcard CORS
- Human-review queue with audit history
- Server-side OpenRouter advisory evidence with strict schema and privacy gates

## Planned capabilities

The following components are planned:

- Video speech transcription
- Visual scene understanding
- Basic policy moderation
- RAG policy retrieval
- Confidence thresholds
- Human-review routing
- Testing and evaluation

## Run on a laptop and phone

For the simplest Windows launch, run this once from the project root:

```powershell
.\start_trustscope.ps1
```

The launcher starts both services, verifies that they are ready, prints the
desktop and same-Wi-Fi phone addresses, and keeps runtime logs outside Git.
Stop both services with `.\stop_trustscope.ps1`.

Start the API on `0.0.0.0:8010` and the Vite frontend on
`0.0.0.0:5173`, then open the laptop's private IPv4 address from a phone on
the same trusted network. See [docs/CROSS_DEVICE_SETUP.md](docs/CROSS_DEVICE_SETUP.md)
for the exact commands and production security boundary.

Provider credentials must remain server-side. Never place a secret in a
frontend environment variable, browser storage, source file, report, or
moderation record.

## Supported moderation categories

The shared policy registry contains 19 categories: Religiously Offensive
Content; Hate Speech & Discrimination; Terrorism & Extremism; Violent Content;
Dangerous Content; Graphic, Obscene & Sexual Content; Sexual Harassment;
Cyberbullying & Harassment; Invasion of Privacy; Illegal Activities; Publishing
Private Information; Identity Theft & Impersonation; Misinformation & Fake
News; Spam, Scam & Phishing; Intellectual Property Infringement; Malicious
Programs; Abusive Words; Child Exploitation; and Normal/Ignore.

The presence of a category in the registry does not mean its specialist has
passed independent readiness. See
[docs/CATEGORY_READINESS_LEDGER.md](docs/CATEGORY_READINESS_LEDGER.md).

OpenRouter is used only as a server-side, review-only evidence source. See
[docs/AI_ADVISORY_ARCHITECTURE.md](docs/AI_ADVISORY_ARCHITECTURE.md).

Child-safety datasets use safe, non-graphic descriptions. Illegal or explicit child-exploitation media must never be stored in this repository.

## Project structure

```text
trust-safety-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── main.py
│   │   └── schemas.py
│   ├── scripts/
│   └── requirements.txt
├── datasets/
├── docs/
├── frontend/
├── sample_uploads/
├── .gitignore
└── README.md


