from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID

import pypdfium2 as pdfium
from fastapi import UploadFile
from opensearchpy import helpers

from src.config import PROJECT_ROOT, Settings
from src.db.interfaces.base import BaseDatabase
from src.repositories.ingestion_task import IngestionTaskRepository
from src.repositories.project_file import ProjectFileRepository
from src.schemas.indexing.models import ChunkMetadata, TextChunk
from src.services.embeddings.base import BaseEmbeddingsClient
from src.services.indexing.project_index_manager import ProjectIndexManager
from src.services.indexing.text_chunker import TextChunker
from src.services.pdf_parser.parser import PDFParserService
from src.services.vector_store.base import BaseVectorStore

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    raw_text: str
    sections: list[dict[str, Any]]
    parser_used: str
    page_count: int
    parser_metadata: dict[str, Any]


class ProjectKnowledgeService:
    """Control-plane service for project document uploads, ingestion jobs, and stats."""

    SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}

    def __init__(
        self,
        database: BaseDatabase,
        settings: Settings,
        pdf_parser: PDFParserService,
        embeddings_service: BaseEmbeddingsClient,
        vector_store: BaseVectorStore,
    ):
        self.database = database
        self.settings = settings
        self.pdf_parser = pdf_parser
        self.embeddings_service = embeddings_service
        self.vector_store = vector_store
        self.chunker = TextChunker(
            chunk_size=settings.chunking.chunk_size,
            overlap_size=settings.chunking.overlap_size,
            min_chunk_size=settings.chunking.min_chunk_size,
        )

        upload_root = Path(settings.project_upload_dir)
        if not upload_root.is_absolute():
            upload_root = (PROJECT_ROOT / upload_root).resolve()
        self.upload_root = upload_root
        self.upload_root.mkdir(parents=True, exist_ok=True)

        self._task_semaphore = asyncio.Semaphore(max(1, settings.project_ingestion_max_concurrency))
        self._running_tasks: dict[UUID, asyncio.Task] = {}

    async def save_uploaded_files(
        self,
        project_id: UUID,
        files: Sequence[UploadFile],
        project_file_repository: ProjectFileRepository,
    ) -> list[Any]:
        if not files:
            raise ValueError("No files provided for upload.")

        project_dir = self.upload_root / str(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        created_files = []

        for uploaded_file in files:
            if not uploaded_file.filename:
                raise ValueError("Uploaded file is missing filename.")

            safe_name = self._sanitize_filename(uploaded_file.filename)
            extension = Path(safe_name).suffix.lower()
            if extension not in self.SUPPORTED_EXTENSIONS:
                raise ValueError(f"Unsupported file type '{extension}'. Allowed: {sorted(self.SUPPORTED_EXTENSIONS)}")

            content = await uploaded_file.read()
            await uploaded_file.close()

            if not content:
                raise ValueError(f"Uploaded file '{safe_name}' is empty.")

            checksum_md5 = hashlib.md5(content).hexdigest()
            stored_name = f"{uuid.uuid4().hex}_{safe_name}"
            storage_path = project_dir / stored_name
            storage_path.write_bytes(content)

            payload = {
                "project_id": project_id,
                "file_name": safe_name,
                "file_extension": extension,
                "content_type": uploaded_file.content_type or "application/octet-stream",
                "size_bytes": len(content),
                "checksum_md5": checksum_md5,
                "storage_path": str(storage_path),
                "source_uri": storage_path.resolve().as_uri(),
                "status": "uploaded",
                "page_count": 0,
                "chunk_count": 0,
                "extra_metadata": {},
                "error_message": None,
            }
            created_files.append(project_file_repository.create(payload))

        return created_files

    def create_ingestion_task(
        self,
        project_id: UUID,
        file_ids: Sequence[UUID],
        ingestion_task_repository: IngestionTaskRepository,
    ) -> Any:
        queued_file_ids = [str(file_id) for file_id in file_ids]
        payload = {
            "project_id": project_id,
            "status": "pending",
            "total_files": len(queued_file_ids),
            "processed_files": 0,
            "failed_files": 0,
            "queued_file_ids": queued_file_ids,
            "error_message": None,
            "started_at": None,
            "completed_at": None,
        }
        return ingestion_task_repository.create(payload)

    def start_ingestion_task(self, task_id: UUID) -> None:
        running_task = self._running_tasks.get(task_id)
        if running_task and not running_task.done():
            return

        task = asyncio.create_task(self._run_task(task_id))
        self._running_tasks[task_id] = task

        def _cleanup(finished_task: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            try:
                finished_task.result()
            except Exception:  # pragma: no cover - already logged in _run_task
                logger.exception("Ingestion task %s ended with an unhandled error.", task_id)

        task.add_done_callback(_cleanup)

    async def shutdown(self) -> None:
        if not self._running_tasks:
            return
        pending = [task for task in self._running_tasks.values() if not task.done()]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        self._running_tasks.clear()

    async def _run_task(self, task_id: UUID) -> None:
        async with self._task_semaphore:
            logger.info("Starting ingestion task %s", task_id)
            started_at = datetime.now(timezone.utc)

            task_record = self._get_task(task_id)
            if task_record is None:
                logger.error("Ingestion task %s not found.", task_id)
                return

            try:
                file_ids = self._parse_file_ids(task_record.queued_file_ids)
                self._update_task(
                    task_id=task_id,
                    update_data={
                        "status": "running",
                        "started_at": started_at,
                        "error_message": None,
                    },
                )

                if not hasattr(self.vector_store, "client"):
                    self._fail_task(task_id, "Current vector store does not support project ingestion.")
                    return

                index_manager = ProjectIndexManager(opensearch_client=self.vector_store.client, settings=self.settings)
                index_info = index_manager.ensure_project_ready(project_id=str(task_record.project_id))
                index_name = index_info["index_name"]

                processed_files = 0
                failed_files = 0

                for file_id in file_ids:
                    success = await self._process_file(
                        task_id=task_id,
                        project_id=task_record.project_id,
                        file_id=file_id,
                        index_name=index_name,
                    )
                    processed_files += 1
                    if not success:
                        failed_files += 1
                    self._update_task(
                        task_id=task_id,
                        update_data={
                            "processed_files": processed_files,
                            "failed_files": failed_files,
                        },
                    )

                completed_at = datetime.now(timezone.utc)
                final_status = "completed"
                error_message = None
                if failed_files > 0 and failed_files == processed_files:
                    final_status = "failed"
                    error_message = "All files in this ingestion task failed."
                elif failed_files > 0:
                    final_status = "completed_with_errors"
                    error_message = f"{failed_files} of {processed_files} files failed."

                self._update_task(
                    task_id=task_id,
                    update_data={
                        "status": final_status,
                        "completed_at": completed_at,
                        "error_message": error_message,
                    },
                )
                logger.info(
                    "Completed ingestion task %s with status=%s processed=%s failed=%s",
                    task_id,
                    final_status,
                    processed_files,
                    failed_files,
                )
            except Exception as exc:
                logger.exception("Ingestion task %s crashed: %s", task_id, exc)
                self._fail_task(task_id, str(exc))


    async def _process_file(self, task_id: UUID, project_id: UUID, file_id: UUID, index_name: str) -> bool:
        file_record = self._get_project_file(project_id=project_id, file_id=file_id)
        if file_record is None:
            logger.error("Task %s: file %s not found for project %s.", task_id, file_id, project_id)
            return False

        self._update_project_file(file_id, {"status": "processing", "error_message": None})
        try:
            parsed_document = await self._extract_document(file_record)
            chunks = self._build_chunks(file_record=file_record, parsed_document=parsed_document)
            if not chunks:
                raise ValueError("No chunks generated from file content.")

            indexed_count = await self._index_chunks(
                project_id=project_id,
                file_record=file_record,
                parsed_document=parsed_document,
                chunks=chunks,
                index_name=index_name,
            )
            self._update_project_file(
                file_id,
                {
                    "status": "indexed",
                    "chunk_count": indexed_count,
                    "page_count": parsed_document.page_count,
                    "parser_used": parsed_document.parser_used,
                    "error_message": None,
                    "extra_metadata": parsed_document.parser_metadata,
                },
            )
            logger.info("Task %s indexed file %s with %s chunks.", task_id, file_record.file_name, indexed_count)
            return True
        except Exception as exc:
            logger.exception("Task %s failed while processing file %s: %s", task_id, file_record.file_name, exc)
            self._update_project_file(file_id, {"status": "failed", "error_message": str(exc)})
            return False

    async def _extract_document(self, file_record: Any) -> ParsedDocument:
        path = Path(file_record.storage_path)
        extension = file_record.file_extension.lower()

        if extension == ".pdf":
            parsed = await self.pdf_parser.parse_pdf(path)
            if parsed is None or not parsed.raw_text.strip():
                raise ValueError("PDF parser returned empty content.")

            sections = [section.model_dump() for section in parsed.sections] if parsed.sections else []
            page_count = self._get_pdf_page_count(path)
            parser_used = parsed.parser_used.value if hasattr(parsed.parser_used, "value") else str(parsed.parser_used)
            return ParsedDocument(
                raw_text=parsed.raw_text,
                sections=sections,
                parser_used=parser_used,
                page_count=page_count,
                parser_metadata=parsed.metadata or {},
            )

        if extension in {".md", ".txt"}:
            raw_text = path.read_text(encoding="utf-8", errors="ignore")
            if not raw_text.strip():
                raise ValueError("Text file is empty after decoding.")
            return ParsedDocument(
                raw_text=raw_text,
                sections=[],
                parser_used="plain_text",
                page_count=1,
                parser_metadata={},
            )

        raise ValueError(f"Unsupported file extension '{extension}'.")

    def _build_chunks(self, file_record: Any, parsed_document: ParsedDocument) -> list[TextChunk]:
        file_key = str(file_record.id)
        if parsed_document.sections:
            return self.chunker.chunk_paper(
                title=file_record.file_name,
                abstract="",
                full_text=parsed_document.raw_text,
                arxiv_id=file_key,
                paper_id=file_key,
                sections=parsed_document.sections,
            )
        return self.chunker.chunk_text(parsed_document.raw_text, arxiv_id=file_key, paper_id=file_key)

    async def _index_chunks(
        self,
        project_id: UUID,
        file_record: Any,
        parsed_document: ParsedDocument,
        chunks: list[TextChunk],
        index_name: str,
    ) -> int:
        chunk_texts = [chunk.text for chunk in chunks]
        embeddings = await self.embeddings_service.embed_passages(chunk_texts, batch_size=50)
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding generation count mismatch with chunks.")

        self.vector_store.client.delete_by_query(
            index=index_name,
            body={
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"project_id": str(project_id)}},
                            {"term": {"file_id": str(file_record.id)}},
                        ]
                    }
                }
            },
            refresh=True,
            conflicts="proceed",
        )

        text_length = len(parsed_document.raw_text)
        timestamp = datetime.now(timezone.utc).isoformat()
        actions = []
        for chunk, embedding in zip(chunks, embeddings):
            page_number = self._estimate_page_number(
                total_pages=parsed_document.page_count,
                start_char=chunk.metadata.start_char,
                total_text_length=text_length,
            )
            actions.append(
                {
                    "_index": index_name,
                    "_id": f"{file_record.id}-{chunk.metadata.chunk_index}",
                    "_source": {
                        "project_id": str(project_id),
                        "file_id": str(file_record.id),
                        "doc_name": file_record.file_name,
                        "page_number": page_number,
                        "chunk_index": chunk.metadata.chunk_index,
                        "chunk_text": chunk.text,
                        "source_type": "project_file",
                        "source_uri": file_record.source_uri,
                        "doc_type": file_record.file_extension.lstrip("."),
                        "metadata": {
                            "word_count": chunk.metadata.word_count,
                            "start_char": chunk.metadata.start_char,
                            "end_char": chunk.metadata.end_char,
                            "overlap_with_previous": chunk.metadata.overlap_with_previous,
                            "overlap_with_next": chunk.metadata.overlap_with_next,
                            "section_title": chunk.metadata.section_title,
                        },
                        "embedding": embedding,
                        "created_at": timestamp,
                        "updated_at": timestamp,
                    },
                }
            )

        success_count, failures = helpers.bulk(
            self.vector_store.client,
            actions,
            refresh=True,
            raise_on_error=False,
        )
        failure_count = len(failures)
        if failure_count > 0:
            raise ValueError(f"Indexing failed for {failure_count} chunks.")
        return int(success_count)

    def get_file_chunks(self, project_id: UUID, file_id: UUID, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        if not hasattr(self.vector_store, "client"):
            return {"total": 0, "items": []}

        index_manager = ProjectIndexManager(opensearch_client=self.vector_store.client, settings=self.settings)
        index_name = index_manager.get_index_name(str(project_id))
        if not self.vector_store.client.indices.exists(index=index_name):
            return {"total": 0, "items": []}

        query = {
            "from": offset,
            "size": limit,
            "track_total_hits": True,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"project_id": str(project_id)}},
                        {"term": {"file_id": str(file_id)}},
                    ]
                }
            },
            "sort": [{"chunk_index": {"order": "asc"}}],
            "_source": ["chunk_index", "page_number", "chunk_text", "metadata"],
        }
        response = self.vector_store.client.search(index=index_name, body=query)
        total = int(response["hits"]["total"]["value"])
        items = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            metadata = source.get("metadata", {})
            items.append(
                {
                    "chunk_id": hit["_id"],
                    "chunk_index": source.get("chunk_index", 0),
                    "page_number": source.get("page_number", 1),
                    "chunk_text": source.get("chunk_text", ""),
                    "word_count": metadata.get("word_count"),
                    "section_title": metadata.get("section_title"),
                }
            )

        return {"total": total, "items": items}

    def get_project_stats(
        self,
        project_id: UUID,
        project_file_repository: ProjectFileRepository,
        ingestion_task_repository: IngestionTaskRepository,
    ) -> dict[str, Any]:
        files = project_file_repository.list_by_project(project_id=project_id, limit=10000, offset=0)
        tasks = ingestion_task_repository.list_by_project(project_id=project_id, limit=10000, offset=0)

        status_counts = {"indexed": 0, "processing": 0, "failed": 0, "uploaded": 0}
        file_type_breakdown: dict[str, int] = {}
        total_chunks = 0
        total_size_bytes = 0

        for file_record in files:
            status_counts[file_record.status] = status_counts.get(file_record.status, 0) + 1
            file_type_breakdown[file_record.file_extension] = file_type_breakdown.get(file_record.file_extension, 0) + 1
            total_chunks += int(file_record.chunk_count or 0)
            total_size_bytes += int(file_record.size_bytes or 0)

        active_tasks = sum(1 for task in tasks if task.status in {"pending", "running"})
        last_ingestion_at = None
        completed_times = [task.completed_at for task in tasks if task.completed_at is not None]
        if completed_times:
            last_ingestion_at = max(completed_times)

        index_document_count = self._count_project_index_documents(project_id)
        return {
            "project_id": project_id,
            "total_files": len(files),
            "indexed_files": status_counts.get("indexed", 0),
            "processing_files": status_counts.get("processing", 0) + status_counts.get("uploaded", 0),
            "failed_files": status_counts.get("failed", 0),
            "total_chunks": total_chunks,
            "total_size_bytes": total_size_bytes,
            "total_tasks": len(tasks),
            "active_tasks": active_tasks,
            "file_type_breakdown": file_type_breakdown,
            "index_document_count": index_document_count,
            "last_ingestion_at": last_ingestion_at,
        }

    def _count_project_index_documents(self, project_id: UUID) -> int:
        if not hasattr(self.vector_store, "client"):
            return 0

        index_manager = ProjectIndexManager(opensearch_client=self.vector_store.client, settings=self.settings)
        index_name = index_manager.get_index_name(str(project_id))
        if not self.vector_store.client.indices.exists(index=index_name):
            return 0

        response = self.vector_store.client.count(
            index=index_name,
            body={"query": {"term": {"project_id": str(project_id)}}},
        )
        return int(response.get("count", 0))

    def _get_task(self, task_id: UUID) -> Any | None:
        with self.database.get_session() as session:
            repo = IngestionTaskRepository(session)
            return repo.get_by_id(task_id)

    def _get_project_file(self, project_id: UUID, file_id: UUID) -> Any | None:
        with self.database.get_session() as session:
            repo = ProjectFileRepository(session)
            return repo.get_by_project_and_id(project_id=project_id, file_id=file_id)

    def _update_task(self, task_id: UUID, update_data: dict[str, Any]) -> None:
        with self.database.get_session() as session:
            repo = IngestionTaskRepository(session)
            task = repo.get_by_id(task_id)
            if task:
                repo.update(task, update_data)

    def _update_project_file(self, file_id: UUID, update_data: dict[str, Any]) -> None:
        with self.database.get_session() as session:
            repo = ProjectFileRepository(session)
            file_record = repo.get_by_id(file_id)
            if file_record:
                repo.update(file_record, update_data)

    def _fail_task(self, task_id: UUID, message: str) -> None:
        logger.error("Ingestion task %s failed: %s", task_id, message)
        self._update_task(
            task_id=task_id,
            update_data={
                "status": "failed",
                "error_message": message,
                "completed_at": datetime.now(timezone.utc),
            },
        )

    def _parse_file_ids(self, raw_file_ids: Sequence[str]) -> list[UUID]:
        parsed = []
        for raw in raw_file_ids:
            try:
                parsed.append(UUID(str(raw)))
            except (TypeError, ValueError):
                logger.warning("Skipping invalid file ID in queued list: %s", raw)
        return parsed

    def _sanitize_filename(self, file_name: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "_", file_name).strip("._")
        return sanitized or "uploaded_file"

    def _get_pdf_page_count(self, file_path: Path) -> int:
        pdf_doc = pdfium.PdfDocument(str(file_path))
        try:
            return len(pdf_doc)
        finally:
            pdf_doc.close()

    def _estimate_page_number(self, total_pages: int, start_char: int, total_text_length: int) -> int:
        if total_pages <= 1 or total_text_length <= 0:
            return 1

        ratio = max(0.0, min(float(start_char) / float(total_text_length), 0.999999))
        estimated = int(ratio * total_pages) + 1
        return max(1, min(estimated, total_pages))
