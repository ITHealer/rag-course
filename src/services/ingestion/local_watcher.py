import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from src.config import Settings
from src.services.ingestion.debug_exporter import IngestionDebugExporter
from src.services.indexing.hybrid_indexer import HybridIndexingService
from src.services.pdf_parser.parser import PDFParserService

logger = logging.getLogger(__name__)

class LocalFileWatcher:
    """Watches a local directory for PDFs, parses and indexes new ones."""

    def __init__(
        self,
        watch_dir: Path,
        state_file: Path,
        pdf_parser: PDFParserService,
        indexer: HybridIndexingService,
        settings: Settings
    ):
        self.watch_dir = watch_dir
        self.state_file = state_file
        self.pdf_parser = pdf_parser
        self.indexer = indexer
        self.settings = settings
        self.debug_exporter = IngestionDebugExporter(
            enabled=settings.ingest_debug.enabled,
            output_dir=settings.ingest_debug.output_dir,
        )
        
        # Ensure watch_dir exists
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        
        self.processed_files: Dict[str, str] = self._load_state()

    def _load_state(self) -> Dict[str, str]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading state file: {e}")
                return {}
        return {}

    def _save_state(self):
        try:
            with open(self.state_file, "w") as f:
                json.dump(self.processed_files, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def _calculate_md5(self, file_path: Path) -> str:
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error hashing {file_path}: {e}")
            return ""

    def _build_paper_data(self, pdf_path: Path, file_hash: str, raw_text: str, sections: list, metadata: dict) -> Dict:
        stem = pdf_path.stem
        return {
            "id": file_hash[:8],
            "arxiv_id": stem,
            "title": metadata.get("title") or stem,
            "abstract": raw_text[:500] + "..." if raw_text else "No abstract",
            "authors": metadata.get("authors") or ["Local Author"],
            "categories": ["local.Upload"],
            "published_date": datetime.now(timezone.utc),
            "raw_text": raw_text,
            "sections": sections,
        }

    async def process_new_files(self) -> int:
        """Scan directory and process any new or modified PDFs.
        
        Returns: number of successfully processed files.
        """
        success_count = 0
        
        if not self.watch_dir.exists():
            return 0
            
        all_pdfs = list(self.watch_dir.rglob("*.pdf"))
        logger.info(f"Scanning directory: Found {len(all_pdfs)} PDF files total.")
        
        for pdf_path in all_pdfs:
            file_name = pdf_path.name
            
            # Simple check by modified time / size could be added, but MD5 is safest
            file_hash = self._calculate_md5(pdf_path)
            if not file_hash:
                continue
                
            if file_name in self.processed_files and self.processed_files[file_name] == file_hash:
                # Already processed this exact version
                continue
                
            logger.info(f"New file detected... {file_name}")
            try:
                # 1. Parse PDF
                pdf_content = await self.pdf_parser.parse_pdf(pdf_path)
                if not pdf_content:
                    logger.error(f"Failed to parse {file_name}, skipping.")
                    continue

                sections = [section.model_dump() for section in pdf_content.sections] if pdf_content.sections else []
                paper_data = self._build_paper_data(
                    pdf_path=pdf_path,
                    file_hash=file_hash,
                    raw_text=pdf_content.raw_text,
                    sections=sections,
                    metadata=pdf_content.metadata,
                )

                # 2. Create chunks once so debug export and indexing use the same data
                chunks = self.indexer.create_chunks(paper_data)
                self.debug_exporter.export(
                    watch_dir=self.watch_dir,
                    pdf_path=pdf_path,
                    pdf_content=pdf_content,
                    chunks=chunks,
                )

                if not chunks:
                    logger.error(f"No chunks created for {file_name}, skipping indexing.")
                    continue

                # 3. Index it using HybridIndexer
                logger.info(f"Indexing {file_name}...")
                stats = await self.indexer.index_paper(paper_data, precomputed_chunks=chunks)
                
                if stats.get("chunks_indexed", 0) == 0:
                    logger.error(f"Failed to index any chunks for {file_name}.")
                else:
                    logger.info(f"Successfully processed {file_name}: {stats['chunks_indexed']} chunks indexed.")
                    
                    # 4. Mark as processed
                    self.processed_files[file_name] = file_hash
                    self._save_state()
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing {file_name}: {e}")
                
        return success_count
