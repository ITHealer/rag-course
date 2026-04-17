import json
import logging
import os
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Dict, Optional
from uuid import uuid4

from src.services.tracing.base import BaseTracer

class LocalLogTracer(BaseTracer):
    """File-based structured logging tracer with daily rotation and 5-day retention.
    
    Implements BaseTracer for zero-cost observability.
    """
    client = None

    def __init__(self, log_dir: str = "logs"):
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "tracing.log")
        
        # Setup specific logger for tracing
        self.logger = logging.getLogger("rag_local_tracer")
        self.logger.setLevel(logging.INFO)
        
        # Prevent propagation to root logger to avoid duplicate console logs
        self.logger.propagate = False
        
        # Remove existing handlers to avoid duplicates on re-init
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            
        # Daily rotation, keep 5 days
        handler = TimedRotatingFileHandler(
            self.log_file,
            when="midnight",
            interval=1,
            backupCount=5,
            encoding="utf-8"
        )
        
        # Simple JSON-like format
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # We also want to log to console if DEBUG is on, but structure it
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter('TRACER: %(message)s'))
        console.setLevel(logging.DEBUG)
        self.logger.addHandler(console)

    def _log_json(self, record: Dict[str, Any]):
        """Write JSON record to log file."""
        record["timestamp"] = datetime.utcnow().isoformat() + "Z"
        try:
            self.logger.info(json.dumps(record, default=str))
        except Exception as e:
            # Fallback for unserializable types
            record["serialization_error"] = str(e)
            self.logger.info(json.dumps({k: str(v) for k, v in record.items()}))

    def start_span(self, name: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        span_id = str(uuid4())
        record = {
            "type": "span_start",
            "span_id": span_id,
            "name": name,
            "metadata": metadata or {},
            "start_time": time.time()
        }
        record.update(kwargs)
        self._log_json(record)
        
        # Return a simple mock span object that holds state
        class LocalSpan:
            def __init__(self, tracer, span_id, name):
                self.tracer = tracer
                self.span_id = span_id
                self.name = name
                self.start_time = time.time()
                
            def end(self, **end_kwargs):
                self.tracer.end_span(self, **end_kwargs)
                
            def update(self, **update_kwargs):
                self.tracer.log_event("span_update", update_kwargs, self)
                
            def event(self, name: str, output: Any):
                self.tracer.log_event(name, {"output": output}, self)
                
        return LocalSpan(self, span_id, name)

    def end_span(self, span: Any, **kwargs):
        if not span:
            return
            
        duration_ms = (time.time() - span.start_time) * 1000
        record = {
            "type": "span_end",
            "span_id": span.span_id,
            "name": span.name,
            "duration_ms": round(duration_ms, 2)
        }
        record.update(kwargs)
        self._log_json(record)

    def log_event(self, event_name: str, event_data: Dict[str, Any], span: Optional[Any] = None):
        record = {
            "type": "event",
            "event_name": event_name,
            "data": event_data
        }
        if span:
            record["span_id"] = span.span_id
            record["span_name"] = span.name
            
        self._log_json(record)

    def flush(self):
        """No-op for local log tracer."""
        pass

    def shutdown(self):
        self._log_json({"type": "system", "event": "tracer_shutdown"})
