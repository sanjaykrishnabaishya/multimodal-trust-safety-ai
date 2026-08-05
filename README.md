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

## Planned capabilities

The following components are planned:

- Video speech transcription
- Visual scene understanding
- Basic policy moderation
- RAG policy retrieval
- Confidence thresholds
- Human-review routing
- Frontend upload interface
- Testing and evaluation

## Supported moderation categories

1. Child Abuse
2. Spam
3. Scam
4. Harassment/Cyberbullying
5. Hate Speech
6. Fake News
7. Violence
8. Nudity
9. Normal/Ignore

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


