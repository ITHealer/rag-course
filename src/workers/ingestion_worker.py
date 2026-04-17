import asyncio
import logging
from pathlib import Path
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ingestion_worker")

# Setup project path to allow imports if run directly
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.config import get_settings
from src.services.embeddings.factory import get_embeddings_client
from src.services.vector_store.factory import VectorStoreFactory
from src.services.indexing.text_chunker import TextChunker
from src.services.indexing.hybrid_indexer import HybridIndexingService
from src.services.pdf_parser.factory import make_pdf_parser_service
from src.services.ingestion.local_watcher import LocalFileWatcher

async def run_worker():
    """Background job loop for watching the local data directory."""
    logger.info("Starting background ingestion worker...")
    
    settings = get_settings()
    
    watch_dir = project_root / "data"
    state_file = project_root / ".ingest_state.json"
    
    # Initialize Dependencies
    pdf_parser = make_pdf_parser_service()
    
    # Needs indexer which needs chunker, embedding, and vector_store
    chunker = TextChunker(
        chunk_size=settings.chunking.chunk_size,
        overlap_size=settings.chunking.overlap_size,
        min_chunk_size=settings.chunking.min_chunk_size
    )
    embeddings_client = get_embeddings_client(settings=settings)
    vector_store = VectorStoreFactory.get_vector_store(settings=settings)
    
    indexer = HybridIndexingService(
        chunker=chunker,
        embeddings_client=embeddings_client,
        opensearch_client=vector_store  # Interface matches BaseVectorStore
    )
    
    watcher = LocalFileWatcher(
        watch_dir=watch_dir,
        state_file=state_file,
        pdf_parser=pdf_parser,
        indexer=indexer,
        settings=settings
    )
    
    logger.info(f"Watching directory {watch_dir} for PDFs...")
    
    try:
        while True:
            await watcher.process_new_files()
            await asyncio.sleep(10)  # poll every 10 seconds
    except asyncio.CancelledError:
        logger.info("Ingestion worker shutdown requested")
    except KeyboardInterrupt:
        logger.info("Ingestion worker stopped by user")
    finally:
        logger.info("Closing clients...")
        # Since it's a script, things will naturally close, but we can call explicitly
        await embeddings_client.close()

if __name__ == "__main__":
    asyncio.run(run_worker())
