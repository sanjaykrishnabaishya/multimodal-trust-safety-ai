# Project Development Stages

## Stage 1 — FastAPI foundation

Status: Complete

Completed work:

- Created the project folders
- Created a Python virtual environment
- Installed FastAPI
- Created the FastAPI application
- Added the root endpoint
- Added the health endpoint
- Added the placeholder moderation endpoint
- Tested the API through Swagger

## Stage 2 — Multimodal datasets

Status: Complete

Generated:

- `datasets/text_dataset.csv`: 400 records
- `datasets/document_dataset.csv`: 200 records
- `datasets/image_dataset.csv`: 250 records
- `datasets/video_dataset.csv`: 150 records
- `datasets/policies.csv`: 9 policy records

The datasets contain safe synthetic examples and contextual labels for:

- News
- Education
- Art
- Medical material
- Gaming
- Human-review cases

The dataset captions and frame descriptions are annotations. Users will not need to provide captions when uploading media.

## Stage 3 — Upload and extraction pipeline

Status: Complete

Completed work:

- Added direct text extraction
- Added multipart file upload
- Added TXT extraction
- Added PDF text extraction
- Added DOCX paragraph and table extraction
- Added image validation and metadata extraction
- Added video metadata extraction
- Added in-memory frame sampling
- Added supported-extension validation
- Added a 100 MB upload limit
- Added a common normalized response structure

## Stage 4 — Optical character recognition

Status: Complete

Completed work:

- Installed Tesseract OCR
- Added the Python OCR service
- Added image preprocessing for OCR
- Added OCR for standalone images
- Added OCR fallback for scanned PDF pages
- Added OCR for sampled video frames
- Added the `/extract/ocr-health` endpoint
- Ensured temporary video files and frames are not permanently stored

Current limitation:

OCR reads visible words but does not understand the complete visual scene, objects, actions, or intent.

## Stage 5 — Speech transcription

Status: Not started

Planned work:

- Add local Whisper speech transcription
- Extract spoken words from video audio
- Detect spoken language
- Return timestamped transcript segments
- Combine audio transcript with video OCR

## Later stages

Planned work:

- Visual scene understanding
- Policy-rule engine
- RAG retrieval
- Multimodal decision fusion
- Confidence thresholds
- Human-review workflow
- Frontend
- Automated testing
- Deployment