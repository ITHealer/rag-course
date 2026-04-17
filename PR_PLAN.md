# PR Plan: Fix Empty PDF Parsing in Docling Ingestion Pipeline

## Summary
The current PDF ingestion flow can treat a Docling conversion with empty output as a successful parse. This produces `raw_text=""`, empty sections, and downstream indexing of useless content.

The problem is not primarily caused by unsupported `convert()` parameters in the current environment. The installed version is `docling 2.52.0`, and `DocumentConverter.convert()` does support `max_num_pages` and `max_file_size`.

The real issue is a combination of:

1. The sample PDF has no extractable text layer for `pypdfium2`.
2. Docling returns `ConversionStatus.SUCCESS` but produces an empty `document`.
3. Our parser does not validate `result.status`, empty `raw_text`, or empty document items before returning `PdfContent`.
4. The watcher and orchestration layer continue indexing even when parse quality is effectively zero.

## Evidence Collected
### Runtime evidence
- Running `src.services.pdf_parser.parser` against `data/arxiv_pdfs/2511.09554v2.pdf` reproduces:
  - `Document conversion finished. Items count: 0`
  - `Extracted raw_text is empty!`
- Direct inspection of Docling in this repo shows:
  - `docling==2.52.0`
  - `DocumentConverter.convert(...)` accepts `max_num_pages` and `max_file_size`
- Direct conversion of the sample PDF with the repo's effective limits (`max_file_size=50MB`) returns:
  - `ConversionStatus.SUCCESS`
  - `len(doc.texts) == 0`
  - `doc.export_to_text() == ""`
- Direct inspection with `pypdfium2` on the first page returns:
  - `count_chars() == 0`

### Code-path evidence
- [src/services/pdf_parser/docling.py](/D:/ai-leanrning/production-agentic-rag-course/src/services/pdf_parser/docling.py#L107) calls Docling and immediately consumes `result.document` without checking `result.status`.
- [src/services/pdf_parser/docling.py](/D:/ai-leanrning/production-agentic-rag-course/src/services/pdf_parser/docling.py#L125) only logs when `raw_text` is empty, then still returns `PdfContent`.
- [src/services/ingestion/local_watcher.py](/D:/ai-leanrning/production-agentic-rag-course/src/services/ingestion/local_watcher.py#L93) only treats `None` as parse failure.
- [src/services/ingestion/local_watcher.py](/D:/ai-leanrning/production-agentic-rag-course/src/services/ingestion/local_watcher.py#L101) builds `paper_data` even when `raw_text` is empty.
- [src/workers/ingestion_worker.py](/D:/ai-leanrning/production-agentic-rag-course/src/workers/ingestion_worker.py#L35) and [airflow/dags/local_ingestion_dag.py](/D:/ai-leanrning/production-agentic-rag-course/airflow/dags/local_ingestion_dag.py#L47) duplicate ingestion bootstrap logic, which increases drift risk when parser handling changes.

## Root Cause
### Primary root cause
`DoclingParser.parse_pdf()` assumes Docling success means usable content. That assumption is false for some PDFs. In the reproduced case, Docling produces an empty document and the parser still returns a "successful" `PdfContent`.

### Secondary root cause
The current validation only checks:
- file exists
- non-zero size
- PDF header
- page count
- file size

It does not validate parse quality after conversion.

### Contributing factors
- `do_ocr=False` by default is reasonable for performance, but there is no controlled fallback when the PDF has no text layer.
- There is no parser-result classification such as `SUCCESS`, `EMPTY`, `FAILED`, `FALLBACK_USED`.
- The ingestion flow is missing fail-fast guards before indexing.
- Tests do not cover "Docling returns success + empty content" or "watcher skips empty parse output".

## What Is Not the Root Cause
- Unsupported Docling `convert()` parameters: not applicable in this repo's installed version.
- Airflow scheduling itself: the DAG is not causing the empty parse; it only reuses the same parser path.
- Worker loop polling: same as above.

## Goals
- Stop treating empty Docling output as a successful parse.
- Prevent empty content from reaching chunking and indexing.
- Add a deterministic fallback strategy for PDFs with no text layer or empty Docling output.
- Centralize ingestion bootstrap so worker and DAG use the same code path.
- Add tests that cover parser-quality gates and orchestration behavior.

## Non-Goals
- Rebuild the full ingestion architecture.
- Introduce a large multi-parser framework in this PR.
- Optimize OCR throughput for all document types.

## Proposed Solution
### 1. Add parser-quality guards in `DoclingParser`
Update `DoclingParser.parse_pdf()` to validate conversion output after `convert()`:

- Check `result.status`.
- Check whether the document has meaningful extracted content.
- Treat these as parse failure conditions:
  - non-success status
  - empty `raw_text`
  - zero extracted text items and zero sections

Expected behavior:
- raise `PDFParsingException` with a precise reason, or
- return `None` only for explicitly skipped cases such as page/file-size policy limits.

This removes the current ambiguous state where parsing "succeeds" but returns no usable content.

### 2. Add fallback parsing strategy for no-text-layer PDFs
Introduce a narrow fallback path when Docling returns empty content:

Recommended order:
1. Detect "no text layer / empty extraction" after the first Docling attempt.
2. Retry Docling with OCR-oriented options:
   - `do_ocr=True`
   - `ocr_options.force_full_page_ocr=True`
3. If OCR dependencies are unavailable or fallback still returns empty output, fail explicitly with a structured error.

Why this approach:
- Keeps Docling as the primary parser.
- Handles scanned/image-heavy PDFs without silently producing empty output.
- Avoids introducing a larger parser abstraction in the same PR.

Optional follow-up, not required for this PR:
- add a secondary backend such as PyMuPDF-based markdown extraction if the team wants a second non-OCR fallback.

### 3. Introduce explicit parse outcome semantics
Extend parser metadata or internal return handling to classify outcomes:
- `success`
- `skipped_by_policy`
- `empty_output`
- `fallback_success`
- `fallback_failed`

At minimum, metadata/logging must record:
- parser used
- docling status
- whether fallback was triggered
- why the file was skipped or failed

This is necessary for observability and future operations.

### 4. Block indexing of empty content in `LocalFileWatcher`
Before building `paper_data`, enforce a content guard:
- skip if `raw_text.strip()` is empty
- skip if both `raw_text` and `sections` are empty
- log the reason with file name and parser metadata

This ensures the index only contains meaningful content, even if parser behavior regresses again.

### 5. Extract shared ingestion bootstrap
Create a shared builder or factory for ingestion dependencies so that:
- worker
- Airflow DAG

both use the same initialization path.

Suggested module:
- `src/services/ingestion/bootstrap.py`

Responsibilities:
- load settings
- create parser
- create chunker
- create embeddings client
- create vector store
- create indexer
- create watcher

Benefits:
- one place to apply parser/fallback changes
- lower maintenance cost
- fewer environment-specific drifts

## Task Breakdown
### Task 1: Harden Docling parse result handling
Files:
- `src/services/pdf_parser/docling.py`

Actions:
- inspect `result.status` before consuming `result.document`
- extract helper functions:
  - `_extract_raw_text(...)`
  - `_build_sections(...)`
  - `_is_empty_parse_result(...)`
- fail explicitly on empty conversion output
- improve error messages to distinguish:
  - invalid PDF
  - policy skip
  - empty output
  - OCR fallback failure

### Task 2: Add OCR fallback for empty extraction
Files:
- `src/services/pdf_parser/docling.py`
- possibly `src/config.py`
- possibly `.env.example`

Actions:
- add dedicated fallback converter or fallback pipeline options
- enable `force_full_page_ocr` for fallback mode
- make fallback behavior configurable, for example:
  - `PDF_PARSER__ENABLE_OCR_FALLBACK=true`
  - `PDF_PARSER__OCR_FALLBACK_TIMEOUT_SECONDS`
- log when fallback is triggered and why

### Task 3: Prevent empty indexing
Files:
- `src/services/ingestion/local_watcher.py`

Actions:
- add `has_meaningful_content(pdf_content)` guard
- skip indexing for empty parse output
- keep the file unprocessed, or mark it with failure status depending on product decision
- log structured reason for skip/failure

Decision required:
- for failed parse attempts, do we want retry-on-next-scan or permanent quarantine after N failures?

Recommended for this PR:
- retry is allowed, but add a failure counter in state as a follow-up issue

### Task 4: Remove worker/DAG bootstrap duplication
Files:
- `src/workers/ingestion_worker.py`
- `airflow/dags/local_ingestion_dag.py`
- new `src/services/ingestion/bootstrap.py`

Actions:
- move shared dependency construction into one function
- keep orchestration layers thin
- ensure resource cleanup still happens in worker/DAG entrypoints

### Task 5: Expand tests
Files:
- `tests/unit/services/test_pdf_parser.py`
- new watcher tests if missing, for example:
  - `tests/unit/services/ingestion/test_local_watcher.py`

Actions:
- add unit tests for:
  - Docling success + empty document => parser failure
  - Docling failure status => parser failure
  - policy skip => returns `None`
  - fallback success => returns populated `PdfContent`
  - fallback failure => raises `PDFParsingException`
- add watcher tests for:
  - empty parse result is not indexed
  - successful parse is indexed
  - state file only updates after successful indexing

## Testing Plan
### Unit tests
- `DoclingParser.parse_pdf()` returns `None` for page/file-size policy skips.
- `DoclingParser.parse_pdf()` raises on `ConversionStatus.FAILURE`.
- `DoclingParser.parse_pdf()` raises on `ConversionStatus.SUCCESS` with empty output.
- `DoclingParser.parse_pdf()` triggers OCR fallback when initial extraction is empty.
- `LocalFileWatcher.process_new_files()` skips indexing when parser output is empty.

### Integration tests
- Use a real PDF fixture with extractable text and assert non-empty `raw_text`.
- Use a fixture that reproduces the current failure mode and assert:
  - initial parse fails quality gate
  - fallback is attempted
  - final outcome is explicit, never silent-empty

### Manual verification
1. Run:
   ```powershell
   uv run python -m src.services.pdf_parser.parser
   ```
2. Verify the sample file no longer reports success with empty output.
3. Drop the sample PDF into `data/` and run the worker path.
4. Verify the watcher does not index empty content.
5. Verify logs clearly show:
   - initial Docling outcome
   - fallback attempt
   - final parse decision

### Regression checks
- Text-based arXiv PDFs still parse successfully.
- Worker loop still continues after one file fails.
- Airflow DAG still runs one-shot ingestion without event-loop errors.

## Rollout Strategy
### Phase 1
- merge parser-quality guard
- merge empty-index blocking
- merge tests

### Phase 2
- enable OCR fallback behind config flag
- validate on a small corpus of known problematic PDFs

### Phase 3
- extract shared ingestion bootstrap
- update worker and DAG to use it

## Risks
- OCR fallback may be slow on CPU-heavy environments.
- OCR fallback may require additional runtime dependencies.
- Some PDFs may still fail even after OCR; those failures must remain explicit and observable.
- If the watcher retries the same broken file every scan, logs may become noisy until retry/quarantine policy is added.

## Acceptance Criteria
- A PDF that produces empty Docling output is no longer treated as a successful parse.
- Empty parse output never reaches indexing.
- Parser logs explain why the document failed or was skipped.
- Worker and DAG use a shared ingestion bootstrap path.
- Tests cover the empty-success regression case.

## Recommended PR Structure
### PR 1
- parser quality gates
- watcher indexing guard
- unit tests

### PR 2
- OCR fallback configuration and implementation
- integration tests with problematic fixtures

### PR 3
- ingestion bootstrap refactor for worker + DAG

## Open Questions
- Should failed files be retried indefinitely, or quarantined after a threshold?
- Do we want OCR fallback enabled by default in development only, or in all environments?
- Is adding a second parser backend in a later PR acceptable if Docling OCR remains unreliable on some PDFs?
