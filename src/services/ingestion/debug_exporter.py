import logging
from pathlib import Path
from typing import Sequence

from src.schemas.indexing.models import TextChunk
from src.schemas.pdf_parser.models import PdfContent

logger = logging.getLogger(__name__)


class IngestionDebugExporter:
    """Persist parser and chunking artifacts for local validation."""

    def __init__(self, enabled: bool, output_dir: str):
        self.enabled = enabled
        self.output_dir = Path(output_dir)

    def export(self, watch_dir: Path, pdf_path: Path, pdf_content: PdfContent, chunks: Sequence[TextChunk]) -> None:
        """Write parsed and chunked outputs to markdown files when debugging is enabled."""
        if not self.enabled:
            return

        relative_pdf_path = self._get_relative_pdf_path(watch_dir, pdf_path)
        parsed_path = (self.output_dir / "parsed" / relative_pdf_path).with_suffix(".md")
        chunks_path = (self.output_dir / "chunks" / relative_pdf_path).with_suffix(".md")

        parsed_path.parent.mkdir(parents=True, exist_ok=True)
        chunks_path.parent.mkdir(parents=True, exist_ok=True)

        parsed_path.write_text(self._build_parsed_markdown(pdf_path, pdf_content), encoding="utf-8")
        chunks_path.write_text(self._build_chunks_markdown(pdf_path, chunks), encoding="utf-8")

        logger.info("Saved ingestion debug artifacts for %s to %s", pdf_path.name, self.output_dir)

    def _get_relative_pdf_path(self, watch_dir: Path, pdf_path: Path) -> Path:
        try:
            return pdf_path.relative_to(watch_dir)
        except ValueError:
            return Path(pdf_path.name)

    def _build_parsed_markdown(self, pdf_path: Path, pdf_content: PdfContent) -> str:
        metadata_lines = [f"- **{key}:** {value}" for key, value in sorted(pdf_content.metadata.items())]
        if not metadata_lines:
            metadata_lines = ["- No parser metadata"]

        lines = [
            f"# Parsed Output: {pdf_path.name}",
            "",
            "## Summary",
            f"- **Parser:** {pdf_content.parser_used}",
            f"- **Sections:** {len(pdf_content.sections)}",
            f"- **Raw Text Length:** {len(pdf_content.raw_text)} characters",
            "",
            "## Metadata",
            *metadata_lines,
            "",
            "## Sections",
        ]

        if pdf_content.sections:
            for index, section in enumerate(pdf_content.sections, start=1):
                lines.extend(
                    [
                        f"### {index}. {section.title}",
                        "",
                        section.content or "_Empty section content_",
                        "",
                    ]
                )
        else:
            lines.extend(["_No sections extracted_", ""])

        lines.extend(["## Raw Text", "", pdf_content.raw_text or "_Empty raw text_", ""])
        return "\n".join(lines)

    def _build_chunks_markdown(self, pdf_path: Path, chunks: Sequence[TextChunk]) -> str:
        lines = [
            f"# Chunk Output: {pdf_path.name}",
            "",
            "## Summary",
            f"- **Chunks:** {len(chunks)}",
            "",
            "## Chunks",
        ]

        if not chunks:
            lines.extend(["_No chunks generated_", ""])
            return "\n".join(lines)

        for chunk in chunks:
            metadata = chunk.metadata
            lines.extend(
                [
                    f"### Chunk {metadata.chunk_index}",
                    "",
                    f"- **Section Title:** {metadata.section_title or 'N/A'}",
                    f"- **Word Count:** {metadata.word_count}",
                    f"- **Start Char:** {metadata.start_char}",
                    f"- **End Char:** {metadata.end_char}",
                    f"- **Overlap With Previous:** {metadata.overlap_with_previous}",
                    f"- **Overlap With Next:** {metadata.overlap_with_next}",
                    "",
                    chunk.text or "_Empty chunk text_",
                    "",
                ]
            )

        return "\n".join(lines)
