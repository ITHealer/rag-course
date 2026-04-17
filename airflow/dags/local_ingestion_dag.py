import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

# Ensure the src directory is in the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from src.config import get_settings
from src.services.embeddings.factory import get_embeddings_client
from src.services.vector_store.factory import VectorStoreFactory
from src.services.indexing.text_chunker import TextChunker
from src.services.indexing.hybrid_indexer import HybridIndexingService
from src.services.pdf_parser.factory import make_pdf_parser_service
from src.services.ingestion.local_watcher import LocalFileWatcher

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "local_pdf_ingestion",
    default_args=default_args,
    description="Polls local data/ folder for new PDFs to index",
    schedule_interval="*/10 * * * *",  # Run every 10 minutes
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=["rag", "ingestion", "local"],
)

def process_local_pdfs():
    """Airflow task to wrap the async LocalFileWatcher."""
    settings = get_settings()
    project_root = Path(__file__).parent.parent.parent
    watch_dir = project_root / "data"
    state_file = project_root / ".ingest_state.json"
    
    pdf_parser = make_pdf_parser_service()
    chunker = TextChunker(
        chunk_size=settings.chunking.chunk_size,
        overlap_size=settings.chunking.overlap_size,
        min_chunk_size=settings.chunking.min_chunk_size
    )
    embeddings_client = get_embeddings_client(settings=settings)
    vector_store = VectorStoreFactory.get_vector_store(settings=settings)
    vector_store.setup_indices(force=False)
    
    indexer = HybridIndexingService(
        chunker=chunker,
        embeddings_client=embeddings_client,
        opensearch_client=vector_store
    )
    
    watcher = LocalFileWatcher(
        watch_dir=watch_dir,
        state_file=state_file,
        pdf_parser=pdf_parser,
        indexer=indexer,
        settings=settings
    )
    
    # Run the async code in a synchronous context for Airflow PythonOperator
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If in a running loop context (rare for standard airflow), use create_task/futures
        import nest_asyncio
        nest_asyncio.apply()
        
    loop.run_until_complete(watcher.process_new_files())

process_task = PythonOperator(
    task_id="process_local_pdfs",
    python_callable=process_local_pdfs,
    dag=dag,
)

process_task
