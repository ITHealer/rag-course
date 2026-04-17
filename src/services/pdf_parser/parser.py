import logging
import asyncio
import sys
from pathlib import Path
from typing import Optional

# Allow running as a standalone script
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[3]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))

from src.exceptions import PDFParsingException, PDFValidationError
from src.schemas.pdf_parser.models import PdfContent

from .docling import DoclingParser

logger = logging.getLogger(__name__)


class PDFParserService:
    """Main PDF parsing service using Docling only."""

    def __init__(self, max_pages: int, max_file_size_mb: int, do_ocr: bool = False, do_table_structure: bool = True):
        """Initialize PDF parser service with configurable limits."""
        self.docling_parser = DoclingParser(
            max_pages=max_pages, max_file_size_mb=max_file_size_mb, do_ocr=do_ocr, do_table_structure=do_table_structure
        )

    async def parse_pdf(self, pdf_path: Path) -> Optional[PdfContent]:
        """Parse PDF using Docling parser only.

        :param pdf_path: Path to PDF file
        :returns: PdfContent object or None if parsing failed
        """
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            raise PDFValidationError(f"PDF file not found: {pdf_path}")

        try:
            result = await self.docling_parser.parse_pdf(pdf_path)
            if result:
                logger.info(f"Parsed {pdf_path.name}")
                return result
            else:
                logger.error(f"Docling parsing returned no result for {pdf_path.name}")
                raise PDFParsingException(f"Docling parsing returned no result for {pdf_path.name}")

        except (PDFValidationError, PDFParsingException):
            raise
        except Exception as e:
            logger.error(f"Docling parsing error for {pdf_path.name}: {e}")
            raise PDFParsingException(f"Docling parsing error for {pdf_path.name}: {e}")


if __name__ == "__main__":
    from src.config import get_settings

    async def main():
        # --- CONFIGURATION START ---
        # Paste your PDF path here
        pdf_to_test = "data/arxiv_pdfs/2511.09554v2.pdf" 
        output_file = "parsed_output.md"
        # --- CONFIGURATION END ---

        settings = get_settings()
        parser_service = PDFParserService(
            max_pages=settings.pdf_parser.max_pages,
            max_file_size_mb=settings.pdf_parser.max_file_size_mb,
            do_ocr=settings.pdf_parser.do_ocr,
            do_table_structure=settings.pdf_parser.do_table_structure,
        )

        path = Path(pdf_to_test)
        if not path.exists():
            print(f"Error: File not found at {pdf_to_test}")
            return

        print(f"Starting to parse: {path.name}...")
        try:
            result = await parser_service.parse_pdf(path)
            if not result:
                print("Parsing failed: No content returned.")
                return

            # Format to Markdown
            md_content = []
            md_content.append(f"# Parsed Result: {path.name}")
            md_content.append(f"- **Title:** {result.metadata.get('title', 'N/A')}")
            md_content.append(f"- **Authors:** {', '.join(result.metadata.get('authors', [])) if isinstance(result.metadata.get('authors'), list) else result.metadata.get('authors', 'N/A')}")
            md_content.append(f"- **Parser Used:** {result.parser_used}")
            md_content.append(f"- **Raw Text Length:** {len(result.raw_text)} characters")
            md_content.append("\n---\n")

            if result.sections:
                md_content.append("## Sections Found")
                for i, section in enumerate(result.sections):
                    md_content.append(f"### {i+1}. {section.title}")
                    md_content.append(section.content[:500] + "..." if len(section.content) > 500 else section.content)
                    md_content.append("\n")
            else:
                md_content.append("## Raw Content (No sections detected)")
                md_content.append(result.raw_text[:2000] + "..." if len(result.raw_text) > 2000 else result.raw_text)

            # Write to file
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(md_content))

            print(f"✅ Success! Results saved to {output_file}")

        except Exception as e:
            print(f"❌ Error during parsing: {e}")

    asyncio.run(main())

