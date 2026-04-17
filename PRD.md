# Product Requirements Document (PRD): arXiv Paper Curator

## 1. Problem, Goals, Non-goals

**Problem:** 
Researchers, students, and engineers struggle to keep up with the overwhelming volume of academic papers published daily on arXiv. Finding relevant papers, extracting key information from dense PDFs, and synthesizing knowledge requires significant manual effort and time.

**Goals:** 
Build an end-to-end, production-grade intelligent research assistant ("arXiv Paper Curator") that automatically ingests, processes, and indexes academic papers. The system must provide a highly capable Agentic Retrieval-Augmented Generation (RAG) interface to allow users to semantically search and converse with the latest research using a web UI and a Telegram Bot.

**Non-goals:**
- Replacing general-purpose search engines (e.g., Google Scholar).
- Training new foundational LLMs from scratch.
- Processing non-academic general web content, news, or social media.

---

## 2. Personas + JTBD (Jobs to be Done)

**Persona 1: AI/ML Researcher or Student**
- **JTBD:** When researching a specific niche or new methodology, I want to ask natural language questions against the latest arXiv papers so I can quickly identify the state-of-the-art architectures without having to read dozens of PDFs manually.

**Persona 2: AI Software Engineer / Learner**
- **JTBD:** When tasked with building an enterprise LLM feature, I want a reference production-grade RAG architecture complete with tracing, exact-match caching, and agentic workflows so I can understand and implement industry best practices.

---

## 3. User Stories

- **[P0]** As a user, I want to search for academic papers using both exact keywords and semantic meaning (Hybrid Search).
- **[P0]** As a user, I want to ask complex natural language questions and receive synthesized answers backed by exact source citations and PDF links.
- **[P1]** As a user, I want the system to stream answers back to me in real-time so I don't have to wait for the complete LLM generation to finish.
- **[P1]** As a user, I want to interact with the research assistant via a Telegram Bot for seamless mobile access.
- **[P1]** As a user, I want the system to be "agentic"—automatically evaluating document relevance, rewriting my query if search results are poor, and detecting out-of-domain questions to prevent hallucinations.
- **[P2]** As an administrator, I want papers to be automatically fetched, parsed, and ingested daily without manual intervention.

---

## 4. Functional Requirements

- **Automated Data Ingestion:** 
  - Daily pipeline orchestrated via Apache Airflow to fetch papers using the arXiv API.
  - Process complex scientific PDFs using Docling to extract text, chunks, and metadata.
- **Search Capabilities API (`/api/v1/hybrid-search`):** 
  - Support BM25 keyword search, semantic search (via embeddings), and Hybrid Search using RRF (Reciprocal Rank Fusion).
- **RAG Endpoints (`/api/v1/ask`, `/api/v1/stream`):**
  - Prompt construction combining retrieved chunks and queries, executed against local LLMs (Ollama).
- **Agentic RAG Engine (`/api/v1/ask-agentic`):** 
  - LangGraph workflow incorporating decision nodes: Guardrails, Retrieval, Document Grading, Query Rewriting, and Answer Generation.
- **User Interfaces:** 
  - Gradio-based interactive web frontend.
  - Telegram Bot integration for conversational AI.
- **Feedback Loop (`/api/v1/feedback`):**
  - Allow users to rate answers and trace them in the observability platform.

---

## 5. Non-functional Requirements

- **Latency:** 
  - Streaming endpoints should achieve a Time To First Byte (TTFB) of under 2 seconds. 
  - Redis exact-match caching must provide sub-second responses for repeated queries.
- **Reliability:** 
  - arXiv API fetching must implement robust rate limiting and retry logic to gracefully handle API throttling.
  - Fallback mechanisms should exist (e.g., reverting to BM25 if embedding generation fails).
- **Scalability & Architecture:** 
  - Microservices architecture deployed via Docker Compose allowing independent scaling of OpenSearch, PostgreSQL, Airflow, and the FastAPI application.
- **Observability:** 
  - End-to-end pipeline tracing using Langfuse to monitor chunk relevance, LLM inference times, and cost optimization.
- **Security & Privacy:** 
  - Local LLM execution via Ollama to guarantee data privacy. 
  - Secure `.env` management for external API keys (Telegram, Jina AI, Langfuse).

---

## 6. Metrics

**North-Star Metrics:**
- **Daily Active Queries (DAQ):** Total number of questions asked through the Web UI and Telegram bot.
- **User Answer Acceptance Rate:** Percentage of feedback rated positively (thumbs up) vs negatively.

**Guardrails:**
- **Pipeline Error Rate:** < 5% failure rate for the daily Airflow ingestion DAGs.
- **LLM Generation Latency:** < 5 seconds average for complete non-streaming responses, TTFB < 2s for streaming.
- **Cache Hit Ratio:** > 20% to validate caching strategy effectiveness.
- **Hallucination / Out-of-Domain Rate:** Tracking the frequency of the Guardrail node correctly rejecting off-topic prompts.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
| :--- | :--- |
| **arXiv API Rate Limits:** IP blocking due to excessive fetching. | Implement exponential backoff, strict request pacing in `ArxivClient`, and track state robustly in Airflow. |
| **PDF Parsing Failures:** Inability to parse complex math equations or multi-column layouts. | Utilize specialized `Docling` parser and maintain a fallback to raw abstracts provided by the arXiv API. |
| **LLM Hallucinations:** Providing inaccurate answers or synthesizing fake citations. | Implement the Agentic "Document Grading" node to heavily filter irrelevant context, strictly prompt the LLM to only answer based on provided chunks, and enforce the Guardrail node. |
| **High Latency for Embeddings/LLM:** Local execution might be slow on limited hardware. | Emphasize Redis caching to serve repeated queries instantly; provide streaming endpoints to improve perceived latency. |

---

## 8. Open Questions

1. **Source Expansion:** Should the ingestion pipeline be generalized to support other research repositories (e.g., PubMed, IEEE, ACL Anthology) in the future?
2. **Authentication / Multi-tenancy:** Do we need structured user accounts and authentication for the Gradio App and APIs, or is the Telegram Bot sufficient for user-level isolation?
3. **Cache Invalidation Policy:** What is the optimal Time-To-Live (TTL) or eviction policy for exact match caching in Redis given the daily ingestion of new papers?
4. **Cloud Migration:** If user demand scales beyond local/single-server hardware capabilities, what is the strategy for migrating Ollama/OpenSearch to managed cloud services?
