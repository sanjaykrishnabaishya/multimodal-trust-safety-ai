# System Architecture

## Multimodal processing flow

```text
User input
    |
    +-- Plain text
    |       |
    |       +-- Text normalization
    |
    +-- TXT, PDF, or DOCX
    |       |
    |       +-- Direct text extraction
    |       +-- OCR fallback for scanned PDF pages
    |
    +-- Image
    |       |
    |       +-- Image validation
    |       +-- Metadata extraction
    |       +-- OCR
    |       +-- Future visual understanding
    |
    +-- Video
            |
            +-- Metadata extraction
            +-- Frame sampling
            +-- Frame OCR
            +-- Future speech transcription
            +-- Future visual understanding

Extracted signals
    |
    +-- Extracted document text
    +-- OCR text
    +-- Audio transcript
    +-- Visual description
    +-- Source context
            |
            v
Future policy retrieval and RAG
            |
            v
Moderation decision
    |
    +-- Category
    +-- Severity
    +-- Action
    +-- Confidence
    +-- Explanation
    +-- Human-review requirement