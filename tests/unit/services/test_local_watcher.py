from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.schemas.indexing.models import ChunkMetadata, TextChunk
from src.schemas.pdf_parser.models import ParserType, PdfContent
from src.services.ingestion.local_watcher import LocalFileWatcher


@pytest.mark.asyncio
async def test_local_watcher_exports_debug_artifacts_and_indexes_with_shared_chunks(tmp_path):
    watch_dir = tmp_path / "data"
    pdf_path = watch_dir / "arxiv_pdfs" / "sample.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\nsample")

    state_file = tmp_path / ".ingest_state.json"
    debug_dir = tmp_path / "debug"

    pdf_content = PdfContent(
        sections=[],
        figures=[],
        tables=[],
        raw_text="Parsed content for validation",
        references=[],
        parser_used=ParserType.DOCLING,
        metadata={"title": "Sample title"},
    )
    shared_chunks = [
        TextChunk(
            text="Chunk content for validation",
            metadata=ChunkMetadata(
                chunk_index=0,
                start_char=0,
                end_char=28,
                word_count=4,
                overlap_with_previous=0,
                overlap_with_next=0,
                section_title="N/A",
            ),
            arxiv_id="sample",
            paper_id="deadbeef",
        )
    ]

    pdf_parser = MagicMock()
    pdf_parser.parse_pdf = AsyncMock(return_value=pdf_content)

    indexer = MagicMock()
    indexer.create_chunks.return_value = shared_chunks
    indexer.index_paper = AsyncMock(
        return_value={"chunks_created": 1, "chunks_indexed": 1, "embeddings_generated": 1, "errors": 0}
    )

    settings = SimpleNamespace(
        ingest_debug=SimpleNamespace(enabled=True, output_dir=str(debug_dir)),
    )

    watcher = LocalFileWatcher(
        watch_dir=watch_dir,
        state_file=state_file,
        pdf_parser=pdf_parser,
        indexer=indexer,
        settings=settings,
    )

    success_count = await watcher.process_new_files()

    assert success_count == 1
    indexer.index_paper.assert_awaited_once()
    assert indexer.index_paper.await_args.kwargs["precomputed_chunks"] == shared_chunks
    assert (debug_dir / "parsed" / "arxiv_pdfs" / "sample.md").exists()
    assert (debug_dir / "chunks" / "arxiv_pdfs" / "sample.md").exists()
