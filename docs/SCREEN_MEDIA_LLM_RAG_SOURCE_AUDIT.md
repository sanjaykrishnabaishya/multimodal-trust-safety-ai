# Screen-media LLM/RAG source audit

This audit is an engineering screening record, not legal advice. Public access to
a repository is not itself permission to use its code, model weights, datasets,
or reference media. Each layer is reviewed separately.

## Approved for development integration

| Component | Source | Licence | Permitted role |
|---|---|---|---|
| Qwen2.5-0.5B-Instruct | `Qwen/Qwen2.5-0.5B-Instruct`, revision `7ae557604adf67be50417f59c2c2f167def9a775` | Apache-2.0 | Optional local evidence analyst; cannot verify titles, create Allow, or enforce |
| Transformers | `huggingface/transformers` | Apache-2.0 | Existing local inference runtime |
| Sentence-Transformers | `huggingface/sentence-transformers` | Apache-2.0 | Existing RAG embeddings and candidate retrieval |
| OpenCV | `opencv/opencv` | Apache-2.0 | Existing frame sampling and non-decisive image measurements |
| Tesseract | `tesseract-ocr/tesseract` | Apache-2.0 | Existing OCR evidence extraction |
| Wikidata structured entity data | Wikidata main/entity namespaces | CC0-1.0 | Film/series labels, aliases, entity IDs, types, and dates only |

The title catalog must not contain posters, film stills, scripts, subtitles,
plots copied from Wikipedia, or other copyrighted creative content. Exact title
retrieval is candidate generation. A title becomes verified only when a unique
CC0 entity match agrees with signed publisher or trusted rights-holder metadata.

## Not approved for product integration

| Candidate | Reason excluded |
|---|---|
| `openai/CLIP` | MIT code, but the model card says deployed use is out of scope and calls for task-specific testing; weight/data rights are not sufficiently clear for this product decision |
| `LAION-AI/CLIP-based-NSFW-Detector` | Repository says code/model are MIT, but it depends on CLIP and non-fully-annotated training material; keep research-only pending separate legal and quality review |
| `Falconsai/nsfw_image_detection` | Model is tagged Apache-2.0, but the fine-tuning dataset is proprietary and cannot be audited from the model card |
| `notAI-tech/NudeNet` and forks | Permissive code claims do not provide a sufficiently clear, separable audit of all bundled weights and adult-image training data |
| `yahoo/open_nsfw` and ports | Archived implementation; training dataset is not released, and modern ports add another provenance layer |

## Locked safety constraints

- LLM output is supporting evidence only.
- RAG retrieval never proves that uploaded pixels came from a retrieved work.
- User captions, OCR, transcripts, filenames, and embedded metadata are spoofable.
- Trusted provenance requires a verified publisher/rights-holder assertion.
- LLM or RAG uncertainty can escalate to review but cannot create Allow.
- Full-blur allowance requires an independently validated visual obscuration
  detector with adequate sampling and sensitive-region coverage.
- Pornography carrying a famous title remains a normal Graphic/Sexual decision
  unless trusted provenance is independently established.
- Child Exploitation, Sexual Harassment, and established category owners retain
  precedence.
