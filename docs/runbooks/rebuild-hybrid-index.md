# Hybrid Index Rebuild Runbook

## Purpose

Rebuild `arxiv-papers-chunks` with the correct hybrid schema (`embedding: knn_vector`) when runtime mapping drift occurs (for example `embedding` becomes `float`).

## Preconditions

- OpenSearch is reachable at `OPENSEARCH__HOST`.
- API and Airflow services use the same OpenSearch cluster.
- You understand this procedure removes existing documents from the target index.

## 1. Verify the issue

Check mapping type for the embedding field:

```bash
curl -s "http://localhost:9200/arxiv-papers-chunks/_mapping"
```

Check index settings include k-NN:

```bash
curl -s "http://localhost:9200/arxiv-papers-chunks/_settings"
```

If `embedding.type` is not `knn_vector` or `index.knn` is not `true`, continue.

## 2. Stop writers

Stop ingestion and API write paths to avoid concurrent writes while rebuilding:

```bash
docker compose stop api airflow
```

## 3. Recreate index with canonical schema

Delete the incompatible index:

```bash
curl -X DELETE "http://localhost:9200/arxiv-papers-chunks"
```

Run index setup through application startup or setup task:

```bash
docker compose up -d opensearch
docker compose up -d api
```

The startup lifecycle calls `setup_indices(force=False)` and recreates the index + RRF pipeline if missing.

## 4. Validate rebuilt schema

```bash
curl -s "http://localhost:9200/arxiv-papers-chunks/_mapping"
curl -s "http://localhost:9200/arxiv-papers-chunks/_settings"
curl -s "http://localhost:9200/_search/pipeline/hybrid-rrf-pipeline"
```

Expected:

- `embedding.type` is `knn_vector`
- `embedding.dimension` matches `OPENSEARCH__VECTOR_DIMENSION` (default `1024`)
- `index.knn` is `true`
- search pipeline `hybrid-rrf-pipeline` exists

## 5. Reindex data

### Option A: arXiv pipeline

Run Airflow tasks that fetch/process/index papers. The indexing path now ensures schema setup before writes.

### Option B: local PDF ingestion

For local watcher ingestion, clear watcher state so old files are reprocessed:

```bash
rm -f .ingest_state.json
```

Then run the local ingestion DAG (or wait for schedule).

## 6. Smoke test search

Hybrid query:

```bash
curl -X POST "http://localhost:8000/api/v1/hybrid-search/" \
  -H "Content-Type: application/json" \
  -d '{"query":"machine learning","use_hybrid":true,"size":3}'
```

BM25 query:

```bash
curl -X POST "http://localhost:8000/api/v1/hybrid-search/" \
  -H "Content-Type: application/json" \
  -d '{"query":"machine learning","use_hybrid":false,"size":3}'
```

Expected:

- hybrid request returns `search_mode: "hybrid"` when schema is healthy
- if fallback occurs, response carries non-null `error` and `search_mode: "bm25"`

## 7. Resume services

```bash
docker compose up -d airflow
```

## Recovery note

If rebuild fails repeatedly, inspect:

1. any process writing before `setup_indices()` runs
2. mismatched OpenSearch endpoint between API and ingestion containers
3. `OPENSEARCH__INDEX_NAME` / `OPENSEARCH__CHUNK_INDEX_SUFFIX` overrides
