"""Abstract base class for observability tracers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseTracer(ABC):
    """Abstract base class for distributed tracing systems."""

    @abstractmethod
    def start_span(self, name: str, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Start a new observability span.
        
        :param name: the span name
        :param metadata: optional dict containing arbitrary metadata to log
        :returns: the Span object to be closed/ended later
        """
        pass

    @abstractmethod
    def end_span(self, span: Any, **kwargs):
        """End a previously tracked span."""
        pass

    @abstractmethod
    def log_event(self, event_name: str, event_data: Dict[str, Any], span: Optional[Any] = None):
        """Log a specific event/metric to the tracing system."""
        pass

    @abstractmethod
    def shutdown(self):
        """Perform cleanup before system exit."""
        pass
