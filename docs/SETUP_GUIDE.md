# Agentic RAG System Setup Guide

## Overview
This refactored system supports pluggable architectures for Vector Stores, Embedding Providers, and Observability Tools. Out of the box, it connects to both legacy instances (OpenSearch, Jina, Langfuse) and local, decoupled open-source variants.

## Running the Web API
```bash
cp .env.example .env
# Edit .env to set your desired VECTOR_STORE, EMBEDDINGS_PROVIDER, and TRACER
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Running the Background Ingestion Worker
For local PDF ingesting, a Python worker continually watches the `data/` folder for new PDFs:
```bash
uv run src/workers/ingestion_worker.py
```

## Using Airflow (Optional)
If you prefer Airflow over the Python worker:
1. Copy `airflow/dags/local_ingestion_dag.py` to your `$AIRFLOW_HOME/dags`
2. Ensure Airflow has access to the project root path.
3. Enable the `local_pdf_ingestion` DAG.

## Telegram Bot
The Telegram features gracefully degrade if not configured. To enable them:
1. Set `TELEGRAM__ENABLED=true` in `.env`
2. Set `TELEGRAM__BOT_TOKEN=your_token` in `.env`

## Testing new configurations
- `VECTOR_STORE=qdrant`: Uses the local Qdrant instance.
- `EMBEDDINGS_PROVIDER=ollama`: Uses SentenceTransformers locally instead of Jina.
- `TRACER=local_log`: Writes tracing spans to standard rolling local logs in the `logs/` directory.
