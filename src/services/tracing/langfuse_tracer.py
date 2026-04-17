import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from langfuse import Langfuse
from src.config import Settings
from src.services.tracing.base import BaseTracer

logger = logging.getLogger(__name__)


class LangfuseTracer(BaseTracer):
    """Langfuse tracer implementing BaseTracer."""

    def __init__(self, settings):
        self.settings = settings
        self.client: Optional[Langfuse] = None

        if self.settings.enabled and self.settings.public_key and self.settings.secret_key:
            try:
                self.client = Langfuse(
                    public_key=self.settings.public_key,
                    secret_key=self.settings.secret_key,
                    host=self.settings.host,
                    flush_at=self.settings.flush_at,
                    flush_interval=self.settings.flush_interval,
                    debug=self.settings.debug,
                )
                logger.info(f"Langfuse v3 tracing initialized (host: {self.settings.host})")
            except Exception as e:
                logger.error(f"Failed to initialize Langfuse: {e}")
                self.client = None
        else:
            logger.info("Langfuse tracing disabled or missing credentials")

    def start_span(self, name: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Start a generic span."""
        if not self.client:
            return None
        
        try:
            return self.client.span(
                name=name,
                metadata=metadata or {},
                **kwargs
            )
        except Exception as e:
            logger.error(f"Error creating span: {e}")
            return None

    def end_span(self, span: Any, **kwargs):
        """End a previously tracked span with optional kwargs like output/level."""
        if not span:
            return
        
        try:
            span.update(**kwargs)
            span.end()
        except Exception as e:
            logger.error(f"Error updating span: {e}")

    def log_event(self, event_name: str, event_data: Dict[str, Any], span: Optional[Any] = None):
        """Log a specific event/metric to the tracing system."""
        if not self.client:
            return
            
        try:
            if span:
                span.event(name=event_name, output=event_data)
            else:
                self.client.event(name=event_name, output=event_data)
        except Exception as e:
            logger.error(f"Error logging event: {e}")

    def flush(self):
        """Flush any pending traces."""
        if self.client:
            try:
                self.client.flush()
            except Exception as e:
                logger.error(f"Error flushing Langfuse: {e}")

    def shutdown(self):
        """Shutdown the Langfuse client."""
        if self.client:
            try:
                self.client.flush()
                self.client.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down Langfuse: {e}")

    # Specific Langfuse methods kept for backward compatibility with RAGTracer
    def trace_rag_request(self, query: str, user_id: str, session_id: str, metadata: Dict):
        if not self.client:
            # return a dummy context manager
            @contextmanager
            def dummy():
                yield None
            return dummy()
            
        return self.client.trace(name="rag_request", user_id=user_id, session_id=session_id, metadata=metadata, input=query)
        
    def create_span(self, trace, name: str, input_data: Any):
        if not trace: 
            return self.start_span(name=name, input_data=input_data)
        return trace.span(name=name, input=input_data)

    def update_span(self, span, output: Any):
        self.end_span(span, output=output)


class RAGTracer:
    """Clean, purpose-built tracer for RAG operations."""

    def __init__(self, tracer: LangfuseTracer):
        self.tracer = tracer

    @contextmanager
    def trace_request(self, user_id: str, query: str):
        """Main request trace context manager."""
        trace = None
        try:
            if hasattr(self.tracer, 'trace_rag_request'):
                with self.tracer.trace_rag_request(
                    query=query, user_id=user_id, session_id=f"session_{user_id}", metadata={"simplified_tracing": True}
                ) as trace:
                    yield trace
            else:
                yield None
        finally:
            if trace and hasattr(self.tracer, 'flush'):
                self.tracer.flush()

    @contextmanager
    def trace_embedding(self, trace, query: str):
        """Query embedding operation with timing."""
        start_time = time.time()
        span = None
        if hasattr(self.tracer, 'create_span'):
            span = self.tracer.create_span(
                trace=trace, name="query_embedding", input_data={"query": query, "query_length": len(query)}
            )
        try:
            yield span
        finally:
            duration = time.time() - start_time
            if span:
                self.tracer.update_span(span=span, output={"embedding_duration_ms": round(duration * 1000, 2), "success": True})

    @contextmanager
    def trace_search(self, trace, query: str, top_k: int):
        """Search operation with timing."""
        span = None
        if hasattr(self.tracer, 'create_span'):
            span = self.tracer.create_span(trace=trace, name="search_retrieval", input_data={"query": query, "top_k": top_k})
        try:
            yield span
        finally:
            if span and hasattr(span, 'end'):
                span.end()

    def end_search(self, span, chunks: List[Dict], arxiv_ids: List[str], total_hits: int):
        """End search span with essential results."""
        if not span:
            return

        self.tracer.update_span(
            span=span,
            output={
                "chunks_returned": len(chunks),
                "unique_papers": len(set(arxiv_ids)),
                "total_hits": total_hits,
                "arxiv_ids": list(set(arxiv_ids)),
            },
        )

    @contextmanager
    def trace_prompt_construction(self, trace, chunks: List[Dict]):
        """Prompt building with timing."""
        span = None
        if hasattr(self.tracer, 'create_span'):
            span = self.tracer.create_span(trace=trace, name="prompt_construction", input_data={"chunk_count": len(chunks)})
        try:
            yield span
        finally:
            if span and hasattr(span, 'end'):
                span.end()

    def end_prompt(self, span, prompt: str):
        """End prompt span with final prompt."""
        if not span:
            return

        self.tracer.update_span(
            span=span,
            output={
                "prompt_length": len(prompt),
                "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            },
        )

    @contextmanager
    def trace_generation(self, trace, model: str, prompt: str):
        """LLM generation with timing."""
        span = None
        if hasattr(self.tracer, 'create_span'):
            span = self.tracer.create_span(
                trace=trace, name="llm_generation", input_data={"model": model, "prompt_length": len(prompt), "prompt": prompt}
            )
        try:
            yield span
        finally:
            if span and hasattr(span, 'end'):
                span.end()

    def end_generation(self, span, response: str, model: str):
        """End generation span with response."""
        if not span:
            return

        self.tracer.update_span(span=span, output={"response": response, "response_length": len(response), "model_used": model})

    def end_request(self, trace, response: str, total_duration: float):
        """End main request trace."""
        if not trace:
            return

        try:
            trace.update(
                output={"answer": response, "total_duration_seconds": round(total_duration, 3), "response_length": len(response)}
            )
            if hasattr(trace, 'end'):
                trace.end()
        except Exception:
            pass
