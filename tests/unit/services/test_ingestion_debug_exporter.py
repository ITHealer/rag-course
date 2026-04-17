from pathlib import Path

from src.schemas.indexing.models import ChunkMetadata, TextChunk
from src.schemas.pdf_parser.models import PaperSection, ParserType, PdfContent
from src.services.ingestion.debug_exporter import IngestionDebugExporter


def test_debug_exporter_writes_parser_and_chunk_markdown(tmp_path):
    watch_dir = tmp_path / "data"
    pdf_path = watch_dir / "nested" / "sample.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4\n")

    pdf_content = PdfContent(
        sections=[PaperSection(title="Intro", content="Hello world")],
        figures=[],
        tables=[],
        raw_text="Hello world from parser",
        references=[],
        parser_used=ParserType.DOCLING,
        metadata={"source": "docling", "title": "Sample"},
    )
    chunks = [
        TextChunk(
            text="Chunk text 1",
            metadata=ChunkMetadata(
                chunk_index=0,
                start_char=0,
                end_char=12,
                word_count=3,
                overlap_with_previous=0,
                overlap_with_next=0,
                section_title="Intro",
            ),
            arxiv_id="sample",
            paper_id="abc123",
        )
    ]

    exporter = IngestionDebugExporter(enabled=True, output_dir=str(tmp_path / "debug_artifacts"))
    exporter.export(watch_dir=watch_dir, pdf_path=pdf_path, pdf_content=pdf_content, chunks=chunks)

    parsed_file = tmp_path / "debug_artifacts" / "parsed" / "nested" / "sample.md"
    chunks_file = tmp_path / "debug_artifacts" / "chunks" / "nested" / "sample.md"

    assert parsed_file.exists()
    assert chunks_file.exists()
    assert "Parsed Output: sample.pdf" in parsed_file.read_text(encoding="utf-8")
    assert "Hello world from parser" in parsed_file.read_text(encoding="utf-8")
    assert "Chunk Output: sample.pdf" in chunks_file.read_text(encoding="utf-8")
    assert "Chunk text 1" in chunks_file.read_text(encoding="utf-8")
